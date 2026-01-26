#!/usr/bin/env python3
"""
Integration test for Knight-Bishop Exchange detector in new pipeline.

Tests that KBE detector is properly integrated and produces expected tags
and diagnostic information when run through the complete pipeline.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

import chess

from rule_tagger2.core.facade import tag_position
from tests.fixtures.mock_engine import MockEngine


class TestKnightBishopExchangeIntegration(unittest.TestCase):
    """Integration tests for KBE detector in full pipeline"""

    def setUp(self):
        """Set up test environment"""
        # Use mock engine by default (CI-friendly, deterministic)
        self.use_mock = os.environ.get("USE_REAL_ENGINE", "0") == "0"

        if self.use_mock:
            # Mock engine: deterministic, no external dependencies
            self.engine_path = "/mock/engine/path"
            self.mock_engine = MockEngine()
        else:
            # Real engine: for manual verification
            self.engine_path = os.environ.get("ENGINE", "/usr/local/bin/stockfish")
            if not os.path.exists(self.engine_path):
                self.skipTest(f"Real engine not found at {self.engine_path}. Set ENGINE env var.")
            self.mock_engine = None

        # Ensure new pipeline is enabled
        os.environ["NEW_PIPELINE"] = "1"
        os.environ["CONTROL_ENABLED"] = "0"  # Disable control flow interference

    def _tag_position_with_mock(self, fen: str, move_uci: str, **kwargs):
        """
        Call tag_position with mock engine if enabled.

        Uses unittest.mock.patch to replace SimpleEngine.popen_uci with MockEngine.
        """
        if self.use_mock:
            # Patch all SimpleEngine.popen_uci calls to return mock engine context manager
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=self.mock_engine)
            mock_context.__exit__ = MagicMock(return_value=None)

            with patch('chess.engine.SimpleEngine.popen_uci', return_value=mock_context):
                return tag_position(
                    engine_path=self.engine_path,
                    fen=fen,
                    played_move_uci=move_uci,
                    use_new=True,
                    **kwargs
                )
        else:
            # Use real engine
            return tag_position(
                engine_path=self.engine_path,
                fen=fen,
                played_move_uci=move_uci,
                use_new=True,
                **kwargs
            )

    def test_accurate_knight_bishop_exchange(self):
        """Test accurate KBE detection (Δcp < 10)"""
        # QGD: Nxd5 (knight takes pawn, accurate trade, ~8cp loss)
        fen = "r1b2rk1/p5b1/q1p2npp/1p1pNp2/3Pn3/1PN3P1/PQ1BPPBP/2R2RK1 b - - 3 17"
        move_uci = "Nxd2"  # Nxd2 - knight takes pawn

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # FORCED ASSERTION: accurate KBE must be True
        self.assertTrue(result.accurate_knight_bishop_exchange,
                        "accurate_knight_bishop_exchange must be True for Δcp < 10")

        # Verify diagnostic information in analysis_context
        self.assertIsNotNone(result.analysis_context)
        kbe_diag = result.analysis_context.get("knight_bishop_exchange")

        self.assertIsNotNone(kbe_diag, "KBE diagnostics should be present when tag is triggered")
        self.assertEqual(kbe_diag.get("subtype"), "accurate_knight_bishop_exchange")
        self.assertTrue(kbe_diag.get("detected"))
        self.assertIsNotNone(kbe_diag.get("eval_delta_cp"))
        self.assertIsNotNone(kbe_diag.get("recapture_rank"))

    def test_inaccurate_knight_bishop_exchange(self):
        """Test inaccurate KBE detection (10 ≤ Δcp < 30)"""
        # Position where minor piece exchange loses material/position
        # Queens Gambit Declined variant: Nxd5 with moderate disadvantage (~15cp loss)
        fen = "r3kb1r/pp1b1ppp/1qn1pn2/2pp2B1/3P4/1QP1P3/PP1NBPPP/R3K1NR w KQkq - 4 8"
        move_uci = "Bxf6"  # Nxd5 - knight takes pawn with eval drop ~15cp

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # FORCED ASSERTION: inaccurate KBE must be True
        self.assertTrue(result.inaccurate_knight_bishop_exchange,
                        "inaccurate_knight_bishop_exchange must be True for 10 ≤ Δcp < 30")

        # Check diagnostics
        kbe_diag = result.analysis_context.get("knight_bishop_exchange")
        self.assertEqual(kbe_diag.get("subtype"), "inaccurate_knight_bishop_exchange")
        eval_delta = kbe_diag.get("eval_delta_cp", 0)
        self.assertGreaterEqual(eval_delta, 10, "Inaccurate KBE should have Δcp ≥ 10")
        self.assertLess(eval_delta, 30, "Inaccurate KBE should have Δcp < 30")

    def test_bad_knight_bishop_exchange(self):
        """Test bad KBE detection (Δcp ≥ 30)"""
        # Position with seriously disadvantageous piece trade
        # Sicilian Defense: Bxb4 losing the bishop pair + central control
        fen = "1r3rk1/p4pb1/bq2p2p/3p2p1/3N4/1PP1P1P1/P2QPRBP/R5K1 b - - 2 22"
        move_uci = "Bxd4"  # Bxb4 - bishop takes knight with eval drop ~35-40cp

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # FORCED ASSERTION: bad KBE must be True
        self.assertTrue(result.bad_knight_bishop_exchange,
                        "bad_knight_bishop_exchange must be True for Δcp ≥ 30")

        # Check diagnostics
        kbe_diag = result.analysis_context.get("knight_bishop_exchange")
        self.assertEqual(kbe_diag.get("subtype"), "bad_knight_bishop_exchange")
        eval_delta = kbe_diag.get("eval_delta_cp", 0)
        self.assertGreaterEqual(eval_delta, 30, "Bad KBE should have Δcp ≥ 30")

    def test_non_kbe_move(self):
        """Test that non-KBE moves don't trigger false positives"""
        # Simple pawn move
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        move_uci = "e2e4"

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # KBE tags should be False for non-capturing moves
        self.assertFalse(result.accurate_knight_bishop_exchange)
        self.assertFalse(result.inaccurate_knight_bishop_exchange)
        self.assertFalse(result.bad_knight_bishop_exchange)

    def test_kbe_diagnostics_structure(self):
        """Test that KBE diagnostics have expected structure"""
        # Any KBE position
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 5"
        move_uci = "c4f7"  # Bxf7+

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # If KBE detected, verify diagnostic structure
        if any([
            result.accurate_knight_bishop_exchange,
            result.inaccurate_knight_bishop_exchange,
            result.bad_knight_bishop_exchange,
        ]):
            kbe_diag = result.analysis_context.get("knight_bishop_exchange")
            self.assertIsNotNone(kbe_diag)

            # Required fields
            self.assertIn("detected", kbe_diag)
            self.assertIn("subtype", kbe_diag)
            self.assertIn("eval_delta_cp", kbe_diag)
            self.assertIn("recapture_rank", kbe_diag)
            self.assertIn("recapture_square", kbe_diag)
            self.assertIn("depth_used", kbe_diag)
            self.assertIn("topn_checked", kbe_diag)

            # Optional fields
            if "opponent_candidates" in kbe_diag:
                self.assertIsInstance(kbe_diag["opponent_candidates"], list)

    def test_new_pipeline_marker(self):
        """Test that new pipeline sets __new_pipeline__ marker"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        move_uci = "e2e4"

        result = self._tag_position_with_mock(fen=fen, move_uci=move_uci)

        # Verify new pipeline marker is present
        self.assertIsNotNone(result.analysis_context)
        engine_meta = result.analysis_context.get("engine_meta", {})
        self.assertIn("__orchestrator__", engine_meta)
        self.assertEqual(engine_meta["__orchestrator__"], "rule_tagger2.new_pipeline")


if __name__ == "__main__":
    unittest.main()
