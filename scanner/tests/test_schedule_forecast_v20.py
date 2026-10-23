"""V20: cadence, scope guards, chart and cautious kickoff projections."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest,json
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from analytics import forecast,scoped_records,kickoff_time,create_chart_html,save_chart
from schedule_control import ScanSchedule


def history(start='2026-11-24T09:00:00+00:00',count=5,locked=()):
    a=datetime.fromisoformat(start); out=[]
    for i in range(count):
        out.append({'event_key':'testevent','time_utc':(a+timedelta(hours=i*3)).isoformat(),
            'available_seated':5000-i*70,'locked_fields':list(locked),
            'standing_availability':'unknown','total':21423})
    return out

class CadenceTests(unittest.TestCase):
    def test_three_hour_timing(self):
        with tempfile.TemporaryDirectory() as d:
            s=ScanSchedule(Path(d)/'settings.json')
            self.assertTrue(s.enabled)
            s.scan_finished(now=100)
            self.assertFalse(s.due(10899))
            self.assertTrue(s.due(10900))
            s.scan_finished(now=10910)
            self.assertFalse(s.due(10911))
            self.assertTrue(s.due(21710))
    def test_toggle_saves_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'settings.json'
            s=ScanSchedule(p);s.scan_finished(now=10)
            s.enable(False,now=20)
            self.assertIsNone(s.seconds_remaining(now=30))
            self.assertFalse(ScanSchedule(p).enabled)
            s.enable(True,now=40)
            self.assertTrue(ScanSchedule(p).enabled)
            self.assertEqual(s.seconds_remaining(now=40),3*3600)
    def test_failed_scan_postpones_once(self):
        with tempfile.TemporaryDirectory() as d:
            s=ScanSchedule(Path(d)/'settings.json');s.scan_finished(now=0)
            s.postpone_after_error(now=11000,minutes=15)
            self.assertFalse(s.due(11899));self.assertTrue(s.due(11900))

class ForecastTests(unittest.TestCase):
    def test_oslo_kickoff_cet_dst(self):
        self.assertEqual(kickoff_time('28.11.2026 kl. 18:00'),datetime(2026,11,28,17,tzinfo=timezone.utc))
        self.assertEqual(kickoff_time('20.06.2027 kl. 18:00'),datetime(2027,6,20,16,tzinfo=timezone.utc))
    def test_at_least_four_over_six_hours(self):
        p=history(count=3)
        r=forecast(p,'28.11.2026 kl. 18:00');self.assertEqual(r['state'],'insufficient')
        p=history(count=4)
        r=forecast(p,'28.11.2026 kl. 18:00');self.assertEqual(r['state'],'estimate')
        self.assertLess(r['value'],p[-1]['available_seated']);self.assertLessEqual(r['low'],r['value']);self.assertGreaterEqual(r['high'],r['value'])
    def test_far_future_no_false_precision(self):
        p=history(start='2026-10-23T09:00:00+00:00',count=4)
        r=forecast(p,'28.11.2026 kl. 18:00');self.assertEqual(r['state'],'too_far');self.assertIsNone(r['value'])
    def test_scope_changes_filter(self):
        p=history(locked=('RB',))
        p+=history(start='2026-11-25T09:00:00+00:00',count=2,locked=('TB',))
        r=forecast(p,'28.11.2026 kl. 18:00',locked=('RB',))
        self.assertEqual(r['count'],5)
        self.assertEqual(scoped_records(p,locked=('TB',))[0]['free'],5000)
        self.assertEqual(forecast(p,'28.11.2026 kl. 18:00',locked=('TB',))['state'],'insufficient')
    def test_rejects_legacy_unscoped(self):
        p=history()
        p[0].pop('locked_fields');p[1].pop('standing_availability')
        self.assertEqual(len(scoped_records(p)),3)
    def test_post_kickoff_no_forecast(self):
        p=history(start='2026-12-01T09:00:00+00:00',count=4)
        self.assertEqual(forecast(p,'28.11.2026 kl. 18:00')['state'],'passed')
    def test_chart_has_actual_and_forecast(self):
        p=history()
        h=create_chart_html(p,'Rosenborg – Molde','28.11.2026 kl. 18:00','testevent')
        self.assertIn('5 sammenlignbare målinger',h)
        self.assertIn('Ledige',h)
        self.assertIn('Grovt scenario',h)
        self.assertIn('stroke-dasharray',h)
        with tempfile.TemporaryDirectory() as t:
            f=save_chart(Path(t),p,'Rosenborg – Molde','28.11.2026 kl. 18:00','testevent')
            self.assertTrue(f.exists());self.assertIn('<svg',f.read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()