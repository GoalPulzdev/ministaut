"""V3 isolated tests, no network/Edge/database access required."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .control import ControlPlane, Event
from .profiles import StadiumProfile, validate_measurement, candidate_from_reference
from .gui import kickoff_iso

URL = "https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675"
NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def match(key="a", days=1, venue="lerkendal"):
    return Event(key, URL, venue, (NOW + timedelta(days=days)).isoformat(), "Test " + key,
                 state="monitoring")


class V3Tests(unittest.TestCase):
    def test_arbitrary_venue_and_fail_closed(self):
        stadium = StadiumProfile("koteng", 1, "vivenu", {"A": 100, "B": 60},
                                 {"A": [[2, 3]], "B": [{"ref": [5, 7]}]}, True)
        self.assertTrue(validate_measurement(stadium, {"A": 20, "B": 30})[0])
        for readings in ({"A": 20}, {"A": 20, "B": 61}, {"A": 20, "B": "30"},
                         {"A": 20, "B": 30, "C": 0}):
            self.assertFalse(validate_measurement(stadium, readings)[0])
        draft = StadiumProfile("koteng", 1, "vivenu", {"A": 100}, {"A": [[1, 2]]}, False)
        self.assertFalse(validate_measurement(draft, {"A": 12})[0])

    def test_legacy_anchors_import_as_unverified(self):
        root = Path(__file__).resolve().parents[1]
        profile = candidate_from_reference(root / "stadion_felt.json",
                                           root / "bekreftede_posisjoner_v16.json")
        self.assertEqual(len(profile.sections), 60)
        self.assertEqual(sum(profile.sections.values()), 19015)
        self.assertEqual(set(profile.sections), set(profile.anchors))
        self.assertFalse(profile.verified)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            profile.save(path)
            self.assertEqual(StadiumProfile.load(path), profile)

    def test_independent_queues_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            cp = ControlPlane(path)
            for i in range(3):
                cp.add(match(str(i), days=i+1))
            self.assertEqual(len(cp.tick(NOW)), 3)
            self.assertEqual(len(cp.tick(NOW)), 0)
            job = cp.claim("edge-worker", NOW)
            self.assertEqual(cp.finish(job.id, True, NOW+timedelta(minutes=1),
                                       worker_id="edge-worker"), "succeeded")
            cp = ControlPlane(path)
            # The other two fixtures still have queued work; do not double-queue.
            self.assertEqual(len(cp.tick(NOW+timedelta(minutes=61))), 1)
            cp.tick(NOW+timedelta(days=2))
            self.assertEqual(cp.events["0"].state, "completed")
            self.assertEqual(cp.events["1"].state, "completed")
            self.assertNotEqual(cp.events["2"].state, "completed")

    def test_pause_cancels_queued_without_affecting_other_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = ControlPlane(Path(tmp) / "state.json")
            cp.add(match("one"))
            cp.add(match("two"))
            jobs = cp.tick(NOW)
            self.assertEqual(len(jobs), 2)
            cp.set_state("one", "paused", now=NOW)
            self.assertEqual(sum(j.state=="cancelled" for j in jobs), 1)
            self.assertEqual(cp.claim("w", NOW).event_id, "two")

    def test_expired_lease_recovered_and_old_worker_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = ControlPlane(Path(tmp) / "state.json")
            cp.add(match("one"))
            [job] = cp.tick(NOW)
            cp.claim("worker-old", NOW, lease_minutes=1)
            again = cp.claim("worker-new", NOW + timedelta(minutes=2))
            self.assertEqual(again.id, job.id)
            self.assertEqual(again.attempts, 2)
            with self.assertRaises(ValueError):
                cp.finish(job.id, True, NOW+timedelta(minutes=3),
                          worker_id="worker-old")
            self.assertEqual(cp.finish(job.id, True, NOW+timedelta(minutes=3),
                                       worker_id="worker-new"), "succeeded")

    def test_no_late_publication_and_auto_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = ControlPlane(Path(tmp) / "state.json")
            cp.add(Event("one", URL, "lerkendal",
                         (NOW+timedelta(minutes=2)).isoformat(),
                         "Late job", state="monitoring"))
            [job] = cp.tick(NOW)
            cp.claim("w", NOW)
            self.assertEqual(cp.finish(job.id, True, NOW+timedelta(minutes=3)),
                             "cancelled")
            self.assertEqual(cp.events["one"].state, "completed")

    def test_norwegian_kickoff(self):
        self.assertEqual(kickoff_iso("28.11.2026 18:00"), "2026-11-28T18:00:00+01:00")
        with self.assertRaises(ValueError):
            kickoff_iso("25.10.2026 02:30")


if __name__=="__main__":
    unittest.main()
