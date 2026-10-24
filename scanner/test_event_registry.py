"""Regression tests for match lifecycle and Koteng isolation."""
import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from event_registry import EventRegistry
ROOT_URL='https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675'
KOTENG_URL='https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd'
class RegistryTests(unittest.TestCase):
    def test_lifecycle_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'monitor_kamper.json'
            reg=EventRegistry(path)
            reg.add(ROOT_URL,'Rosenborg – Molde')
            self.assertEqual(reg.status(reg.items[0]),'awaiting_kickoff')
            now=datetime(2026,10,24,12,0,tzinfo=timezone.utc)
            reg.update(reg.items[0]['key'],kickoff_at=(now+timedelta(hours=3)).isoformat())
            self.assertEqual(len(reg.eligible(now)),1)
            reloaded=EventRegistry(path)
            self.assertEqual(len(reloaded.eligible(now)),1)
            self.assertEqual(reloaded.status(reloaded.items[0],now+timedelta(hours=4)),'finished')
            self.assertEqual(reloaded.eligible(now+timedelta(hours=4)),[])
    def test_isolated_venue(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg=EventRegistry(Path(tmp)/'events.json')
            now=datetime(2026,10,24,12,0,tzinfo=timezone.utc)
            koteng=reg.add(KOTENG_URL,'RBK Kvinner','koteng_arena',kickoff_at=(now+timedelta(days=1)).isoformat())
            self.assertEqual(reg.status(koteng,now),'awaiting_map')
            self.assertEqual(reg.eligible(now),[])
            reg.add(KOTENG_URL)
            self.assertEqual(reg.get(koteng['key'])['venue'],'koteng_arena')
    def test_timezone_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg=EventRegistry(Path(tmp)/'events.json')
            with self.assertRaises(ValueError):
                reg.add(ROOT_URL,kickoff_at='2026-11-28T18:00:00')
if __name__=='__main__': unittest.main()
