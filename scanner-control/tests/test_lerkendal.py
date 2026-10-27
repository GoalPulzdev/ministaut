from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.model import Job
from app.storage import Store
from app.runner import Controller, command, LERKENDAL_PORT
from app import runner

ROOT=Path(__file__).resolve().parents[1]
KEY='6a9a7e3f3f93920b289b0675'
URL='https://billett.rbk.no/checkout/'+KEY
ENGINE_FILES=('hurtigkart.py','publication.py','sync_ministaut.py','match_config.py','verified_navigation.py','stadion_felt.json')

def engine(base):
    p=base/'lerkendal';p.mkdir(exist_ok=True)
    for name in ENGINE_FILES:(p/name).write_text('stub',encoding='utf-8')
    (base/'engines').mkdir(exist_ok=True)
    (base/'engines'/'lerkendal_once.py').write_text('stub',encoding='utf-8')
    return Job(KEY,'Rosenborg – Molde','RBK Herrer','lerkendal',URL,
               (datetime.now(timezone.utc)+timedelta(days=5)).isoformat(),'lerkendal_v23',str(p))

class FakePopen:
    def __init__(self,*a,**kw):self.args=a;self.kwargs=kw;self.code=None;self.pid=999999
    def poll(self):return self.code

class ControllerLerkendal(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name);self.store=Store(self.base/'state'/'db.sqlite');self.addCleanup(self.store.close)
        self.job=engine(self.base);self.store.put_job(self.job);self.procs=[]
        def factory(*a,**kw):
            p=FakePopen(*a,**kw);self.procs.append(p);return p
        self.ctrl=Controller(self.base,self.store,popen=factory)
        def close_logs():
            for a in self.ctrl.active.values():
                if a.log:a.log.close()
            if self.ctrl.sending:self.ctrl.sending.log.close()
        self.addCleanup(close_logs)

    def test_command_uses_wrapper_and_own_port(self):
        cmd,cwd,interactive=command(self.job,self.base,'py',report=self.base/'r.json')
        self.assertEqual(cmd[1],str(self.base/'engines'/'lerkendal_once.py'))
        self.assertIn(str(LERKENDAL_PORT),cmd);self.assertNotIn('9222',cmd)
        self.assertFalse(interactive)

    def test_rejected_scan_is_not_stored(self):
        self.ctrl.start(self.job,force=True)
        report=self.ctrl.active[KEY].report
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps({'event_key':KEY,'accepted':False,'reason':'Mangler felt: E1'}),encoding='utf-8')
        self.procs[0].code=4;self.ctrl.poll()
        st=self.store.state(KEY)
        self.assertEqual(st['last_status'],runner.REJECTED);self.assertIn('E1',st['note'])
        self.assertIsNone(self.store.latest(KEY))

    def test_verified_scan_queued_and_sent_with_engine_payload(self):
        res=self.base/'out'/'resultat.json';res.parent.mkdir();res.write_text('{}',encoding='utf-8')
        self.ctrl.enable(KEY,True,True);self.ctrl.poll()
        self.assertEqual(len(self.procs),1)
        data={'event_key':KEY,'run_id':'a'*32,'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'available_seated':4321,'sections':list(range(60)),'quality_status':'LERKENDAL_60_VERIFIED','diagnostic':str(res)}
        self.procs[0].code=0
        with mock.patch('app.observations.verified_lerkendal',return_value=data):self.ctrl.poll()
        self.assertEqual(self.store.state(KEY)['last_status'],runner.QUEUED)
        sender=self.procs[-1]
        self.assertEqual(sender.args[0][1:3],['-c',runner.SEND_LERKENDAL])
        self.assertEqual(sender.args[0][3],str(res))

    def test_timeout_stops_hung_scan(self):
        self.ctrl.start(self.job,force=True)
        later=datetime.now(timezone.utc)+timedelta(minutes=31)
        with mock.patch('app.runner._kill_tree',side_effect=lambda p:setattr(p,'code',1)):
            self.ctrl.poll(later);self.ctrl.poll(later)
        self.assertEqual(self.store.state(KEY)['last_status'],runner.TIMEOUT)

    def test_koteng_and_lerkendal_run_side_by_side(self):
        k=self.base/'koteng';k.mkdir()
        for n in ('hourly_koteng.py','koteng_scanner.py','profile_lock.py','koteng_profile.json','ankerpunkter_koteng.json','sync_koteng.py'):
            (k/n).write_text('stub',encoding='utf-8')
        kj=Job('6aaceecebfe408c38e1712dd','Rosenborg – Røa','RBK Kvinner','koteng_arena','https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd',
               (datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'koteng_v24',str(k))
        self.store.put_job(kj)
        self.ctrl.enable(KEY,True);self.ctrl.enable(kj.key,True);self.ctrl.poll()
        self.assertEqual({a.job.profile for a in self.ctrl.active.values()},{'koteng_v24','lerkendal_v23'})

# Minimal fake engine: exercises exactly the hooks the wrapper must control.
STUBS={
'hurtigkart.py':'''
import json,sys,builtins
from pathlib import Path
def panel_install(page):return True
def main():
    a=sys.argv;url=a[a.index('--url')+1];assert a[a.index('--port')+1]!='9222'
    builtins.input('Trykk ENTER')
    panel_install(type('P',(),{'url':PAGE_URL})())
    import sync_ministaut
    try:
        sync_ministaut.upload('x');raise SystemExit(9)
    except RuntimeError:pass
    out=Path('output/run1');out.mkdir(parents=True)
    (out/'resultat.json').write_text(json.dumps({'url':url,'time_utc':'2026-10-27T15:00:00+00:00',
      'free_confirmed_fields':FREE,'captured_fields':60,'locked_fields':[]}),encoding='utf-8')
    return 0
''',
'sync_ministaut.py':'def upload(p):raise AssertionError("real upload called")\n',
'publication.py':'''
def event_key(url):return url.rstrip('/').rsplit('/',1)[1]
def validate_complete(r):
    ok=r['free_confirmed_fields']>=0
    return ok,'' if ok else 'Ikke full kontroll over 60 felt'
''',
'verified_navigation.py':'''
from publication import event_key
def verify_event(page,dest):
    if event_key(page.url)!=event_key(dest):raise RuntimeError('Feil kamp i Edge')
''',
}

class WrapperTests(unittest.TestCase):
    def run_wrapper(self,free=4321,page_url=URL):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);d=Path(t.name)
        for name,src in STUBS.items():
            src=src.replace('PAGE_URL',repr(page_url)).replace('FREE',str(free))
            (d/name).write_text(textwrap.dedent(src),encoding='utf-8')
        rep=d/'rapport.json'
        p=subprocess.run([sys.executable,str(ROOT/'engines'/'lerkendal_once.py'),'--url',URL,'--port','9231',
                          '--report',str(rep),'--map-wait','0'],cwd=d,capture_output=True,text=True,timeout=60)
        return p,(json.loads(rep.read_text(encoding='utf-8')) if rep.exists() else None)

    def test_accepted(self):
        p,rep=self.run_wrapper()
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        self.assertTrue(rep['accepted']);self.assertEqual(rep['available_seated'],4321);self.assertEqual(rep['event_key'],KEY)

    def test_quality_rejected(self):
        p,rep=self.run_wrapper(free=-1)
        self.assertEqual(p.returncode,4,p.stderr);self.assertFalse(rep['accepted']);self.assertIn('60 felt',rep['reason'])

    def test_wrong_event_in_edge_stops(self):
        p,rep=self.run_wrapper(page_url='https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3')
        self.assertEqual(p.returncode,2);self.assertIsNone(rep)

    def test_refuses_production_port(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'hurtigkart.py').write_text('def main():return 0\n',encoding='utf-8')
            for name in ('sync_ministaut.py','publication.py','verified_navigation.py'):
                (Path(d)/name).write_text(textwrap.dedent(STUBS[name]),encoding='utf-8')
            p=subprocess.run([sys.executable,str(ROOT/'engines'/'lerkendal_once.py'),'--url',URL,'--port','9222',
                              '--report','x.json'],capture_output=True,text=True,timeout=60,cwd=d)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('9222',p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
