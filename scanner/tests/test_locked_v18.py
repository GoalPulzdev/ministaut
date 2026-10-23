import copy
import json
import tempfile
import unittest
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from match_config import SEATS,normalize_locked,save_locked,load_locked,check_map_against_reference
from publication import (validate_complete,snapshot_from_result,publish,large_change,
                         compatible_previous,load_history)
ROOT=Path(__file__).resolve().parents[1]
URL='https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675'


def source():
    return json.loads((ROOT/'fixtures'/'complete_molde_v16.json').read_text(encoding='utf-8'))


def locked_result(names=('RB','TB')):
    d=source()
    original={x['section']:x for x in d['confirmed_fields']}
    assert all(original[n]['free']==0 for n in names)
    d['confirmed_fields']=[x for x in d['confirmed_fields'] if x['section'] not in names]
    d['locked_fields']=list(names)
    d['locked_fields_confirmed']=True
    d['map_structure_verified']=True
    d['captured_fields']=len(d['confirmed_fields'])
    d['covered_fields']=60
    d['capacity_verified_fields']=sum(x['capacity'] for x in d['confirmed_fields'])
    return d

class LockedFieldTests(unittest.TestCase):
    def test_fixed_capacity(self):
        self.assertEqual(len(SEATS),60)
        self.assertEqual(sum(SEATS.values()),19015)
        self.assertEqual(SEATS['RB'],530)
        self.assertEqual(SEATS['TB'],287)

    def test_58_read_and_2_confirmed_locks_is_complete(self):
        d=locked_result()
        self.assertTrue(validate_complete(d)[0],validate_complete(d)[1])
        snapshot=snapshot_from_result(d,'Rosenborg – Molde','28.11.2026 kl. 18:00')
        self.assertEqual(snapshot['available_seated'],6551)
        self.assertEqual(snapshot['estimated_sold'],21423-6551)
        self.assertEqual(snapshot['locked_fields'],['RB','TB'])
        self.assertEqual(snapshot['locked_capacity'],817)
        self.assertEqual(len(snapshot['section_free']),58)

    def test_missing_unapproved_section_is_not_imputed_zero(self):
        d=locked_result();d['confirmed_fields']=d['confirmed_fields'][:-1]
        d['captured_fields']=len(d['confirmed_fields']);d['covered_fields']=59
        self.assertFalse(validate_complete(d)[0])

    def test_locked_must_be_confirmed(self):
        d=locked_result();d['locked_fields_confirmed']=False
        self.assertFalse(validate_complete(d)[0])
        d=locked_result();d['map_structure_verified']=False
        self.assertFalse(validate_complete(d)[0])

    def test_cannot_read_and_lock_same_section(self):
        d=source();d['locked_fields']=['RB'];d['locked_fields_confirmed']=True
        d['map_structure_verified']=True
        self.assertFalse(validate_complete(d)[0])

    def test_false_duplicate_and_unknown_locks_rejected(self):
        for value in (['RB','RB'],['XZY'],['A','B','C']):
            with self.assertRaises(ValueError):normalize_locked(value)

    def test_live_map_may_hide_locked_sections_but_not_active(self):
        name_set=set(SEATS)-{'RB','TB'}
        cap={n:SEATS[n] for n in name_set}
        ok,problems=check_map_against_reference(name_set,cap,('RB','TB'))
        self.assertTrue(ok,problems)
        # A locked section may remain in the map even when its seat inventory
        # is unavailable or empty for this public checkout.
        ok,_=check_map_against_reference(name_set|{'RB','TB'},cap,('RB','TB'))
        self.assertTrue(ok)
        ok,_=check_map_against_reference(name_set-{'A'},cap,('RB','TB'))
        self.assertFalse(ok)
        cap['A']=SEATS['A']+1
        ok,_=check_map_against_reference(name_set,cap,('RB','TB'))
        self.assertFalse(ok)

    def test_confirmation_persist_per_event(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            with self.assertRaises(ValueError):save_locked(folder,URL,'RB',confirmed=False)
            save_locked(folder,URL,'RB,TB',confirmed=True)
            self.assertEqual(load_locked(folder,URL),('RB','TB'))
            self.assertEqual(load_locked(folder,URL.replace('6a9a7e3f3f93920b289b0675','6a9a7c2b15599587216e21f3')),())

    def test_new_locked_scope_resets_public_delta(self):
        one=source();one['time_utc']='2026-10-23T06:33:06+00:00'
        two=locked_result();two['time_utc']='2026-10-23T06:35:06+00:00'
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            p1=publish(one,folder/'first',folder/'history')
            p2=publish(two,folder/'second',folder/'history')
            self.assertTrue(p1['published'])
            self.assertTrue(p2['published'],p2['reason'])
            self.assertIsNone(p2['previous'])
            public=json.loads((folder/'second'/'deling_status.json').read_text(encoding='utf-8'))
            self.assertIsNone(public['delta_since_previous'])
            self.assertTrue(public['comparison_scope_changed'])

    def test_large_jump_blocks_publication_and_history_without_approval(self):
        first=source();second=copy.deepcopy(first)
        second['time_utc']='2026-10-23T07:33:06+00:00'
        for f in second['confirmed_fields']:
            if f['section'] in ('PA','QA'):
                old=f['free'];f['free']=f['capacity'];f['min_free']=f['free'];f['max_free']=f['free']
        second['free_confirmed_fields']=sum(f['free'] for f in second['confirmed_fields'])
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            p1=publish(first,root/'one',root/'history')
            p2=publish(second,root/'two',root/'history')
            self.assertTrue(p1['published'])
            self.assertFalse(p2['published'])
            self.assertTrue((root/'two'/'kvalitetsvarsel_v18.json').exists())
            self.assertEqual(len(load_history(root/'history',p1['record']['event_key'])),1)
            p3=publish(second,root/'two-approved',root/'history',approve_large_change=True)
            self.assertTrue(p3['published'])
            self.assertEqual(len(load_history(root/'history',p1['record']['event_key'])),2)

if __name__=='__main__':unittest.main()