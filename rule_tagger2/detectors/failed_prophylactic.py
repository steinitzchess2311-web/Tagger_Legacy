"""
Failed Prophylactic Detector

This detector identifies when a prophylactic move fails - i.e., when a move
tagged as `prophylactic_move` is followed by an opponent response that
causes a significant evaluation drop.

Detection criteria:
1. The current move must be tagged as `prophylactic_move`
2. After the move, opponent's top-N candidate moves are analyzed
3. If any of the top-N moves causes eval drop ≥ threshold, tag as `failed_prophylactic`

Environment variables:
- PROPHY_FAIL_CP: Evaluation drop threshold in centipawns (default: 50)
- PROPHY_FAIL_TOPN: Number of top opponent moves to check (default: 3)

Extracted from milestone4 requirements in project_process.md (rows 45-47).
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import chess
import chess.engine

from rule_tagger2.detectors.base import DetectorMetadata, TagDetector
from rule_tagger2.orchestration.context import AnalysisContext


def _get_prophy_fail_config() -> tuple[int, int]:
    """
    Load failed prophylactic configuration from environment variables.

    Returns:
        Tuple of (eval_drop_threshold_cp, topn)
        - eval_drop_threshold_cp: Minimum eval drop to consider prophylaxis failed
        - topn: Number of top opponent moves to check
    """
    threshold_cp = int(os.getenv("PROPHY_FAIL_CP", "70"))
    topn = int(os.getenv("PROPHY_FAIL_TOPN", "3"))
    return threshold_cp, topn


class FailedProphylacticDetector(TagDetector):
    """
    Detects when a prophylactic move fails due to strong opponent response.

    This detector analyzes positions where a move was tagged as prophylactic
    and checks if the opponent has a strong refutation in their top-N moves.
    """

    def __init__(self):
        """Initialize detector with environment-based configuration."""
        self._threshold_cp, self._topn = _get_prophy_fail_config()
        self._last_metadata: Optional[DetectorMetadata] = None

    @property
    def name(self) -> str:
        return "FailedProphylactic"

    def detect(self, context: AnalysisContext) -> List[str]:
        """
        Detect if a prophylactic move failed.

        Args:
            context: AnalysisContext containing board state and tags

        Returns:
            List containing "failed_prophylactic" if conditions are met, else empty
        """
        tags = []
        diagnostic_info = {}

        # Check if the move was tagged as prophylactic
        is_prophylactic = context.metadata.get("prophylactic_move", False)
        diagnostic_info["is_prophylactic"] = is_prophylactic

        if not is_prophylactic:
            self._last_metadata = DetectorMetadata(
                detector_name=self.name,
                tags_found=[],
                diagnostic_info={"reason": "not_prophylactic", **diagnostic_info},
            )
            return tags

        # Analyze opponent's position after the prophylactic move
        board_after = context.board.copy(stack=False)
        board_after.push(context.played_move)

        # Get opponent's top-N candidate moves and their evaluations
        failure_detected, worst_eval_drop, failing_move = self._check_opponent_refutation(
            context, board_after
        )

        diagnostic_info["failure_detected"] = failure_detected
        diagnostic_info["worst_eval_drop_cp"] = worst_eval_drop
        diagnostic_info["threshold_cp"] = self._threshold_cp
        diagnostic_info["topn_checked"] = self._topn

        if failing_move:
            diagnostic_info["failing_move"] = failing_move.uci()

        if failure_detected:
            tags.append("failed_prophylactic")
            diagnostic_info["reason"] = f"opponent_refutation_{worst_eval_drop}cp"

        # Cache diagnostics to context for report layer
        if "prophylaxis_diagnostics" not in context.metadata:
            context.metadata["prophylaxis_diagnostics"] = {}

        context.metadata["prophylaxis_diagnostics"]["failure_check"] = {
            "failure_detected": failure_detected,
            "worst_eval_drop_cp": worst_eval_drop,
            "threshold_cp": self._threshold_cp,
            "topn_checked": self._topn,
            "failing_move_uci": failing_move.uci() if failing_move else None,
        }

        confidence_scores = {}
        if failure_detected:
            # Higher confidence for larger eval drops
            confidence_scores["failed_prophylactic"] = min(
                1.0, worst_eval_drop / (self._threshold_cp * 2)
            )

        self._last_metadata = DetectorMetadata(
            detector_name=self.name,
            tags_found=tags,
            confidence_scores=confidence_scores,
            diagnostic_info=diagnostic_info,
        )

        return tags

    def get_metadata(self) -> DetectorMetadata:
        """
        Returns metadata from the most recent detection.

        Returns:
            DetectorMetadata with diagnostic information
        """
        if self._last_metadata is None:
            return DetectorMetadata(
                detector_name=self.name, tags_found=[], diagnostic_info={}
            )
        return self._last_metadata

    def _check_opponent_refutation(
        self, context: AnalysisContext, board_after: chess.Board
    ) -> tuple[bool, int, Optional[chess.Move]]:
        """
        Check if opponent has a strong refutation in their top-N moves.

        Args:
            context: AnalysisContext for engine path and current eval
            board_after: Board position after the prophylactic move

        Returns:
            Tuple of (failure_detected, worst_eval_drop_cp, failing_move)
            - failure_detected: True if eval drop >= threshold
            - worst_eval_drop_cp: Largest eval drop found
            - failing_move: The move causing the worst eval drop (or None)
        """
        if not context.engine_path:
            # No engine available, cannot check
            return False, 0, None

        # Baseline eval is the eval after the prophylactic move (from current player's POV)
        baseline_eval_cp = context.eval_played_cp

        worst_eval_drop = 0
        failing_move = None

        try:
            with chess.engine.SimpleEngine.popen_uci(context.engine_path) as eng:
                # Get opponent's top-N candidate moves
                result = eng.analyse(
                    board_after,
                    chess.engine.Limit(depth=context.depth),
                    multipv=self._topn,
                )

                candidates = []
                if isinstance(result, list):
                    for line in result:
                        if "pv" not in line or not line["pv"]:
                            continue
                        candidates.append(line)
                else:
                    candidates = [result]

                # For each candidate, check eval drop
                for line in candidates:
                    if "pv" not in line or not line["pv"]:
                        continue

                    move = line["pv"][0]
                    # Score is from opponent's POV after their move
                    score_pov_opp = line["score"].pov(board_after.turn).score(mate_score=10000)

                    # Convert to current player's POV (negate)
                    score_pov_player = -score_pov_opp

                    # Eval drop = baseline - new_eval (positive means player lost eval)
                    eval_drop = baseline_eval_cp - score_pov_player

                    # Adjust for player color (evals are from White's POV)
                    if context.actor == chess.BLACK:
                        eval_drop = -eval_drop

                    if eval_drop > worst_eval_drop:
                        worst_eval_drop = eval_drop
                        failing_move = move

                # Check if worst drop exceeds threshold
                failure_detected = worst_eval_drop >= self._threshold_cp

                return failure_detected, worst_eval_drop, failing_move

        except Exception as e:
            # Engine error, return no failure
            return False, 0, None

    def is_applicable(self, context: AnalysisContext) -> bool:
        """
        Determine if this detector should run.

        Only runs if the move is tagged as prophylactic.

        Args:
            context: AnalysisContext to check

        Returns:
            True if move is prophylactic
        """
        return context.metadata.get("prophylactic_move", False)

    def get_priority(self) -> int:
        """
        Returns execution priority.

        Failed prophylactic detection runs after prophylaxis detection.

        Returns:
            Priority 60 (late, after main tactical and prophylaxis detectors)
        """
        return 60
