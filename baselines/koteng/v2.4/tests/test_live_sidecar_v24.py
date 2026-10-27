"""Test V2.4 installation and secure Koteng-only live sender; offline only."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import sync_koteng
import preflight_v24

class LiveSidecarV24(unittest.TestCase):
    def setUp(self):
        self.reference=json.loads((ROOT/'reference/approved_reference_diagnostic.json').read_text(encoding='utf-8'))
    def test_all_required_first_run_files_present(self):
        for name in ('01_INSTALLER.bat','02_TEST_EN_GANG.bat','03_KONFIGURER_TOKEN.bat',
                     '04_START_LIVE_TIMEVIS.bat','installer_v24.ps1','sett_token_v24.ps1',
                     'koteng_profile.json','ankerpunkter_koteng.json','sync_koteng.py',
                     'hourly_koteng.py','requirements_v24.txt'):
            self.assertTrue((ROOT/name).is_file(),name)
    def test_locked_profile_passes(self):
        self.assertTrue(preflight_v24.check(check_deps=False))
        self.assertEqual(sync_koteng.verify_local_lock(),
                         json.loads((ROOT/'koteng_profile.json').read_text())['local_profile_lock']['sha256'])
    def test_archived_unlocked_diagnostic_never_published(self):
        with self.assertRaisesRegex(ValueError,'Feil arrangement'):
            sync_koteng.build_payload(ROOT/'reference/approved_reference_diagnostic.json')
    def test_local_verified_diagnostic_can_be_encoded_without_network(self):
        d=copy.deepcopy(self.reference)
        d['profile_version']=sync_koteng.VERSION
        d['profile_lock']={'state':'LOCKED','digest_sha256':sync_koteng.verify_local_lock()}
        d['validation']['quality_status']='LOCKED_LOCAL_VERIFIED'
        d['validation']['local_seated_coverage_verified']=True
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'diagnostikk.json'
            p.write_text(json.dumps(d),encoding='utf-8')
            payload=sync_koteng.build_payload(p)
            self.assertEqual(payload['available_seated'],424)
            self.assertEqual(payload['reading_status'],'pending')  # API verifies and publishes as observed.
            self.assertEqual(len(payload['sections']),6)
            self.assertEqual({r['section'] for r in payload['sections']},set(sync_koteng.SECTIONS))
    def test_unverified_diagnostic_rejected(self):
        d=copy.deepcopy(self.reference)
        d['profile_version']=sync_koteng.VERSION
        d['profile_lock']={'state':'LOCKED','digest_sha256':sync_koteng.verify_local_lock()}
        d['validation']['quality_status']='NEEDS_REVIEW'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'diagnostikk.json'
            p.write_text(json.dumps(d),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'kvalitetsgodkjent'):
                sync_koteng.build_payload(p)
    def test_token_not_bundled(self):
        self.assertFalse((ROOT/'.ministaut-token').exists())
        self.assertFalse(list(ROOT.glob('*.env')))

if __name__=='__main__':unittest.main()
