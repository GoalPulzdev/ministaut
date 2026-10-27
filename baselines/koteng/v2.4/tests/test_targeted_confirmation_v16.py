"""Regression tests for a real-world Koteng pattern: 3/6 -> 6/6."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koteng_scanner import Observation, validate, sections_needing_recheck
from anchor_scan import scan_anchor_pass


class MockPage:
    def __init__(self, mapping):
        self.mapping = mapping
        self.current = []
        self.mouse = self
    def move(self, x, y):
        self.current = [self.mapping[(x, y)]] if (x,y) in self.mapping else []
    def wait_for_timeout(self, ms):
        pass


def read_current(page):
    return page.current


class TargetedConfirmation(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.profile = json.loads((root / 'koteng_profile.json').read_text(encoding='utf-8'))
        self.profile['active_url'] = self.profile['event_configs']['6aaceecebfe408c38e1712dd']['checkout_url']
        self.caps = self.profile['reference_sections']
        self.observed = {
            'VIP': 45, 'FELT-1': 48, 'FELT-2': 125,
            'FELT-3': 70, 'FELT-4': 136, 'FELT-5': 0
        }
        self.full = {section: Observation(section, self.observed[section], cap)
                     for section, cap in self.caps.items()}

    def test_partial_then_full_then_targeted_provides_two_confirmations(self):
        first = {k:v for k,v in self.full.items() if k in ('FELT-3','FELT-4','FELT-5')}
        second = self.full.copy()
        needed = sections_needing_recheck(self.profile, [first, second])
        self.assertEqual(needed, {'VIP','FELT-1','FELT-2'})
        intermediate = validate(self.profile,[first,second])
        self.assertEqual(intermediate['counted_sections'],3)
        self.assertEqual(intermediate['observed_available_in_verified_fields'],206)
        third = {name: self.full[name] for name in needed}
        final = validate(self.profile,[first,second,third])
        self.assertEqual(final['counted_sections'],6)
        self.assertEqual(final['observed_available_in_verified_fields'],424)
        self.assertEqual(final['missing_sections'],[])
        self.assertEqual(final['confirmation_count_by_section']['VIP'],2)
        self.assertFalse(final['public_approved'])
        self.assertFalse(final['publishable'])
        self.assertFalse(final['complete'])  # the stadium profile remains unverified
        self.assertEqual(sections_needing_recheck(self.profile,[first,second,third]),set())

    def test_single_late_success_still_does_not_count(self):
        first = {}
        second = {'VIP': self.full['VIP']}
        final = validate(self.profile,[first,second])
        self.assertIn('VIP',final['missing_sections'])
        self.assertNotIn('VIP',final['sections'])

    def test_conflict_between_two_separate_successes_remains_blocking(self):
        first = self.full.copy()
        second = self.full.copy()
        third = {'VIP':Observation('VIP',30,71)}
        result = validate(self.profile,[first,second,third])
        self.assertIn('VIP',result['conflicts'])
        self.assertNotIn('VIP',result['sections'])
        self.assertFalse(result['complete'])

    def test_after_recovery_scans_only_missing_fields(self):
        anchors = {name: [(i*90+70, 130)] for i, name in enumerate(self.caps)}
        mapping = {tuple(anchors[name][0]): obs for name, obs in self.full.items()}
        page = MockPage(mapping)
        target = {'VIP','FELT-1','FELT-2'}
        observations, _, _, diagnostics = scan_anchor_pass(
            page, anchors, self.caps, 150, read_current, Observation,
            viewport=(1000,700), scouts=False, only_sections=target)
        self.assertEqual(set(observations),target)
        self.assertEqual({x['field'] for x in diagnostics},target)

    def test_unrecognized_target_name_is_blocked(self):
        anchors = {'VIP':[(50,50)],'FELT-1':[(90,50)]}
        page = MockPage({})
        with self.assertRaises(ValueError):
            scan_anchor_pass(page,anchors,{'VIP':71,'FELT-1':49},150,read_current,
                             Observation,only_sections={'NOT_A_FIELD'})

    def test_even_after_recheck_one_success_is_not_enough(self):
        first = {'VIP':self.full['VIP']}
        second = {}
        third = {}
        fourth = {}
        result = validate(self.profile,[first,second,third,fourth])
        self.assertEqual(result['counted_sections'],0)
        self.assertIn('VIP',result['missing_sections'])

if __name__=='__main__':
    unittest.main()
