"""
Knight-Bishop Exchange Detector

This detector identifies moves where a knight or bishop captures an opponent's
knight or bishop, and classifies the exchange based on evaluation loss:

Subtypes:
- accurate_knight_bishop_exchange: Δcp < 10 (minimal loss)
- inaccurate_knight_bishop_exchange: 10 ≤ Δcp < 30 (moderate loss)
- bad_knight_bishop_exchange: Δcp ≥ 30 (significant loss)

Detection criteria:
1. Either: (a) The played move is a minor piece (N/B) capturing opponent's minor piece (N/B); or
   (b) The move offers an exchange by moving a minor into an opponent minor's attack while defended
2. For capture lines, opponent's top-3 candidates must include the direct recapture
3. Evaluation delta is calculated as: Δcp = eval_before - eval_after (from player's POV)

Environment variables:
- KBE_DEPTH: Analysis depth for recapture check (default: 14)
- KBE_TOPN: Number of top moves to check for recapture (default: 3)
- KBE_THRESHOLDS: Comma-separated thresholds for accurate/inaccurate (default: "10,30")

Extracted from milestone3 requirements in project_process.md.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import chess
import chess.engine

from rule_tagger2.detectors.base import DetectorMetadata, TagDetector
from rule_tagger2.orchestration.context import AnalysisContext


def _get_kbe_config() -> Tuple[int, int, List[int]]:
    """
    Load knight-bishop exchange configuration from environment variables.

    Returns:
        Tuple of (depth, topn, thresholds)
        - depth: Analysis depth for recapture check
        - topn: Number of top moves to check
        - thresholds: [accurate_threshold, inaccurate_threshold]
    """
    depth = int(os.getenv("KBE_DEPTH", "14"))
    topn = int(os.getenv("KBE_TOPN", "3"))
    threshold_str = os.getenv("KBE_THRESHOLDS", "10,30")
    thresholds = [int(x.strip()) for x in threshold_str.split(",")]
    if len(thresholds) != 2:
        thresholds = [10, 30]  # fallback
    return depth, topn, thresholds


class KnightBishopExchangeDetector(TagDetector):
    """
    Detects knight-bishop exchanges and classifies them by evaluation delta.

    This detector identifies moves where a minor piece captures an opponent's
    minor piece, checks if recapture is in the opponent's top-N moves,
    and classifies the exchange based on evaluation loss.
    """

    def __init__(self):
        """Initialize detector with environment-based configuration."""
        self._depth, self._topn, self._thresholds = _get_kbe_config()
        self._last_metadata: Optional[DetectorMetadata] = None

    @property
    def name(self) -> str:
        return "KnightBishopExchange"

    def detect(self, context: AnalysisContext) -> List[str]:
        """
        Detect knight-bishop exchange and return appropriate tag.

        Args:
            context: AnalysisContext containing board state and analysis

        Returns:
            List containing at most one tag:
            - "accurate_knight_bishop_exchange"
            - "inaccurate_knight_bishop_exchange"
            - "bad_knight_bishop_exchange"
            Or empty list if not a qualifying exchange.
        """
        tags = []
        diagnostic_info = {}
        confidence_scores = {}

        # Determine whether this is a direct capture or an exchange offer
        exchange_mode = "capture"
        board_after = context.board.copy(stack=False)
        board_after.push(context.played_move)

        offer_info = None
        if not self._is_minor_piece_capture(context):
            offer_info = self._find_minor_exchange_offer(context, board_after)
            if offer_info is None:
                self._last_metadata = DetectorMetadata(
                    detector_name=self.name,
                    tags_found=[],
                    diagnostic_info={"reason": "not_minor_piece_exchange"},
                )
                return tags
            exchange_mode = "offer"

        # Get the capture/target square (where the exchange happens)
        capture_square = context.played_move.to_square
        diagnostic_info["capture_square"] = chess.square_name(capture_square)
        diagnostic_info["exchange_mode"] = exchange_mode

        opponent_candidates: List[Dict] = []
        diagnostic_info["opponent_topn_moves"] = []
        recapture_found = True
        recapture_rank = 0

        if exchange_mode == "capture":
            recapture_found, recapture_rank, opponent_candidates = self._check_recapture_in_topn(
                context, board_after, capture_square
            )

            diagnostic_info["recapture_found"] = recapture_found
            diagnostic_info["recapture_rank"] = recapture_rank
            diagnostic_info["opponent_topn_moves"] = [
                {"move": c["move"].uci(), "score_cp": c["score_cp"]}
                for c in opponent_candidates[:self._topn]
            ]

            if not recapture_found:
                self._last_metadata = DetectorMetadata(
                    detector_name=self.name,
                    tags_found=[],
                    diagnostic_info={"reason": "recapture_not_in_topn", **diagnostic_info},
                )
                return tags
        else:
            diagnostic_info["offer_attackers"] = [
                chess.square_name(sq) for sq in offer_info["attackers"]
            ]
            diagnostic_info["offer_defenders"] = [
                chess.square_name(sq) for sq in offer_info["defenders"]
            ]

        # Calculate evaluation delta from player's POV
        # Δcp = eval_before - eval_after (positive means player lost evaluation)
        # NOTE: context.eval_before_cp and context.eval_played_cp are already in actor's POV
        # (see rule_tagger2/core/engine_io.py:177 and rule_tagger2/legacy/engine/analysis.py:73
        # where .pov(board.turn) is applied), so no additional sign flip is needed.
        eval_delta_cp = context.eval_before_cp - context.eval_played_cp

        diagnostic_info["eval_before_cp"] = context.eval_before_cp
        diagnostic_info["eval_played_cp"] = context.eval_played_cp
        diagnostic_info["eval_delta_cp"] = eval_delta_cp
        diagnostic_info["thresholds"] = {
            "accurate": self._thresholds[0],
            "inaccurate": self._thresholds[1],
        }

        # Classify based on thresholds
        if eval_delta_cp < self._thresholds[0]:
            tag = "accurate_knight_bishop_exchange"
            confidence_scores[tag] = 1.0 - (eval_delta_cp / self._thresholds[0])
        elif eval_delta_cp < self._thresholds[1]:
            tag = "inaccurate_knight_bishop_exchange"
            progress = (eval_delta_cp - self._thresholds[0]) / (
                self._thresholds[1] - self._thresholds[0]
            )
            confidence_scores[tag] = 0.5 + progress * 0.5
        else:
            tag = "bad_knight_bishop_exchange"
            confidence_scores[tag] = min(
                1.0, 0.5 + (eval_delta_cp - self._thresholds[1]) / 50.0
            )

        tags.append(tag)
        diagnostic_info["subtype"] = tag

        # Cache to analysis_meta for report layer
        if "knight_bishop_exchange" not in context.metadata:
            context.metadata["knight_bishop_exchange"] = {}

        kbe_meta = {
            "detected": True,
            "subtype": tag,
            "eval_delta_cp": eval_delta_cp,
            "recapture_rank": recapture_rank,
            "recapture_square": diagnostic_info["capture_square"],
            "depth_used": self._depth,
            "topn_checked": self._topn,
            "opponent_candidates": diagnostic_info["opponent_topn_moves"],
            "exchange_mode": exchange_mode,
        }

        if exchange_mode == "offer" and offer_info:
            kbe_meta["offer_attackers"] = [
                chess.square_name(sq) for sq in offer_info["attackers"]
            ]
            kbe_meta["offer_defenders"] = [
                chess.square_name(sq) for sq in offer_info["defenders"]
            ]

        context.metadata["knight_bishop_exchange"].update(kbe_meta)

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

    def _is_minor_piece_capture(self, context: AnalysisContext) -> bool:
        """
        Check if the played move is a knight or bishop capturing an opponent's knight or bishop.

        Args:
            context: AnalysisContext containing board state

        Returns:
            True if move is a qualifying minor piece exchange
        """
        board = context.board
        move = context.played_move

        # Check if it's a capture
        if not board.is_capture(move):
            return False

        # Get the piece making the capture
        piece = board.piece_at(move.from_square)
        if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
            return False

        # Get the captured piece
        captured_piece = board.piece_at(move.to_square)
        if captured_piece is None or captured_piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
        ):
            return False

        return True

    def _find_minor_exchange_offer(
        self, context: AnalysisContext, board_after: chess.Board
    ) -> Optional[Dict[str, List[int]]]:
        """
        Detect if the move offers a minor-piece exchange by moving into an attacked square.

        Args:
            context: AnalysisContext containing board state
            board_after: Board after the played move

        Returns:
            Dict with attacker/defender squares if offer detected, else None
        """
        board = context.board
        move = context.played_move

        piece = board.piece_at(move.from_square)
        if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
            return None

        if board.is_capture(move):
            return None

        opponent = board_after.turn
        attackers: List[int] = []
        for sq in board_after.attackers(opponent, move.to_square):
            attacker_piece = board_after.piece_at(sq)
            if attacker_piece and attacker_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                attackers.append(sq)

        if not attackers:
            return None

        defenders = [
            sq
            for sq in board_after.attackers(not opponent, move.to_square)
            if board_after.piece_at(sq) is not None
        ]

        if not defenders:
            return None

        return {"attackers": attackers, "defenders": defenders}

    def _check_recapture_in_topn(
        self, context: AnalysisContext, board_after: chess.Board, capture_square: int
    ) -> Tuple[bool, int, List[Dict]]:
        """
        Check if recapture is in opponent's top-N candidate moves.

        Args:
            context: AnalysisContext for engine path
            board_after: Board position after the exchange
            capture_square: Square where the exchange occurred

        Returns:
            Tuple of (recapture_found, rank, candidates)
            - recapture_found: True if recapture is in top-N
            - rank: 1-indexed rank of recapture (0 if not found)
            - candidates: List of top-N opponent candidates
        """
        if not context.engine_path:
            # Fallback: no engine available, assume recapture exists
            return True, 1, []

        try:
            with chess.engine.SimpleEngine.popen_uci(context.engine_path) as eng:
                result = eng.analyse(
                    board_after,
                    chess.engine.Limit(depth=self._depth),
                    multipv=self._topn,
                )

                candidates = []
                if isinstance(result, list):
                    for idx, line in enumerate(result):
                        if "pv" not in line or not line["pv"]:
                            continue
                        mv = line["pv"][0]
                        sc = line["score"].pov(board_after.turn).score(mate_score=10000)
                        candidates.append({"move": mv, "score_cp": sc, "rank": idx + 1})
                else:
                    # Single result
                    if "pv" in result and result["pv"]:
                        mv = result["pv"][0]
                        sc = result["score"].pov(board_after.turn).score(mate_score=10000)
                        candidates.append({"move": mv, "score_cp": sc, "rank": 1})

                # Check if any candidate is a recapture to the original square
                for cand in candidates:
                    if cand["move"].to_square == capture_square:
                        return True, cand["rank"], candidates

                return False, 0, candidates

        except Exception as e:
            # If engine fails, log and return False
            return False, 0, []

    def is_applicable(self, context: AnalysisContext) -> bool:
        """
        Determine if this detector should run.

        Only runs if the move is a capture (quick pre-filter).

        Args:
            context: AnalysisContext to check

        Returns:
            True if detector should run
        """
        board = context.board
        move = context.played_move

        if board.is_capture(move):
            return True

        piece = board.piece_at(move.from_square)
        if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
            return False

        temp = board.copy(stack=False)
        temp.push(move)
        opponent = temp.turn
        for sq in temp.attackers(opponent, move.to_square):
            attacker_piece = temp.piece_at(sq)
            if attacker_piece and attacker_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                defenders = temp.attackers(not opponent, move.to_square)
                if defenders:
                    return True
        return False

    def get_priority(self) -> int:
        """
        Returns execution priority.

        Knight-bishop exchanges are tactical, run early.

        Returns:
            Priority 20 (after main tactical detectors)
        """
        return 20
