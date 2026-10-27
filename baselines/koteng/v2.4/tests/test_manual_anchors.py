import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from anchor_training import (build_anchor_document, mapped_points, save_anchor_document,
                             validate_picks)
from anchor_scan import scan_anchor_pass
from koteng_scanner import Observation, validate

ROOT=Path(__file__).resolve().parents[1]

class TestManualAnchors(unittest.TestCase):
    def setUp(self):
        self.profile=json.loads((ROOT/'koteng_profile.json').read_text())
        self.key='6aaceecebfe408c38e1712dd'
        self.profile['active_url']=self.profile['event_configs'][self.key]['checkout_url']
        self.sections=list(self.profile['reference_sections'])
        self.picks={name:[[100+60*i,220]] for i,name in enumerate(self.sections)}

    def test_roundtrip_file(self):
        doc=build_anchor_document(self.picks,self.profile,self.key,(1726,856),[0,250,1151,770.4],.9)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ankerpunkter_koteng.json'
            save_anchor_document(path,doc)
            loaded=json.loads(path.read_text())
            self.assertEqual(mapped_points(loaded,self.profile['reference_sections'],(1726,856),[0,250,1151,770.4],.9),
                             {k:[tuple(p) for p in v] for k,v in self.picks.items()})

    def test_geometry_changes_reject_without_wrong_scan(self):
        doc=build_anchor_document(self.picks,self.profile,self.key,(1726,856),[0,250,1151,770.4],.9)
        for viewport,region,zoom in [((1726,800),[0,250,1151,770.4],.9),
                                     ((1726,856),[0,230,1151,770.4],.9),
                                     ((1726,856),[0,250,1151,770.4],.8)]:
            with self.assertRaises(ValueError):mapped_points(doc,self.profile['reference_sections'],viewport,region,zoom)

    def test_missing_and_invalid_points_are_rejected(self):
        with self.assertRaises(ValueError):validate_picks({'VIP':[[200,220]]},self.profile['reference_sections'],(1726,856))
        bad=copy.deepcopy(self.picks);bad['VIP']=[[99999,5]]
        with self.assertRaises(ValueError):validate_picks(bad,self.profile['reference_sections'],(1726,856))

    def test_two_independent_passes(self):
        anchors={name:self.picks[name] for name in self.sections}
        bypoint={tuple(self.picks[name][0]):Observation(name, min(20,self.profile['reference_sections'][name]),self.profile['reference_sections'][name])
                 for name in self.sections}
        class Mouse:
            def move(self,x,y):page.current=(x,y)
        class Page:
            current=None
            mouse=Mouse()
            def wait_for_timeout(self,ms):pass
        page=Page()
        def read(page):return [bypoint[page.current]] if page.current in bypoint else []
        first,issues,hits,rejected=scan_anchor_pass(page,anchors,self.profile['reference_sections'],85,read,Observation)
        second,issues2,hits2,rejected2=scan_anchor_pass(page,anchors,self.profile['reference_sections'],85,read,Observation)
        self.assertEqual((len(first),len(second),hits,hits2),(6,6,6,6))
        self.assertFalse(issues or issues2)
        self.assertTrue(all(r["result"]=="confirmed" for r in rejected+rejected2))
        result=validate(self.profile,[first,second])
        self.assertEqual(result['counted_sections'],6)
        self.assertFalse(result['publishable'])

    def test_stale_tooltip_and_wrong_anchor_do_not_count(self):
        anchors={name:self.picks[name] for name in self.sections}
        class Mouse:
            def move(self,x,y):pass
        class Page:
            mouse=Mouse()
            def wait_for_timeout(self,ms):pass
        page=Page()
        # A stale VIP popup that never changes must NOT verify other points.
        def stale(_):return [Observation('VIP',45,71)]
        first,_,_,rejected=scan_anchor_pass(page,anchors,self.profile['reference_sections'],85,stale,Observation)
        self.assertEqual(first,{})
        self.assertTrue(rejected)

if __name__=='__main__':unittest.main()
