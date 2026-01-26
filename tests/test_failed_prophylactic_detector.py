import unittest

import chess

from rule_tagger2.detectors.failed_prophylactic import FailedProphylacticDetector
from rule_tagger2.orchestration.context import AnalysisContext


class FailedProphylacticDetectorTest(unittest.TestCase):
    """Regression tests for FailedProphylactic detector diagnostics."""

    def test_reason_string_uses_worst_eval_drop_value(self):
        """Ensure detector builds diagnostics with defined variables (no NameError)."""
        board = chess.Board()
        move = chess.Move.from_uci("g1f3")
        ctx = AnalysisContext(board=board, played_move=move, actor=board.turn)
        ctx.metadata["prophylactic_move"] = True

        detector = FailedProphylacticDetector()

        # Stub engine-dependent check so we can deterministically trigger failure.
        detector._check_opponent_refutation = lambda *_: (
            True,
            75,
            chess.Move.from_uci("b7b5"),
        )

        tags = detector.detect(ctx)

        self.assertIn("failed_prophylactic", tags)

        diag_info = detector.get_metadata().diagnostic_info
        self.assertEqual(diag_info.get("reason"), "opponent_refutation_75cp")

        failure_check = ctx.metadata["prophylaxis_diagnostics"]["failure_check"]
        self.assertEqual(failure_check["worst_eval_drop_cp"], 75)


if __name__ == "__main__":
    unittest.main()
