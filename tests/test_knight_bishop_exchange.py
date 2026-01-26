"""
Unit tests for KnightBishopExchangeDetector

Tests cover:
1. Accurate exchange (Δcp < 10)
2. Inaccurate exchange (10 ≤ Δcp < 30)
3. Bad exchange (Δcp ≥ 30)
4. Non-qualifying moves (not a capture, not minor pieces, recapture not in top-3)
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import chess

from rule_tagger2.detectors.knight_bishop_exchange import KnightBishopExchangeDetector
from rule_tagger2.orchestration.context import AnalysisContext


class TestKnightBishopExchangeDetector(unittest.TestCase):
    """Test suite for knight-bishop exchange detection."""

    def setUp(self):
        """Set up test environment with default thresholds."""
        os.environ["KBE_DEPTH"] = "14"
        os.environ["KBE_TOPN"] = "3"
        os.environ["KBE_THRESHOLDS"] = "10,30"
        self.detector = KnightBishopExchangeDetector()

    def tearDown(self):
        """Clean up environment variables."""
        for var in ["KBE_DEPTH", "KBE_TOPN", "KBE_THRESHOLDS"]:
            if var in os.environ:
                del os.environ[var]

    def test_accurate_knight_bishop_exchange(self):
        """Test accurate exchange (minimal eval loss, Δcp < 10)."""
        # Position: e4 e5 Nf3 Nc6 Bb5 (Ruy Lopez)
        # Move: Bxc6 (accurate bishop takes knight)
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3")
        move = chess.Move.from_uci("b5c6")  # White Bxc6

        # Rewind to before move
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=45,
            eval_played_cp=40,  # Δcp = 5 (accurate)
            engine_path="/usr/local/bin/stockfish",
        )

        # Mock the recapture check
        with patch.object(
            self.detector, "_check_recapture_in_topn", return_value=(True, 1, [])
        ):
            tags = self.detector.detect(context)

        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "accurate_knight_bishop_exchange")
        self.assertIn("knight_bishop_exchange", context.metadata)
        self.assertEqual(context.metadata["knight_bishop_exchange"]["subtype"], "accurate_knight_bishop_exchange")

    def test_inaccurate_knight_bishop_exchange(self):
        """Test inaccurate exchange (moderate eval loss, 10 ≤ Δcp < 30)."""
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")
        move = chess.Move.from_uci("b5c6")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=50,
            eval_played_cp=30,  # Δcp = 20 (inaccurate)
            engine_path="/usr/local/bin/stockfish",
        )

        with patch.object(
            self.detector, "_check_recapture_in_topn", return_value=(True, 2, [])
        ):
            tags = self.detector.detect(context)

        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "inaccurate_knight_bishop_exchange")

    def test_bad_knight_bishop_exchange(self):
        """Test bad exchange (significant eval loss, Δcp ≥ 30)."""
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")
        move = chess.Move.from_uci("b5c6")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=100,
            eval_played_cp=50,  # Δcp = 50 (bad)
            engine_path="/usr/local/bin/stockfish",
        )

        with patch.object(
            self.detector, "_check_recapture_in_topn", return_value=(True, 1, [])
        ):
            tags = self.detector.detect(context)

        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "bad_knight_bishop_exchange")

    def test_not_a_capture(self):
        """Test that non-capture moves are not detected."""
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")  # Not a capture

        context = AnalysisContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=20,
            eval_played_cp=20,
        )

        tags = self.detector.detect(context)
        self.assertEqual(len(tags), 0)

    def test_not_minor_piece_capture(self):
        """Test that non-minor-piece captures are not detected."""
        # Position where rook takes pawn
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3")
        move = chess.Move.from_uci("h1e1")  # Rook move (not a minor piece)

        context = AnalysisContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=20,
            eval_played_cp=20,
        )

        tags = self.detector.detect(context)
        self.assertEqual(len(tags), 0)

    def test_recapture_not_in_topn(self):
        """Test that exchanges without recapture in top-N are not detected."""
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")
        move = chess.Move.from_uci("b5c6")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=45,
            eval_played_cp=40,
            engine_path="/usr/local/bin/stockfish",
        )

        # Mock recapture NOT found in top-3
        with patch.object(
            self.detector, "_check_recapture_in_topn", return_value=(False, 0, [])
        ):
            tags = self.detector.detect(context)

        self.assertEqual(len(tags), 0)
        metadata = self.detector.get_metadata()
        self.assertIn("recapture_not_in_topn", metadata.diagnostic_info.get("reason", ""))

    def test_black_perspective_eval_delta(self):
        """Test that eval delta is correctly computed for Black."""
        # Use white Bxc6 position but set actor to BLACK to test sign flip
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")
        move = chess.Move.from_uci("b5c6")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.BLACK,  # Set Black as actor to test eval sign flip
            eval_before_cp=20,  # From White's POV (positive = White better)
            eval_played_cp=35,  # From White's POV (White gained)
            engine_path="/usr/local/bin/stockfish",
        )

        # Mock both methods to bypass position validation
        with patch.object(self.detector, "_is_minor_piece_capture", return_value=True), \
             patch.object(self.detector, "_check_recapture_in_topn", return_value=(True, 1, [])):
            tags = self.detector.detect(context)

        # For Black actor: eval_delta = -(20 - 35) = -(-15) = 15
        # (positive eval_delta means the actor lost evaluation)
        self.assertEqual(len(tags), 1)
        metadata = self.detector.get_metadata()
        self.assertEqual(metadata.diagnostic_info["eval_delta_cp"], 15)

    def test_is_applicable(self):
        """Test that detector only runs on capture moves."""
        board = chess.Board()

        # Non-capture move
        move_quiet = chess.Move.from_uci("e2e4")
        context_quiet = AnalysisContext(board=board, played_move=move_quiet, actor=chess.WHITE)
        self.assertFalse(self.detector.is_applicable(context_quiet))

        # Capture move
        board_capture = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
        move_capture = chess.Move.from_uci("e4e5")
        context_capture = AnalysisContext(board=board_capture, played_move=move_capture, actor=chess.WHITE)
        self.assertTrue(self.detector.is_applicable(context_capture))

    def test_priority(self):
        """Test that detector has correct priority."""
        self.assertEqual(self.detector.get_priority(), 20)

    def test_metadata_caching(self):
        """Test that metadata is correctly cached to context."""
        board_before = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3")
        move = chess.Move.from_uci("b5c6")

        context = AnalysisContext(
            board=board_before,
            played_move=move,
            actor=chess.WHITE,
            eval_before_cp=45,
            eval_played_cp=40,
            engine_path="/usr/local/bin/stockfish",
        )

        with patch.object(
            self.detector, "_check_recapture_in_topn", return_value=(True, 1, [])
        ):
            tags = self.detector.detect(context)

        # Check metadata is in context
        self.assertIn("knight_bishop_exchange", context.metadata)
        kbe_meta = context.metadata["knight_bishop_exchange"]
        self.assertTrue(kbe_meta["detected"])
        self.assertEqual(kbe_meta["subtype"], "accurate_knight_bishop_exchange")
        self.assertEqual(kbe_meta["eval_delta_cp"], 5)
        self.assertEqual(kbe_meta["recapture_rank"], 1)
        self.assertEqual(kbe_meta["depth_used"], 14)
        self.assertEqual(kbe_meta["topn_checked"], 3)


if __name__ == "__main__":
    unittest.main()
