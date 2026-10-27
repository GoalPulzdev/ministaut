import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koteng_scanner import (Observation, event_key, parse_tooltip, validate,
                            browser_viewport, region_is_visible, choose_map_candidate)

class TestKoteng(unittest.TestCase):
    def setUp(self):
        self.profile=json.loads((Path(__file__).resolve().parents[1]/'koteng_profile.json').read_text())
        self.profile['active_url']=self.profile['event_configs']['6aaceecebfe408c38e1712dd']['checkout_url']
        self.pass1={s:Observation(s,0,c) for s,c in self.profile['reference_sections'].items()}
    def test_known_formats(self):
        self.assertEqual(parse_tooltip('FELT-2 Free Seats: 125/160'),Observation('FELT-2',125,160))
        self.assertEqual(parse_tooltip('VIP Ledige seter: 49 av 71'),Observation('VIP',49,71))
        self.assertEqual(parse_tooltip('Felt 4 Tilgjengelige plasser: 138 / 152'),Observation('FELT-4',138,152))
    def test_bad_counts(self):
        self.assertIsNone(parse_tooltip('Felt 3 Free Seats 500/120'))
        self.assertIsNone(parse_tooltip('Free Seats 48/49'))
    def test_bad_event(self):
        with self.assertRaises(ValueError):event_key('https://example.com/checkout/foo')
    def test_training_not_complete(self):
        r=validate(self.profile,[self.pass1,self.pass1])
        self.assertEqual(r['counted_sections'],6)
        self.assertFalse(r['complete'])
        self.assertFalse(r['publishable'])
        self.assertEqual(r['observed_available_in_verified_fields'],0)
    def test_missing_not_zero(self):
        p=self.pass1.copy();p.pop('FELT-5')
        r=validate(self.profile,[self.pass1,p])
        self.assertIn('FELT-5',r['missing_sections'])
        self.assertEqual(r['counted_sections'],5)
    def test_mismatched_capacity_blocks(self):
        p=self.pass1.copy();p['VIP']=Observation('VIP',0,72)
        r=validate(self.profile,[self.pass1,p])
        self.assertIn('VIP',r['conflicts'])
    def test_locked_requires_confirmation(self):
        p=copy.deepcopy(self.profile)
        p['event_configs']['6aaceecebfe408c38e1712dd']['locked_sections']=['FELT-5']
        r=validate(p,[self.pass1,self.pass1])
        self.assertTrue(any('bekreftelse' in x for x in r['errors']))
    def test_real_viewport_when_playwright_viewport_is_none(self):
        class EdgePage:
            viewport_size = None
            def evaluate(self, code):
                return {"width": 1475, "height": 835}
        self.assertEqual(browser_viewport(EdgePage()), (1475, 835))

    def test_map_must_fit_actual_visible_height(self):
        self.assertFalse(region_is_visible([145,555,1209,1100], (1600,900)))
        self.assertTrue(region_is_visible([221,411,820,855], (1500,900)))

    def test_select_seating_not_sidebar(self):
        regions=[{"rect":[1400,100,1550,800],"area":105000,"tag":"svg"},
                 {"rect":[200,200,700,700],"area":250000,"tag":"canvas"}]
        self.assertEqual(choose_map_candidate(regions,(1600,900))["tag"], "canvas")

    def test_unexpected_field_blocks(self):
        p=self.pass1.copy();p['FELT-6']=Observation('FELT-6',10,20)
        r=validate(self.profile,[p,p])
        self.assertIn('FELT-6',r['unknown_sections'])

if __name__=='__main__':unittest.main()
