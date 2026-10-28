from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import locks, oslo
from app.model import Job, checkout_key, parse_utc
from app.storage import Store
from app.runner import Controller, command, acquire, schedule_after, outbox_retry, lock_name
from app import runner

EVENT='6aaceecebfe408c38e1712dd'
URL=f'https://billett.rbk.no/checkout/{EVENT}'
DEAD_PID=999999

def sample(base,**kw):
    p=base/'koteng'
    p.mkdir(exist_ok=True)
    for name in ('hourly_koteng.py','koteng_scanner.py','profile_lock.py','koteng_profile.json','ankerpunkter_koteng.json','sync_koteng.py'):
        (p/name).write_text('stub',encoding='utf-8')
    (base/'engines').mkdir(exist_ok=True)
    (base/'engines'/'koteng_once.py').write_text('stub',encoding='utf-8')
    job=Job(EVENT,'Rosenborg Røa','RBK Kvinner','koteng_arena',URL,
            (datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),
            'koteng_v24',str(p))
    return replace(job,**kw)

def verified(run='test-id',free=424,diag=''):
    return {'event_key':EVENT,'run_id':run,'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'available_seated':free,'sections':[{'section':k} for k in range(6)],
            'quality_status':'LOCKED_LOCAL_VERIFIED','diagnostic':diag}

class FakePopen:
    instances=[]
    next_pid=DEAD_PID
    def __init__(self,*args,**kwargs):
        self.args=args
        self.kwargs=kwargs
        self.code=None
        self.pid=FakePopen.next_pid
        self.instances.append(self)
    def poll(self):return self.code
    def terminate(self):self.code=-15

class OsloTests(unittest.TestCase):
    def test_winter_and_summer(self):
        self.assertEqual(oslo.parse_local('01.11.2026','14:30'),datetime(2026,11,1,13,30,tzinfo=timezone.utc))
        self.assertEqual(oslo.parse_local('15.07.2026','19:00'),datetime(2026,7,15,17,0,tzinfo=timezone.utc))
    def test_dst_edges(self):
        # 2026: summer time 29 March 01:00 UTC -> 25 October 01:00 UTC
        self.assertEqual(oslo.to_oslo(datetime(2026,3,29,0,59,tzinfo=timezone.utc)).hour,1)
        self.assertEqual(oslo.to_oslo(datetime(2026,3,29,1,0,tzinfo=timezone.utc)).hour,3)
        self.assertEqual(oslo.to_oslo(datetime(2026,10,25,0,59,tzinfo=timezone.utc)).hour,2)
        self.assertEqual(oslo.to_oslo(datetime(2026,10,25,1,0,tzinfo=timezone.utc)).hour,2)
        with self.assertRaises(ValueError):oslo.parse_local('29.03.2026','02:30')
        self.assertEqual(oslo.parse_local('25.10.2026','02:30').hour,0)  # first (summer) occurrence
    def test_round_trip(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        while t.year==2026:
            self.assertEqual(oslo.from_oslo(oslo.to_oslo(t)),t) if not (t.month==10 and oslo.to_oslo(t).hour==2) else None
            t+=timedelta(hours=7)
    def test_bad_input(self):
        for d,h in (('2026-11-01','14:30'),('31.02.2026','10:00'),('01.11.2026','25:00')):
            with self.subTest(d=d,h=h),self.assertRaises(ValueError):oslo.parse_local(d,h)

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
            # V0.2: any approved Koteng match (stadium lock, not match lock); key and URL must agree
            other=replace(j,key='6ac390963b28cba4d656278f',url='https://billett.rbk.no/checkout/6ac390963b28cba4d656278f')
            self.assertEqual(other.venue,'koteng_arena')
            with self.assertRaises(ValueError):replace(j,key='6ac390963b28cba4d656278f')
            with self.assertRaises(ValueError):replace(j,venue='lerkendal')
            with self.assertRaises(ValueError):replace(j,interval_minutes=5)
            with self.assertRaises(ValueError):replace(j,stop_before_minutes=-31)
    def test_v01_config_loads(self):
        with tempfile.TemporaryDirectory() as td:
            data=sample(Path(td)).as_json();data.pop('stop_before_minutes')
            self.assertEqual(Job.from_json(data).stop_before_minutes,-5)
    def test_schedule_and_no_catchup(self):
        with tempfile.TemporaryDirectory() as td:
            j=sample(Path(td))
            t=datetime(2026,10,27,10,tzinfo=timezone.utc)
            self.assertEqual(parse_utc(schedule_after(j,0,t))-t,timedelta(hours=1))
            self.assertEqual(parse_utc(schedule_after(j,1,t))-t,timedelta(minutes=10))
            self.assertEqual(parse_utc(schedule_after(j,5,t))-t,timedelta(minutes=60))
    def test_final_phase_every_15_min(self):
        with tempfile.TemporaryDirectory() as td:
            j=replace(sample(Path(td)),kickoff_at='2026-10-29T17:00:00+00:00')
            k=j.kickoff();fs=k-timedelta(minutes=85)
            self.assertEqual(j.final_start(),fs);self.assertEqual(j.last_start(),k+timedelta(minutes=5))
            # follow the slots -85,-70,...,-10,+5 (a scan finishing ~30 s after its slot)
            t,slots=fs-timedelta(minutes=20),[]
            while t<j.start_deadline():
                t=parse_utc(schedule_after(j,0,t));slots.append(int((t-k).total_seconds()//60));t+=timedelta(seconds=30)
            self.assertEqual(slots,[-85,-70,-55,-40,-25,-10,5,20])
            self.assertEqual(parse_utc(schedule_after(j,3,fs+timedelta(seconds=30))),fs+timedelta(minutes=15))
            # a slot planned with the old hourly rule is pulled forward
            self.assertEqual(j.effective_due(fs+timedelta(minutes=40),fs-timedelta(hours=1)),fs)
            self.assertEqual(j.effective_due(fs+timedelta(minutes=50),fs+timedelta(minutes=5)),fs+timedelta(minutes=15))
            self.assertEqual(j.effective_due(fs+timedelta(minutes=15),fs+timedelta(minutes=16)),fs+timedelta(minutes=15))
            with self.assertRaises(ValueError):replace(j,final_interval_minutes=5)
            data=j.as_json();data.pop('final_window_minutes');data.pop('final_interval_minutes')
            self.assertEqual((Job.from_json(data).final_window_minutes,Job.from_json(data).final_interval_minutes),(90,15))
    def test_outbox_backoff(self):
        t=datetime(2026,10,27,10,tzinfo=timezone.utc)
        self.assertEqual(parse_utc(outbox_retry(1,t,0))-t,timedelta(minutes=2))
        self.assertEqual(parse_utc(outbox_retry(9,t,0))-t,timedelta(minutes=60))
    def test_lock_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/lock_name(EVENT)
            acquire(p)
            with self.assertRaises(FileExistsError):acquire(p)
            self.assertTrue(p.exists())
    def test_command_never_uploads(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);j=sample(base)
            cmd,cwd,interactive=command(j,base,python='fakepy',report=base/'r.json')
            self.assertEqual(cmd[:2],['fakepy',str(base/'engines'/'koteng_once.py')])
            self.assertIn(URL,cmd);self.assertNotIn('--upload',cmd);self.assertNotIn('--send',cmd)
            self.assertFalse(interactive)
            self.assertNotIn('--upload',command(replace(j,enabled=True,upload=True),base,'python',report=base/'r.json')[0])

class LockTests(unittest.TestCase):
    def test_own_pid_alive_dead_pid_not(self):
        self.assertTrue(locks.pid_alive(os.getpid()))
        self.assertFalse(locks.pid_alive(DEAD_PID))
    def test_release_refuses_living_process(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.lock';acquire(p)
            with self.assertRaises(locks.LockBusy):locks.release(p)
            locks.release(p,force_own=True);self.assertFalse(p.exists())
    def test_program_lock(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'app.lock'
            locks.acquire_program(p)
            with self.assertRaises(locks.LockBusy):locks.acquire_program(p)
            p.write_text(f'controller_pid={DEAD_PID}\n',encoding='utf-8')
            locks.acquire_program(p)  # stale program lock is replaced
            self.assertEqual(locks.read(p)['controller_pid'],str(os.getpid()))

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
        self.addCleanup(self.close_logs)
        self.lock=self.base/'state'/'locks'/lock_name(EVENT)

    def close_logs(self):
        for a in self.ctrl.active.values():
            if a.log:a.log.close()
        if self.ctrl.sending:self.ctrl.sending.log.close()

    def finish_scan(self,result=None,code=0,when=None):
        self.procs[-1].code=code
        with mock.patch('app.observations.verified_koteng',return_value=result or verified()):
            self.ctrl.poll(when)

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
        self.assertTrue(self.lock.exists())
        self.assertEqual(locks.read(self.lock)['child_pid'],str(DEAD_PID))
        with self.assertRaises(RuntimeError):self.ctrl.start(self.job,force=True)
        self.finish_scan()
        self.assertEqual(self.store.latest(EVENT)['available_seated'],424)
        self.assertEqual(self.store.state(EVENT)['last_status'],runner.VERIFIED)
        self.assertFalse(self.lock.exists())
        self.assertIsNotNone(self.store.state(EVENT)['next_due'])
        self.assertEqual(self.store.outbox_counts(),{})  # not live: nothing queued

    def test_bad_report_rejected(self):
        self.ctrl.start(self.job,force=True)
        self.procs[0].code=0
        with mock.patch('app.observations.verified_koteng',side_effect=ValueError('bad signature')):
            self.ctrl.poll()
        self.assertEqual(self.store.state(EVENT)['last_status'],'feil')
        self.assertIsNone(self.store.latest(EVENT))
        self.assertTrue(any('Kontroll' in m for m in self.ctrl.messages))

    def test_kickoff_stops_new_scans(self):
        old=replace(self.job,kickoff_at='2020-01-01T00:00:00Z',enabled=True)
        self.store.put_job(old)
        self.store.set_due(EVENT,'2020-01-01T00:00:00Z')
        self.ctrl.poll()
        self.assertEqual(len(self.procs),0)
        self.assertEqual(self.store.state(EVENT)['last_status'],'ferdig')

    def test_no_start_inside_kickoff_margin(self):
        soon=replace(self.job,kickoff_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),enabled=True,stop_before_minutes=20)
        self.store.put_job(soon)
        with self.assertRaises(RuntimeError):self.ctrl.start(soon,force=True)
        self.assertEqual(self.store.state(EVENT)['last_status'],'ferdig')
        self.assertEqual(self.procs,[])

    def test_scan_after_kickoff_allowed_until_last_slot(self):
        started=replace(self.job,kickoff_at=(datetime.now(timezone.utc)-timedelta(minutes=4)).isoformat(),enabled=True)
        self.store.put_job(started)
        self.ctrl.start(started,force=True)  # last slot is kickoff + 5 min
        self.assertEqual(len(self.procs),1)

    def test_running_scan_killed_after_last_slot(self):
        job=replace(self.job,kickoff_at=(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat())
        self.store.put_job(job)
        self.ctrl.start(job,force=True)
        with mock.patch('app.runner._kill_tree',side_effect=lambda p:setattr(p,'code',1)):
            self.ctrl.poll(job.kickoff()+timedelta(seconds=1))
            self.assertIsNone(self.ctrl.active[EVENT].stop_reason)  # kickoff alone no longer stops it
            self.ctrl.poll(job.hard_stop()+timedelta(seconds=1))
            self.ctrl.poll(job.hard_stop()+timedelta(seconds=3))
        self.assertEqual(self.store.state(EVENT)['last_status'],runner.KICKOFF)
        self.assertIsNone(self.store.latest(EVENT))

    def test_failure_backoff(self):
        self.ctrl.enable(EVENT,True)
        self.ctrl.poll()
        self.procs[0].code=2
        self.ctrl.poll()
        self.assertEqual(self.store.state(EVENT)['failures'],1)
        self.assertEqual(self.store.state(EVENT)['last_status'],'feil')

    def test_stale_lock_needs_review(self):
        self.lock.parent.mkdir(parents=True)
        self.lock.write_text(f'controller_pid={DEAD_PID}\nchild_pid={DEAD_PID}\n',encoding='utf-8')
        self.ctrl.enable(EVENT,True)
        self.ctrl.mark_stale_locks()
        self.assertEqual(self.store.state(EVENT)['last_status'],runner.REVIEW)
        self.ctrl.poll()
        self.assertEqual(self.procs,[])  # no retry storm against a review lock
        self.ctrl.release_lock(EVENT)
        self.assertFalse(self.lock.exists())
        self.ctrl.poll()
        self.assertEqual(len(self.procs),1)

    def test_orphan_process_blocks_release(self):
        self.lock.parent.mkdir(parents=True)
        self.lock.write_text(f'controller_pid={DEAD_PID}\nchild_pid={os.getppid()}\n',encoding='utf-8')
        with self.assertRaises(locks.LockBusy):self.ctrl.release_lock(EVENT)

    def test_live_publishes_only_via_outbox(self):
        diag=self.base/'diag.json';diag.write_text('{}',encoding='utf-8')
        self.ctrl.enable(EVENT,True,True)
        self.ctrl.poll()
        self.finish_scan(verified(diag=str(diag)))
        self.assertEqual(self.store.state(EVENT)['last_status'],runner.QUEUED)
        # the same poll started the sender
        sender=self.procs[-1]
        self.assertEqual(sender.args[0][1:],['-c',runner.SEND_KOTENG,str(self.base/'engines'),EVENT,str(diag)])
        self.assertEqual(self.store.outbox_counts(),{'sender':1})
        sender.code=0;self.ctrl.poll()
        self.assertEqual(self.store.outbox_counts(),{'sendt':1})
        self.assertEqual(self.store.history(EVENT)[0]['publish_status'],'sendt')

    def test_outbox_retries_then_gives_up(self):
        diag=self.base/'diag.json';diag.write_text('{}',encoding='utf-8')
        self.ctrl.enable(EVENT,True,True)
        self.store.enqueue(verified(diag=str(diag)),str(diag))
        t=datetime.now(timezone.utc)
        for attempt in range(runner.OUTBOX_MAX_ATTEMPTS):
            self.ctrl.poll(t)
            self.assertIsNotNone(self.ctrl.sending,attempt)
            self.ctrl.sending.process.code=2
            self.ctrl.poll(t)
            row=self.store.db.execute('SELECT next_try FROM outbox').fetchone()
            t=max(t,parse_utc(row['next_try']))
            if attempt==0:self.assertEqual(self.store.outbox_counts(),{'venter':1})
        self.assertEqual(self.store.outbox_counts(),{'forkastet':1})

    def test_live_off_stops_queued_publication(self):
        diag=self.base/'diag.json';diag.write_text('{}',encoding='utf-8')
        self.ctrl.enable(EVENT,True,True)
        self.store.enqueue(verified(diag=str(diag)),str(diag))
        self.ctrl.enable(EVENT,True,False)
        self.ctrl.poll()
        self.assertEqual(self.store.outbox_counts(),{'stoppet':1})
        self.assertFalse(any('--send' in p.args[0] for p in self.procs))

    def test_crash_mid_send_requeues(self):
        self.store.enqueue(verified(),'x')
        with self.store.write() as db:db.execute("UPDATE outbox SET status='sender'")
        self.ctrl.recover_outbox()
        self.assertEqual(self.store.outbox_counts(),{'venter':1})

    def test_history_delta(self):
        for i,(run,free) in enumerate((('a1',500),('a2',470),('a3',470))):
            v=verified(run,free);v['observed_at']=f'2026-10-27T1{i}:00:00+00:00'
            self.store.observation(v,False)
        h=self.store.history(EVENT)
        self.assertEqual([r['delta'] for r in h],[0,-30,None])

    def test_edit_rules(self):
        with self.assertRaises(ValueError):self.ctrl.save_job(self.job)  # duplicate add
        self.ctrl.enable(EVENT,True)
        self.ctrl.save_job(replace(self.job,label='Nytt navn'),EVENT)
        self.assertFalse(self.store.job(EVENT).enabled)  # edits land deactivated
        self.ctrl.start(self.job,force=True)
        with self.assertRaises(RuntimeError):self.ctrl.save_job(self.job,EVENT)
        with self.assertRaises(RuntimeError):self.ctrl.delete_job(EVENT)

    def test_one_koteng_at_a_time(self):
        self.ctrl.start(self.job,force=True)
        other=replace(self.job)  # same profile, simulated second job
        self.ctrl.active['other']=self.ctrl.active.pop(EVENT)
        with self.assertRaises(RuntimeError):self.ctrl.start(other,force=True)

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

class MigrationTests(unittest.TestCase):
    def test_v01_database_upgrades_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'control.sqlite3'
            db=sqlite3.connect(path)
            db.executescript('''CREATE TABLE jobs (key TEXT PRIMARY KEY, config_json TEXT NOT NULL,
                next_due TEXT, failures INTEGER NOT NULL DEFAULT 0, last_status TEXT NOT NULL DEFAULT 'klar',
                last_finished TEXT, last_log TEXT);''')
            data=sample(Path(td)).as_json();data.pop('stop_before_minutes')
            import json;db.execute('INSERT INTO jobs(key,config_json) VALUES (?,?)',(EVENT,json.dumps(data)));db.commit();db.close()
            store=Store(path)
            try:
                self.assertEqual(store.jobs()[0].key,EVENT)
                self.assertIn('note',store.state(EVENT))
            finally:store.close()

if __name__=='__main__':unittest.main()
