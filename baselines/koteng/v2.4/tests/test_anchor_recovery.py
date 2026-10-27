import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from anchor_scan import scan_anchor_pass
from koteng_scanner import Observation

class FakePage:
    def __init__(self, mapping, sticky=False, extras=False):
        self.mapping=mapping;self.position=(0,0);self.current=[]
        self.sticky=sticky;self.extras=extras
        self.mouse=self
    def move(self,x,y):
        self.position=(x,y)
        if (x,y) in self.mapping:
            self.current=[self.mapping[(x,y)]]
        elif not self.sticky:
            self.current=[]
    def wait_for_timeout(self,ms): pass

def observations(page):
    if page.extras and page.current:
        return page.current+[Observation('VIP',45,71)] if page.current[0].section!='VIP' else page.current
    return page.current

class TestAnchorRecovery(unittest.TestCase):
    def setUp(self):
        self.cap={'FELT-1':49,'FELT-2':160,'VIP':71}
        self.points={'FELT-1':[(70,200)],'FELT-2':[(170,200)],'VIP':[(250,200)]}
        self.map={(70,200):Observation('FELT-1',48,49),
                  (170,200):Observation('FELT-2',125,160),
                  (250,200):Observation('VIP',45,71)}
    def test_each_field_independent_from_bad_prime(self):
        p=FakePage(self.map)
        a={**self.points,'FELT-1':[(10,280)]} # FELT-1 is invalid; others must still pass
        result,_,hit,checks=scan_anchor_pass(p,a,self.cap,180,observations,Observation)
        self.assertEqual(set(result),{'FELT-2','VIP'})
        self.assertEqual(hit,2)
        self.assertIn('target_not_visible',[r['result'] for r in checks])
    def test_two_passes_sticky_popup(self):
        p=FakePage(self.map,sticky=True)
        one,_,count_a,_=scan_anchor_pass(p,self.points,self.cap,180,observations,Observation)
        two,_,count_b,_=scan_anchor_pass(p,self.points,self.cap,180,observations,Observation)
        self.assertEqual((len(one),len(two),count_a,count_b),(3,3,3,3))
    def test_unrelated_stale_popup_does_not_drown_expected_field(self):
        p=FakePage(self.map,extras=True)
        one,_,hit,checks=scan_anchor_pass(p,self.points,self.cap,180,observations,Observation)
        self.assertEqual((len(one),hit),(3,3))
    def test_wrong_anchor_never_passes(self):
        p=FakePage({(70,200):Observation('FELT-2',125,160),
                    (170,200):Observation('FELT-1',48,49),
                    (250,200):Observation('VIP',45,71)})
        one,_,_,checks=scan_anchor_pass(p,self.points,self.cap,180,observations,Observation)
        self.assertEqual(set(one),{'VIP'})
        self.assertTrue(any(r['result']=='hovered_other_section' for r in checks))
    def test_permanent_popup_is_rejected(self):
        p=FakePage({},sticky=True)
        p.current=[Observation('VIP',45,71)]
        one,_,hit,checks=scan_anchor_pass(p,self.points,self.cap,180,observations,Observation)
        self.assertEqual((one,hit),({},0))
        self.assertTrue(any(r['result']=='stale_same_tooltip_at_neutral' or r['result']=='cannot_prove_popup_changed' for r in checks))

if __name__=='__main__':unittest.main()
