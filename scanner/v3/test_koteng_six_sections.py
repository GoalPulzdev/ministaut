"""Local Koteng six-section regression checks, with no browser launch."""
import tempfile
import unittest
from pathlib import Path
from .koteng_reference import EXPECTED_SEATED, TOTAL_SEATED, validate_koteng_profile
from .profiles import StadiumProfile
from .verify_koteng import V1_FIRST_TRAINING_REGION, position, profile_location


class SixSectionTests(unittest.TestCase):
    def complete_profile(self, version=1):
        system = "map_normalized" if version == 1 else "map_normalized_v2"
        return StadiumProfile(
            "koteng_arena", version, "vivenu", dict(EXPECTED_SEATED),
            {key: [{"ref": [0.2, 0.4], "coordinate_system": system}]
             for key in EXPECTED_SEATED},
            False,
        )

    def test_exact_six_and_601(self):
        self.assertEqual(set(EXPECTED_SEATED),
                         {"FELT-1", "FELT-2", "FELT-3",
                          "FELT-4", "FELT-5", "VIP"})
        self.assertEqual(TOTAL_SEATED, 601)
        self.assertEqual(sum((48, 125, 76, 138, 0, 49)), 436)
        self.assertNotIn("STÅPLASS A", EXPECTED_SEATED)

    def test_existing_profile_is_accepted_as_draft(self):
        p = self.complete_profile()
        self.assertIs(validate_koteng_profile(p), p)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v1.json"
            p.save(path)
            self.assertEqual(StadiumProfile.load(path), p)

    def test_missing_fields_or_changed_capacity_are_rejected(self):
        p = self.complete_profile()
        p.anchors.pop("VIP")
        with self.assertRaises(ValueError):
            validate_koteng_profile(p)
        p = self.complete_profile()
        p.sections["VIP"] = 72
        with self.assertRaises(ValueError):
            validate_koteng_profile(p)

    def test_first_run_normalized_coordinate_reconstruction(self):
        # First locally supplied report recorded this original training crop.
        x, y = position({"ref": [0.2, 0.4]}, V1_FIRST_TRAINING_REGION)
        self.assertEqual((x, y), (322, 634))


if __name__=="__main__":
    unittest.main()
