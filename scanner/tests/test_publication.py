import copy
import json
import tempfile
import unittest
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from publication import (TOTAL_PLACES,event_labels,parse_match_header,validate_complete,
    snapshot_from_result,store_snapshot,load_history,render_html,relative_interval,publish)

ORIGINAL=Path('/mnt/data/resultat(4).json')
ROOT=Path(__file__).resolve().parents[1]

def real_fixture():
    # Copy to tests/fixtures so ZIP works without previous chats.
    return json.loads((ROOT/'fixtures'/'complete_molde_v16.json').read_text(encoding='utf-8'))

class StatusTests(unittest.TestCase):
    def test_fixed_capacity_and_estimate(self):
        d=real_fixture()
        ok,msg=validate_complete(d)
        self.assertTrue(ok,msg)
        s=snapshot_from_result(d,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        self.assertEqual(s['total'],21423)
        self.assertEqual(s['available_seated'],6551)
        self.assertEqual(s['calculated_unavailable'],14872)

    def test_missing_field_prevents_public_post(self):
        d=real_fixture(); d['captured_fields']=59
        self.assertFalse(validate_complete(d)[0])
        with tempfile.TemporaryDirectory() as t:
            pub=publish(d,Path(t)/'out',Path(t)/'history')
            self.assertFalse(pub['published'])
            self.assertFalse((Path(t)/'history').exists())

    def test_conflict_prevents_public_post(self):
        d=real_fixture();d['conflicts']={'K':[{'free':17},{'free':18}]}
        self.assertFalse(validate_complete(d)[0])

    def test_capacity_change_prevents_public_post(self):
        d=real_fixture();d['capacity_verified_fields']=19014
        self.assertFalse(validate_complete(d)[0])

    def test_dedup_and_per_match_history(self):
        d=real_fixture()
        older=copy.deepcopy(d);older['time_utc']='2026-10-23T06:05:27+00:00'
        older['free_confirmed_fields']=6594
        older['confirmed_fields'][0]['free']=43
        # Capacity of field A is 94 and its free was 0, so this remains in range.
        older['confirmed_fields'][0]['min_free']=43
        older['confirmed_fields'][0]['max_free']=43
        a=snapshot_from_result(older,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        b=snapshot_from_result(d,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        with tempfile.TemporaryDirectory() as temp:
            history=Path(temp)
            records,previous=store_snapshot(history,a)
            self.assertIsNone(previous)
            records,previous=store_snapshot(history,b)
            self.assertEqual(previous['calculated_unavailable'],14829)
            self.assertEqual(b['calculated_unavailable']-previous['calculated_unavailable'],43)
            records,previous=store_snapshot(history,b)
            self.assertEqual(len(records),2)
            self.assertEqual(previous['calculated_unavailable'],14829)
            self.assertEqual(len(load_history(history,b['event_key'])),2)

    def test_dynamic_match_parser(self):
        label=parse_match_header('Rosenborg-Molde 28.11.2026 18:00\nVelg billetter')
        self.assertEqual(label,('Rosenborg – Molde','28.11.2026 kl. 18:00'))
        self.assertEqual(event_labels(real_fixture()['url'])[0],'Rosenborg – Molde')

    def test_public_html_has_no_scanner_metrics(self):
        d=real_fixture();s=snapshot_from_result(d,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        t=render_html(s,None,[s])
        self.assertIn('14 872',t)
        self.assertIn('6 551',t)
        self.assertIn('21 423',t)
        self.assertNotIn('felt registrert',t)
        self.assertNotIn('manuelle felt',t)
        self.assertIn('Ikke et offisielt salgstall',t)

    def test_first_history_has_no_false_delta(self):
        d=real_fixture();s=snapshot_from_result(d,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        html=render_html(s,None,[s])
        self.assertIn('Første komplette måling',html)
        self.assertEqual(relative_interval('2026-10-23T06:05:27+00:00',s['time_utc']),'28 min')

if __name__=='__main__':unittest.main()