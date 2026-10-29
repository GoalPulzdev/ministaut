from __future__ import annotations
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT=Path(__file__).resolve().parents[1]
WRAPPER=ROOT/'engines'/'koteng_once.py'
ROA='6aaceecebfe408c38e1712dd'
BRO='6ac390963b28cba4d656278f'

# Minimal fake Koteng engine: records which profile/event the lock check saw.
STUBS={
'koteng_scanner.py':'''
import re,json,sys
from urllib.parse import urlparse
from profile_lock import load_verified_lock
def event_key(url):return re.fullmatch(r"/checkout/([a-zA-Z0-9_-]{8,100})/?",urlparse(url).path).group(1)
def main(argv=None):
    a=argv;url=a[a.index('--url')+1];prof=json.load(open(a[a.index('--profile')+1],encoding='utf-8'))
    key=event_key(url);assert key in prof['event_configs']
    _,digest=load_verified_lock(prof,__import__('pathlib').Path('ankerpunkter_koteng.json').resolve(),key)
    import pathlib;out=pathlib.Path(a[a.index('--output')+1])/key/'run1';out.mkdir(parents=True)
    (out/'diagnostikk.json').write_text(json.dumps({'event_key':key,'digest':digest}),encoding='utf-8')
    return 0
''',
'profile_lock.py':'''
import json
CALLS=[]
def load_verified_lock(profile,anchor_path,event):
    CALLS.append(event)
    if profile['local_profile_lock']['event_key']!=event:raise ValueError('lock is for another event')
    if profile.get('reference_sections')!={'VIP':71}:raise ValueError('geometry changed')
    return {},'sha-ok'
''',
'sync_koteng.py':'''
import json
from pathlib import Path
from profile_lock import load_verified_lock
EVENT='6aaceecebfe408c38e1712dd'
def build_payload(path):
    prof=json.loads(Path('koteng_profile.json').read_text(encoding='utf-8'))
    _,digest=load_verified_lock(prof,Path('ankerpunkter_koteng.json'),EVENT)
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if d['event_key']!=EVENT or d['digest']!=digest:raise ValueError('wrong event or digest')
    return {'available_seated':316,'observed_at':'2026-10-27T15:00:00+00:00','source_run_id':'r'*40,'event_key':EVENT}
''',
}

class KotengMultiTests(unittest.TestCase):
    def engine(self,registry=None,sections=None):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);d=Path(t.name)
        for n,src in STUBS.items():(d/n).write_text(textwrap.dedent(src),encoding='utf-8')
        (d/'ankerpunkter_koteng.json').write_text('{}',encoding='utf-8')
        (d/'koteng_profile.json').write_text(json.dumps({'venue_id':'koteng_arena','profile_version':'v1.8',
            'reference_sections':sections or {'VIP':71},'standing_sections':[],'map_full_coverage_verified':True,
            'local_profile_lock':{'event_key':ROA,'state':'LOCKED'},'event_configs':{ROA:{'locked_sections':[]}}}),encoding='utf-8')
        if registry is not None:(d/'godkjente_kamper.json').write_text(json.dumps(registry),encoding='utf-8')
        return d

    def run_wrapper(self,d,key):
        rep=d/'rapport.json'
        p=subprocess.run([sys.executable,str(WRAPPER),'--url','https://billett.rbk.no/checkout/'+key,'--report',str(rep)],
                         cwd=d,capture_output=True,text=True,timeout=60)
        return p,(json.loads(rep.read_text(encoding='utf-8')) if rep.exists() else None)

    def test_unapproved_match_refused(self):
        p,rep=self.run_wrapper(self.engine(registry={}),BRO)
        self.assertNotEqual(p.returncode,0);self.assertIn('ikke godkjent',p.stdout+p.stderr);self.assertIsNone(rep)

    def test_approved_match_uses_sealed_stadium_lock(self):
        d=self.engine(registry={BRO:{'venue_id':'koteng_arena'}})
        p,rep=self.run_wrapper(d,BRO)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertTrue(rep['accepted']);self.assertEqual(rep['event_key'],BRO);self.assertEqual(rep['available_seated'],316)

    def test_original_match_needs_no_registry(self):
        p,rep=self.run_wrapper(self.engine(registry=None),ROA)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertTrue(rep['accepted'])

    def test_changed_stadium_geometry_blocks_every_match(self):
        d=self.engine(registry={BRO:{'venue_id':'koteng_arena'}},sections={'VIP':70})
        p,rep=self.run_wrapper(d,BRO)
        self.assertNotEqual(p.returncode,0);self.assertFalse(rep and rep.get('accepted'))

if __name__=='__main__':unittest.main()
