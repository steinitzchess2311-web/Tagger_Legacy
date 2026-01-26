"""
Tests for codex_utils helpers.

Verifies that analyze_position exposes new pipeline tag flags when
engine_meta.tag_flags_v8 is absent (e.g., for Knight-Bishop Exchange).
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from codex_utils import analyze_position
from tests.fixtures.mock_engine import MockEngine


class TestCodexUtils(unittest.TestCase):
    """codex_utils helper tests."""

    def setUp(self):
        self.mock_engine = MockEngine()
        self.mock_context = MagicMock()
        self.mock_context.__enter__.return_value = self.mock_engine
        self.mock_context.__exit__.return_value = None

        # Ensure new pipeline path is exercised
        os.environ["NEW_PIPELINE"] = "1"
        os.environ["CONTROL_ENABLED"] = "0"

    def test_analyze_position_exposes_kbe_tags(self):
        """KBE tags should surface via analyze_position.active tags."""
        fen = "r1b2rk1/p5b1/q1p2npp/1p1pNp2/3Pn3/1PN3P1/PQ1BPPBP/2R2RK1 b - - 3 17"
        move = "e4d2"  # Accurate knight-bishop exchange

        with patch("chess.engine.SimpleEngine.popen_uci", return_value=self.mock_context):
            analysis = analyze_position(fen, move, engine_path="/mock", use_new=True)

        active_tags = analysis["tags"]["active"]
        self.assertIn("accurate_knight_bishop_exchange", active_tags)
        self.assertTrue(
            analysis["tags"]["all"].get("accurate_knight_bishop_exchange"),
            "Tag flag should be present when detector fires",
        )

    def test_primary_lists_include_kbe_tags(self):
        """Primary/secondary tag lists should include new detector tags."""
        fen = "r1b2rk1/p5b1/q1p2npp/1p1pNp2/3Pn3/1PN3P1/PQ1BPPBP/2R2RK1 b - - 3 17"
        move = "e4d2"

        with patch("chess.engine.SimpleEngine.popen_uci", return_value=self.mock_context):
            analysis = analyze_position(fen, move, engine_path="/mock", use_new=True)

        self.assertIn(
            "accurate_knight_bishop_exchange",
            analysis["tags"]["primary"],
            "Primary tag list should keep new detector tags",
        )
        self.assertIn(
            "accurate_knight_bishop_exchange",
            analysis["tags"]["secondary"],
            "Secondary tag list should keep new detector tags",
        )


if __name__ == "__main__":
    unittest.main()
