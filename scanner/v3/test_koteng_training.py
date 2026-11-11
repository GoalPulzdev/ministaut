"""Focused Koteng learner unit tests; not a replacement for a real Edge run."""
import unittest
from unittest.mock import patch
from .learn_koteng import (
    REFERENCE_SEAT_FIELDS, focused_koteng_region, even_sample,
    parse_training_tooltip,
)


class FakePage:
    viewport_size = {"width": 1600, "height": 960}


class KotengLearningTests(unittest.TestCase):
    def test_user_report_expected_labels(self):
        self.assertEqual(REFERENCE_SEAT_FIELDS,
                         {"VIP", "FELT-1", "FELT-2", "FELT-3", "FELT-4", "FELT-5"})

    def test_numbered_sector_readings(self):
        for text, section, free, cap in (
            ("Felt-1\nLedige seter 48/49", "FELT-1", 48, 49),
            ("Section VIP\nFree seats 49/71", "VIP", 49, 71),
            ("Felt-5\nLedige seter 0/49", "FELT-5", 0, 49),
            ("Seksjon FELT-3: tilgjengelige plasser 76 av 120",
             "FELT-3", 76, 120),
        ):
            obs = parse_training_tooltip(text, 42, 23)
            self.assertIsNotNone(obs, text)
            self.assertEqual((obs.section, obs.free, obs.capacity),
                             (section, free, cap))

    def test_standing_kept_separate(self):
        obs = parse_training_tooltip("Ståplass A\nLedige plasser 12/100", 500, 800)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.section, "STÅPLASS-A")
        self.assertEqual(obs.source, "standing-training")

    def test_misleading_or_incomplete_tooltip_rejected(self):
        for text in ("Felt 3", "Ledige plasser 12/100",
                     "Felt-1: Ledige seter 120/49"):
            self.assertIsNone(parse_training_tooltip(text, 0, 0))

    def test_crop_corrects_actual_report_overreach(self):
        with patch("v3.learn_koteng.choose_map_region",
                   return_value=((5, 423.75, 1590, 950), "svg/canvas")):
            region, source = focused_koteng_region(FakePage())
        self.assertEqual(region, (5, 268.8, 1064.0, 950))
        self.assertIn("koteng-left-column", source)

    def test_grid_sample_reaches_both_ends(self):
        items = list(range(2000))
        chosen = even_sample(items, 200)
        self.assertEqual((chosen[0], chosen[-1]), (0, 1999))
        self.assertEqual(len(chosen), 200)


if __name__ == "__main__":
    unittest.main()
