from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.model import Job, checkout_key, parse_utc
from app.storage import Store
from app.runner import Controller, command, acquire, schedule_after, lock_name

EVENT='6aaceecebfe408c38e1712dd'
URL=f'https://billett.rbk.no/checkout/{EVENT}'

def sample(base):
    p=base/'koteng'
    p.mkdir(exist_ok=True)
    for name in ('hourly_koteng.py','koteng_scanner.py','profile_lock.py','koteng_profile.json','ankerpunkter_koteng.json','sync_koteng.py'):
        (p/name).write_text('stub',encoding='utf-8')
    return Job(EVENT,'Rosenborg Røa','RBK Kvinner','koteng_arena',URL,
               (datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),
               'koteng_v24',str(p))

class FakePopen:
    instances=[]
    def __init__(self,*args,**kwargs):
        self.args=args
        self.kwargs=kwargs
        self.code=None
        self.instances.append(self)
    def poll(self):return self.code
    def terminate(self):self.code=-15

class ModelTests(unittest.TestCase):
    def test_url(self):
        self.assertEqual(checkout_key(URL),EVENT)
        for bad in (URL+'?test=1',URL.replace('https','http'),URL.replace('billett.rbk.no','bad.example'),
                    'https://billett.rbk.no/checkout/../',
                    'https://evil:b@billett.rbk.no/checkout/'+EVENT):
            with self.subTest(url=bad),self.assertRaises(ValueError):checkout_key(bad)
    def test_kickoff_requires_timezone(self):
        with self.assertRaises(ValueError):parse_utc('2026-11-01T14:30:00')
        self.assertEqual(parse_utc('2026-11-01T14:30:00+01:00').hour,13)
    def test_profile_locks_event(self):
        with tempfile.TemporaryDirectory() as td:
            j=sample(Path(td))
            with self.assertRaises(ValueError):replace(j,key='6a9a7e3f3f93920b289b0675',url='https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675')
            with self.assertRaises(ValueError):replace(j,venue='lerkendal')
            with self.assertRaises(ValueError):replace(j,interval_minutes=5)
    def test_schedule_and_no_catchup(self):
        with tempfile.TemporaryDirectory() as td:
            j=sample(Path(td))
            t=datetime(2026,10,27,10,tzinfo=timezone.utc)
            self.assertEqual(parse_utc(schedule_after(j,0,t))-t,timedelta(hours=1))
            self.assertEqual(parse_utc(schedule_after(j,1,t))-t,timedelta(minutes=10))
            self.assertEqual(parse_utc(schedule_after(j,5,t))-t,timedelta(minutes=60))
    def test_lock_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/lock_name(EVENT)
            acquire(p)
            with self.assertRaises(FileExistsError):acquire(p)
            self.assertTrue(p.exists())
    def test_command_no_custom_event(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);j=sample(base)
            cmd,cwd,interactive=command(j,base,python='fakepy')
            self.assertEqual(cmd[:2],['fakepy',str(cwd/'hourly_koteng.py')])
            self.assertIn('--once',cmd);self.assertNotIn('--upload',cmd)
            self.assertFalse(interactive)
            self.assertIn('--upload',command(replace(j,enabled=True,upload=True),base,'python')[0])

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.store=Store(self.base/'state'/'db.sqlite')
        self.addCleanup(self.store.close)
        self.job=sample(self.base)
        self.store.put_job(self.job)
        self.procs=[]
        def factory(*a,**kw):
            p=FakePopen(*a,**kw);self.procs.append(p);return p
        self.ctrl=Controller(self.base,self.store,popen=factory)

    def test_initially_off_and_opt_in(self):
        self.ctrl.poll()
        self.assertEqual(self.procs,[])
        with self.assertRaises(RuntimeError):self.ctrl.start(self.job)
        self.ctrl.enable(EVENT,True)
        self.assertTrue(self.store.jobs()[0].enabled)
        self.assertIsNotNone(self.store.state(EVENT)['next_due'])

    def test_run_after_enable_and_verify_report(self):
        self.ctrl.enable(EVENT,True)
        self.ctrl.poll()
        self.assertEqual(len(self.procs),1)
        self.assertTrue((self.base/'state'/'locks'/lock_name(EVENT)).exists())
        with self.assertRaises(RuntimeError):self.ctrl.start(self.job,force=True)
        payload={'event_key':EVENT,'run_id':'test-id','observed_at':'2026-10-27T10:00:00+00:00',
                 'available_seated':424,'sections':[{'section':k} for k in range(6)],'quality_status':'LOCKED_LOCAL_VERIFIED'}
        self.procs[0].code=0
        with mock.patch('app.observations.verified_new_report',return_value=payload):
            self.ctrl.poll()
        self.assertEqual(self.store.latest(EVENT)['available_seated'],424)
        self.assertEqual(self.store.state(EVENT)['last_status'],'fullført')
        self.assertFalse((self.base/'state'/'locks'/lock_name(EVENT)).exists())
        self.assertIsNotNone(self.store.state(EVENT)['next_due'])

    def test_bad_report_rejected(self):
        self.ctrl.start(self.job,force=True)
        self.procs[0].code=0
        with mock.patch('app.observations.verified_new_report',side_effect=ValueError('bad signature')):
            self.ctrl.poll()
        self.assertEqual(self.store.state(EVENT)['last_status'],'feil')
        self.assertIsNone(self.store.latest(EVENT))
        self.assertIn('kontroll',self.ctrl.error)

    def test_kickoff_stops_new_scans(self):
        old=replace(self.job,kickoff_at='2020-01-01T00:00:00Z',enabled=True)
        self.store.put_job(old)
        self.store.set_due(EVENT,'2020-01-01T00:00:00Z')
        self.ctrl.poll()
        self.assertEqual(len(self.procs),0)
        self.assertEqual(self.store.state(EVENT)['last_status'],'ferdig')

    def test_failure_backoff(self):
        self.ctrl.enable(EVENT,True)
        self.ctrl.poll()
        self.procs[0].code=2
        self.ctrl.poll()
        self.assertEqual(self.store.state(EVENT)['failures'],1)
        self.assertEqual(self.store.state(EVENT)['last_status'],'feil')

    def test_persist_config_and_distinct_jobs(self):
        job2=Job('6a9a7c2b15599587216e21f3','RBK Start','RBK Herrer','lerkendal',
                 'https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3',
                 (datetime.now(timezone.utc)+timedelta(days=9)).isoformat(),
                 'lerkendal_legacy',str(self.base/'lerkendal'))
        self.store.put_job(job2)
        self.assertEqual(len(self.store.jobs()),2)
        self.assertNotEqual(self.store.state(EVENT)['config_json'],self.store.state(job2.key)['config_json'])
        self.ctrl.poll()
        self.assertEqual(len(self.procs),0)

if __name__=='__main__':unittest.main()
