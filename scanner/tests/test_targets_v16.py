import json,math,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from targets_v16 import confirmed_load,field_bases,field_candidates,record_verified,round_robin_recovery
from pitch_locator import Pitch,to_screen
from hurtigkart import CONFIRMED_POINTS,KNOWN,OLD

ROOT=Path(__file__).resolve().parents[1]

class ProvenTargetsTests(unittest.TestCase):
    def setUp(self):
        self.pitch=Pitch(319.4,409.7,201.4,130.5)

    def test_sixty_sections(self):
        self.assertEqual(set(CONFIRMED_POINTS),set(KNOWN))
        self.assertEqual(len(CONFIRMED_POINTS),60)

    def test_manual_points_bundled_for_both_matches(self):
        for name in ('A','HB','N','TB','GB','RB','SA','TA'):
            self.assertTrue(any(row['source']=='manual' for row in CONFIRMED_POINTS[name]),name)

    def test_alt_points_preserved_for_moved_field(self):
        for name in ('A','GB','RB','SA','TA'):
            self.assertGreaterEqual(len(CONFIRMED_POINTS[name]),2,name)

    def test_convert_rbk_coordinates(self):
        goals={'RB':(318,418),'GB':(531,551),'SA':(329,367),'TA':(284,412)}
        for name,(x,y) in goals.items():
            pair=CONFIRMED_POINTS[name][0]['ref']
            self.assertLessEqual(math.dist(to_screen(pair,self.pitch),(x,y)),1.5,name)

    def test_first_and_recovery_distinct(self):
        options=field_candidates('RB',self.pitch,{}, {},CONFIRMED_POINTS,{},KNOWN,OLD)
        self.assertGreater(len(options),2)
        first=(options[0][1],options[0][2])
        steps=list(round_robin_recovery({'RB':options},{'RB':{first}},per_field_limit=5))
        self.assertEqual(len(steps),5)
        self.assertNotIn(first,[(v[1],v[2]) for v in steps])
        self.assertEqual(len(set((v[1],v[2]) for v in steps)),5)

    def test_legacy_manual_wins_over_bundled(self):
        target=(400,260)
        opts=field_candidates('RB',self.pitch,{'RB':target},{},CONFIRMED_POINTS,{},KNOWN,OLD)
        self.assertEqual(opts[0][0],'manuell_v15')
        self.assertEqual(opts[0][1:],to_screen(target,self.pitch))

    def test_recent_verified_wins_over_static(self):
        opts=field_candidates('GB',self.pitch,{}, {'GB':[{'ref':[570,490],'source':'automatic'}]},
                              CONFIRMED_POINTS,{},KNOWN,OLD)
        self.assertEqual(opts[0][0],'bekreftet_v16')

    def test_invalid_seed_load_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json';p.write_text('{"fields":{"A":[{"ref":[1]},{"ref":[2,3]}]}}')
            self.assertEqual(len(confirmed_load(p)['A']),1)
            p.write_text('[')
            self.assertEqual(confirmed_load(p),{})

    def test_feedback_round_trip_and_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'recent.json';points={}
            self.assertTrue(record_verified(p,points,'GB',(500,500),self.pitch,'automatic'))
            self.assertTrue(record_verified(p,points,'GB',(500,500),self.pitch,'automatic'))
            self.assertEqual(len(confirmed_load(p)['GB']),1)
            self.assertNotIn('free',p.read_text())
            self.assertNotIn('checkout',p.read_text())

    def test_round_robin_order(self):
        plans={'GB':[('a',10,10),('b',11,11)],'RB':[('x',20,20),('y',21,21)]}
        schedule=list(round_robin_recovery(plans,{},per_field_limit=2))
        self.assertEqual([x[0] for x in schedule],['GB','RB','GB','RB'])
        self.assertEqual(schedule[2][1:3],(11,11))

    def test_no_seat_counts_in_bundle(self):
        content=(ROOT/'bekreftede_posisjoner_v16.json').read_text(encoding='utf-8')
        self.assertNotIn('free_seats',content)
        self.assertNotIn('checkout/',content)

if __name__=='__main__':unittest.main()