"""Regression tests for locked Koteng V1.8, not Lerkendal."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_lock import load_verified_lock, verify_profile_lock
from koteng_scanner import Observation, validate, run
from anchor_training import mapped_points

ROOT=Path(__file__).resolve().parents[1]
KEY='6aaceecebfe408c38e1712dd'

class LockedKotengProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=json.loads((ROOT/'koteng_profile.json').read_text('utf-8'))
        cls.anchors=json.loads((ROOT/'ankerpunkter_koteng.json').read_text('utf-8'))
        cls.latest=json.loads((ROOT/'reference/approved_reference_diagnostic.json').read_text('utf-8'))
    def test_lock_integrity_and_real_reference(self):
        self.assertEqual(verify_profile_lock(self.profile,self.anchors,KEY),
                         self.profile['local_profile_lock']['sha256'])
        self.assertEqual(self.latest['validation']['counted_sections'],6)
        self.assertEqual(self.latest['validation']['errors'],[])
        self.assertEqual(self.latest['validation']['observed_available_in_verified_fields'],424)
        self.assertEqual(len(self.latest['observations_by_pass']),2)
        self.assertEqual(self.profile['reference_snapshot']['available_seated_observed'],424)
        for section, capacity in self.profile['reference_sections'].items():
            expected=self.latest['validation']['sections'][section]['free']
            self.assertEqual(expected,self.profile['reference_snapshot']['observed_by_section'][section])
            for observations in self.latest['observations_by_pass']:
                self.assertEqual(observations[section]['free'],expected)
                self.assertEqual(observations[section]['capacity'],capacity)
    def test_verified_points_match_diagnostic(self):
        points=mapped_points(self.anchors,self.profile['reference_sections'],(1294,642),
                             [0,201.6,863.3,577.8],0.9)
        self.assertEqual({k:list(v[0]) for k,v in points.items()},
                         self.latest['two_pass_anchor_candidates'])
    def test_any_changed_coordinate_fails(self):
        changed=copy.deepcopy(self.anchors)
        changed['points']['FELT-1'][0][0]+=.001
        with self.assertRaisesRegex(ValueError,'Låst seksjonsprofil'):
            verify_profile_lock(self.profile,changed,KEY)
    def test_capacity_change_fails(self):
        p=copy.deepcopy(self.profile)
        p['reference_sections']['VIP']=72
        with self.assertRaisesRegex(ValueError,'Låst seksjonsprofil'):
            verify_profile_lock(p,self.anchors,KEY)
    def test_lock_protects_ref_snapshot_and_locked_field_configuration(self):
        for mode in ('snapshot', 'field'):
            p = copy.deepcopy(self.profile)
            if mode == 'snapshot':
                p['reference_snapshot']['available_seated_observed'] = 425
            else:
                p['event_configs'][KEY]['locked_sections'] = ['FELT-5']
            with self.assertRaisesRegex(ValueError, 'Låst seksjonsprofil'):
                verify_profile_lock(p, self.anchors, KEY)

    def test_wrong_event_fails(self):
        with self.assertRaises(ValueError):
            verify_profile_lock(self.profile,self.anchors,'some-other-event')
    def test_geometry_change_fails(self):
        with self.assertRaisesRegex(ValueError,'endret størrelse'):
            mapped_points(self.anchors,self.profile['reference_sections'],(1200,642),
                          [0,201.6,863.3,577.8],0.9)
    def test_publication_flags_stay_off(self):
        self.assertFalse(self.profile['public_export_enabled'])
        self.assertFalse(self.profile['approved'])
        self.assertFalse(self.profile['map_full_coverage_verified'])
        self.assertEqual(set(self.profile['standing_sections']),{'STAAPLASS_A','STAAPLASS_B'})
        self.assertEqual(self.profile['event_configs'][KEY]['locked_sections'],[])
        self.assertEqual(self.profile['event_configs'][KEY]['selected_ticket_category'],'ukjent')
    def test_locked_local_quality_not_publishable(self):
        p=copy.deepcopy(self.profile)
        p['active_url']=p['event_configs'][KEY]['checkout_url']
        observations=[{s:Observation(s,rows[s]['free'],rows[s]['capacity'])
                       for s in p['reference_sections']}
                      for rows in self.latest['observations_by_pass']]
        valid=validate(p,observations,lock_integrity_verified=True)
        self.assertEqual(valid['quality_status'],'LOCKED_LOCAL_VERIFIED')
        self.assertTrue(valid['local_seated_coverage_verified'])
        self.assertFalse(valid['publishable'])
        self.assertFalse(valid['complete'])
        self.assertEqual(valid['observed_available_in_verified_fields'],424)
        # Calling validate without verified lock never claims locked status.
        self.assertEqual(validate(p,observations)['quality_status'],'NEEDS_REVIEW')
    def test_automatic_retraining_is_rejected_before_edge(self):
        args=SimpleNamespace(profile=str(ROOT/'koteng_profile.json'),
                             url=self.profile['event_configs'][KEY]['checkout_url'],
                             teach=True,region=None,anchors=str(ROOT/'ankerpunkter_koteng.json'))
        with self.assertRaisesRegex(ValueError,'LÅST'):
            run(args)
    def test_missing_anchor_fails_before_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'mangler'):
                load_verified_lock(self.profile,Path(tmp)/'mangler.json',KEY)

if __name__=='__main__':unittest.main()
