import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from anchor_scan import point_candidates, scan_anchor_pass
from koteng_scanner import Observation

class Dummy:
    def __init__(self,positions,sticky=False):
        self.positions=positions;self.current=[];self.sticky=sticky;self.mouse=self
    def move(self,x,y):
        if (x,y) in self.positions:self.current=[self.positions[(x,y)]]
        elif not self.sticky:self.current=[]
    def wait_for_timeout(self,ms):pass

def read(page):return page.current

class Recovery(unittest.TestCase):
    def test_offsets_and_hints_never_leave_viewport(self):
        p=point_candidates([(10,10)],(100,100),True,[(99,99)],40)
        self.assertTrue(all(0<=x<100 and 0<=y<100 for (x,y),_ in p))
        self.assertEqual(p[0][0],(10,10))
    def test_recovery_nearby_point(self):
        ref={'VIP':71,'FELT-1':49}
        anchors={'VIP':[(100,100)],'FELT-1':[(300,100)]}
        positions={(100,118):Observation('VIP',45,71),
                   (300,118):Observation('FELT-1',48,49)}
        page=Dummy(positions)
        p1,_,_,checks=scan_anchor_pass(page,anchors,ref,80,read,Observation,
                        viewport=(800,600),scouts=True)
        self.assertEqual(set(p1),set(ref))
        self.assertTrue(all(c['probe_count']>1 for c in checks))
        self.assertEqual(p1['VIP'].y,118)
        p2,_,_,_=scan_anchor_pass(page,anchors,ref,80,read,Observation,
                        viewport=(800,600),scouts=True,
                        preferred={n:[(p1[n].x,p1[n].y)] for n in p1})
        self.assertEqual(set(p2),set(ref))
    def test_never_accept_other_field_or_stale_label(self):
        ref={'VIP':71,'FELT-1':49}
        anchors={'VIP':[(100,100)],'FELT-1':[(300,100)]}
        page=Dummy({(100,118):Observation('FELT-1',48,49)})
        out,_,_,checks=scan_anchor_pass(page,anchors,ref,80,read,Observation,
                                viewport=(800,600),scouts=True)
        self.assertNotIn('VIP',out)
        self.assertIn('VIP',[c['field'] for c in checks])
        page2=Dummy({},sticky=True)
        page2.current=[Observation('VIP',45,71)]
        out2,_,_,_=scan_anchor_pass(page2,anchors,ref,80,read,Observation,
                                viewport=(800,600),scouts=True)
        self.assertEqual(out2,{})

if __name__=='__main__':unittest.main()
