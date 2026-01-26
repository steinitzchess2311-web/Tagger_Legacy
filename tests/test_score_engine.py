import unittest

from core.score_engine import collapse_failure_severity


class CollapseFailureSeverityTest(unittest.TestCase):
    def test_prefers_true_ratio_for_failed_direction(self) -> None:
        ratios = {
            "failed_direction_maneuver": 0.4,
            "failed_direction_maneuver.true": 0.1,
            "failed_direction_maneuver.temporary": 0.3,
        }
        collapsed = collapse_failure_severity(ratios)
        self.assertNotIn("failed_direction_maneuver.true", collapsed)
        self.assertAlmostEqual(0.1, collapsed["failed_direction_maneuver"])

    def test_non_failure_tags_are_preserved(self) -> None:
        ratios = {"latent_active_maneuver": 0.2}
        collapsed = collapse_failure_severity(ratios)
        self.assertEqual(ratios, collapsed)


if __name__ == "__main__":
    unittest.main()
