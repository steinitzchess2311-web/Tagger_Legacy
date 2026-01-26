"""
Engine interface abstractions for the v2 rule tagger core.
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple

import chess
import chess.engine

from chess_evaluator import ChessEvaluator, pov

from rule_tagger2.legacy.config import STYLE_COMPONENT_KEYS
from ..models import Candidate
from rule_tagger2.legacy.move_utils import classify_move


class EngineClient(Protocol):
    """Protocol describing the engine interactions required by the facade."""

    def analyse_candidates(
        self,
        board: chess.Board,
        depth: int,
        multipv: int,
        *,
        depth_low: int | None = None,
    ) -> Tuple[List[Candidate], int, Dict[str, Any]]:
        """Return move candidates and evaluation metadata for the given state."""

    def eval_specific(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
    ) -> int:
        """Return centipawn evaluation for `move` played in `board`."""

    def simulate_followups(
        self,
        board: chess.Board,
        actor: chess.Color,
        steps: int,
        *,
        depth: int = 6,
    ) -> Tuple[
        Dict[str, float],
        Dict[str, float],
        List[Dict[str, float]],
        List[Dict[str, float]],
    ]:
        """Return metric sequences after self/opponent follow-ups."""


class StockfishEngine(EngineClient):
    """Stockfish-backed implementation of the engine protocol."""

    def __init__(self, engine_path: str):
        self._engine_path = engine_path

    # --- EngineClient API -------------------------------------------------

    def analyse_candidates(
        self,
        board: chess.Board,
        depth: int,
        multipv: int,
        *,
        depth_low: int | None = None,
    ) -> Tuple[List[Candidate], int, Dict[str, Any]]:
        return analyse_candidates(
            self._engine_path,
            board,
            depth=depth,
            multipv=multipv,
            depth_low=depth_low,
        )

    def eval_specific(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
    ) -> int:
        return eval_specific_move(self._engine_path, board, move, depth=depth)

    def simulate_followups(
        self,
        board: chess.Board,
        actor: chess.Color,
        steps: int,
        *,
        depth: int = 6,
    ) -> Tuple[
        Dict[str, float],
        Dict[str, float],
        List[Dict[str, float]],
        List[Dict[str, float]],
    ]:
        with chess.engine.SimpleEngine.popen_uci(self._engine_path) as engine:
            return simulate_followup_metrics(
                engine,
                board,
                actor,
                steps=steps,
                depth=depth,
            )


# --- Helpers migrated from the frozen rule_tagger v1 implementation -------

def contact_profile(board: chess.Board) -> Tuple[float, int, int, int]:
    total_moves = 0
    capture_moves = 0
    checking_moves = 0
    for mv in board.legal_moves:
        total_moves += 1
        if board.is_capture(mv):
            capture_moves += 1
        else:
            board.push(mv)
            if board.is_check():
                checking_moves += 1
            board.pop()
    contact_moves = capture_moves + checking_moves
    ratio = (contact_moves / total_moves) if total_moves else 0.0
    return ratio, total_moves, capture_moves, checking_moves


def material_balance(board: chess.Board, actor: chess.Color) -> float:
    piece_values = {
        chess.PAWN: 1.0,
        chess.KNIGHT: 3.0,
        chess.BISHOP: 3.0,
        chess.ROOK: 5.0,
        chess.QUEEN: 9.0,
        chess.KING: 0.0,
    }
    total = 0.0
    for _, piece in board.piece_map().items():
        value = piece_values.get(piece.piece_type, 0.0)
        total += value if piece.color == actor else -value
    return total


def defended_square_count(board: chess.Board, color: chess.Color) -> int:
    attacked = chess.SquareSet()
    for square in chess.SquareSet(board.occupied_co[color]):
        piece = board.piece_at(square)
        if piece is None:
            continue
        attacked |= board.attacks(square)
    return len(attacked)


def analyse_candidates(
    engine_path: str,
    board: chess.Board,
    depth: int = 14,
    multipv: int = 6,
    depth_low: int | None = 6,
) -> Tuple[List[Candidate], int, Dict[str, Any]]:
    contact_ratio, total_moves, capture_count, checking_count = contact_profile(board)

    with chess.engine.SimpleEngine.popen_uci(engine_path) as eng:
        low_cp = None
        low_score = None
        if depth_low and depth_low < depth:
            low_info = eng.analyse(board, chess.engine.Limit(depth=depth_low), multipv=1)
            low_root = low_info[0] if isinstance(low_info, list) else low_info
            low_score = low_root["score"].pov(board.turn)
            low_cp = low_score.score(mate_score=10000)

        root = eng.analyse(board, chess.engine.Limit(depth=depth), multipv=max(1, multipv))
        root1 = root[0]
        root_score = root1["score"].pov(board.turn)
        eval_before_cp = root_score.score(mate_score=10000)

        high_cp = None
        high_score = None
        depth_high = max(depth + 4, depth + 2)
        if depth_high > depth:
            high_info = eng.analyse(board, chess.engine.Limit(depth=depth_high), multipv=1)
            high_root = high_info[0] if isinstance(high_info, list) else high_info
            high_score = high_root["score"].pov(board.turn)
            high_cp = high_score.score(mate_score=10000)

        cands: List[Candidate] = []
        for line in root:
            if "pv" not in line or not line["pv"]:
                continue
            mv = line["pv"][0]
            sc = line["score"].pov(board.turn).score(mate_score=10000)
            cands.append(Candidate(move=mv, score_cp=sc, kind=classify_move(board, mv)))

    cands.sort(key=lambda c: c.score_cp, reverse=True)
    score_gap_cp = cands[0].score_cp - cands[1].score_cp if len(cands) > 1 else 0
    depth_low_cp = low_cp if low_cp is not None else eval_before_cp
    depth_jump_cp = eval_before_cp - depth_low_cp
    depth_high_cp = high_cp if high_cp is not None else eval_before_cp

    contact_count = capture_count + checking_count
    mate_threat = root_score.is_mate() or (high_score.is_mate() if high_score else False)
    phase_ratio = estimate_phase_ratio(board)

    analysis_meta: Dict[str, Any] = {
        "score_gap_cp": score_gap_cp,
        "depth_jump_cp": depth_jump_cp,
        "deepening_gain_cp": depth_high_cp - eval_before_cp,
        "contact_ratio": contact_ratio,
        "contact_moves": contact_count,
        "capture_moves": capture_count,
        "checking_moves": checking_count,
        "total_moves": total_moves,
        "phase_ratio": round(phase_ratio, 3),
        "mate_threat": mate_threat,
    }
    analysis_meta.setdefault("engine_meta", {})
    analysis_meta["engine_meta"].update(
        {
            "depth_used": depth,
            "multipv": multipv,
            "depth_low": depth_low,
            "depth_high": depth_high,
        }
    )
    return cands, eval_before_cp, analysis_meta


def eval_specific_move(
    engine_path: str,
    board: chess.Board,
    move: chess.Move,
    depth: int = 14,
) -> int:
    with chess.engine.SimpleEngine.popen_uci(engine_path) as eng:
        board = board.copy(stack=False)
        board.push(move)
        info = eng.analyse(board, chess.engine.Limit(depth=depth), multipv=1)
        root = info[0] if isinstance(info, list) else info
        return root["score"].pov(not board.turn).score(mate_score=10000)


def evaluation_and_metrics(
    board: chess.Board,
    actor: chess.Color,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Any]]:
    evaluation = ChessEvaluator(board).evaluate()
    comps = evaluation["components"]
    metrics = {key: round(pov(comps[key], actor), 3) for key in STYLE_COMPONENT_KEYS}
    opp_metrics = {key: round(-metrics[key], 3) for key in STYLE_COMPONENT_KEYS}
    return metrics, opp_metrics, evaluation


def metrics_delta(lhs: Dict[str, float], rhs: Dict[str, float]) -> Dict[str, float]:
    return {key: round(rhs.get(key, 0.0) - lhs.get(key, 0.0), 3) for key in STYLE_COMPONENT_KEYS}


def simulate_followup_metrics(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    actor: chess.Color,
    steps: int = 3,
    depth: int = 6,
) -> Tuple[Dict[str, float], Dict[str, float], List[Dict[str, float]], List[Dict[str, float]]]:
    future_board = board.copy(stack=False)
    base_metrics, base_opp_metrics, _ = evaluation_and_metrics(future_board, actor)
    metrics_seq: List[Dict[str, float]] = []
    opp_seq: List[Dict[str, float]] = []
    for _ in range(steps):
        if future_board.is_game_over():
            break
        result = engine.play(future_board, chess.engine.Limit(depth=depth))
        if result.move is None:
            break
        future_board.push(result.move)
        metrics, opp_metrics, _ = evaluation_and_metrics(future_board, actor)
        metrics_seq.append(metrics)
        opp_seq.append(opp_metrics)
    return base_metrics, base_opp_metrics, metrics_seq, opp_seq


def estimate_phase_ratio(board: chess.Board) -> float:
    phase_weights = {
        chess.PAWN: 0,
        chess.KNIGHT: 1,
        chess.BISHOP: 1,
        chess.ROOK: 2,
        chess.QUEEN: 4,
    }
    total_phase = 24
    current_phase = 0
    for piece_type, weight in phase_weights.items():
        if weight == 0:
            continue
        for color in (chess.WHITE, chess.BLACK):
            current_phase += weight * len(board.pieces(piece_type, color))
    return current_phase / total_phase if total_phase else 0.0


__all__ = [
    "EngineClient",
    "StockfishEngine",
    "analyse_candidates",
    "contact_profile",
    "defended_square_count",
    "eval_specific_move",
    "evaluation_and_metrics",
    "estimate_phase_ratio",
    "material_balance",
    "metrics_delta",
    "simulate_followup_metrics",
]
