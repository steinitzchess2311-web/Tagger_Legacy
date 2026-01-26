"""
Analysis helpers for the rule tagger.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import chess

from .thresholds import (
    LOSING_TAU_MIN,
    LOSING_TAU_SCALE,
    MANEUVER_ALLOW_LIGHT_CAPTURE,
    SOFT_GATE_MIDPOINT,
    SOFT_GATE_WIDTH,
    TENSION_CONTACT_DELAY,
    VOLATILITY_DROP_TOL,
    WINNING_TAU_MAX,
    WINNING_TAU_SCALE,
)


def compute_tau(eval_before: float) -> float:
    if eval_before >= 3.0:
        return min(WINNING_TAU_MAX, 1.0 + WINNING_TAU_SCALE * (eval_before - 3.0))
    if eval_before <= -2.0:
        return max(LOSING_TAU_MIN, 1.0 + LOSING_TAU_SCALE * (eval_before + 2.0))
    return 1.0


def _soft_gate_weight(effective_delta: float) -> float:
    return 1.0 / (1.0 + math.exp(-(effective_delta - SOFT_GATE_MIDPOINT) / SOFT_GATE_WIDTH))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def compute_tactical_weight(
    delta_eval_cp: int,
    delta_tactics: float,
    delta_structure: float,
    depth_jump_cp: int,
    deepening_gain_cp: int,
    score_gap_cp: int,
    contact_ratio: float,
    phase_ratio: float,
    best_is_forcing: bool,
    played_is_forcing: bool,
    mate_threat: bool,
) -> float:
    eval_component = abs(delta_eval_cp) / 120.0
    depth_component = max(0.0, depth_jump_cp) / 120.0
    deepening_component = max(0.0, deepening_gain_cp) / 90.0
    gap_component = max(0.0, score_gap_cp) / 80.0
    tactics_component = abs(delta_tactics)
    contact_component = contact_ratio
    forcing_component = 0.5 if best_is_forcing else 0.0
    response_penalty = 0.25 if best_is_forcing and not played_is_forcing else 0.0
    mate_component = 0.8 if mate_threat else 0.0
    phase_penalty = (1.0 - phase_ratio) * 0.7
    structure_penalty = max(0.0, abs(delta_structure) - 0.1)

    raw_score = (
        0.45 * eval_component
        + 0.75 * depth_component
        + 0.65 * deepening_component
        + 0.9 * gap_component
        + 1.2 * tactics_component
        + 0.7 * contact_component
        + forcing_component
        + mate_component
        - 0.9 * structure_penalty
        - phase_penalty
        - response_penalty
    )

    return _sigmoid(raw_score - 1.3)


def apply_tactical_gating(
    tags: List[str],
    effective_delta: float,
    material_delta: float,
    blockage_penalty: float,
    plan_passed: bool,
) -> Tuple[Optional[List[str]], Optional[str]]:
    if effective_delta <= -2.0 or material_delta <= -1.0:
        return ["missed_tactic"], "tactical_blunder"
    if blockage_penalty >= 1.0 and effective_delta <= -1.0:
        return ["missed_tactic", "structural_blockage"], "structural_failure"
    if plan_passed is False:
        return ["prophylactic_meaningless"], "plan_drop_failed"
    return None, None


LIGHT_PIECES = {chess.PAWN, chess.KNIGHT, chess.BISHOP}


def _is_light_trade(board: chess.Board, move: chess.Move) -> bool:
    captured = board.piece_at(move.to_square)
    if not captured or captured.piece_type not in LIGHT_PIECES:
        return False
    if board.gives_check(move):
        return False
    return True


def is_maneuver_move(board: chess.Board, move: chess.Move) -> bool:
    piece = board.piece_at(move.from_square)
    if piece is None:
        return False
    if board.gives_check(move):
        return False
    if board.is_capture(move):
        if not MANEUVER_ALLOW_LIGHT_CAPTURE:
            return False
        if not _is_light_trade(board, move):
            return False
    if piece.piece_type == chess.PAWN:
        return False
    if piece.piece_type == chess.KING:
        active_pieces = sum(
            1
            for sq_piece in board.piece_map().values()
            if sq_piece.piece_type not in (chess.KING, chess.PAWN)
        )
        if active_pieces > 6 and not board.is_capture(move):
            return False
    return True


def evaluate_maneuver_metrics(
    change_self: Dict[str, float],
    change_opp: Dict[str, float],
    effective_delta: float,
    file_pressure_delta: float,
) -> Tuple[float, float, Dict[str, float]]:
    mobility_gain = change_self.get("mobility", 0.0)
    center_gain = change_self.get("center_control", 0.0)
    structure_gain = change_self.get("structure", 0.0)
    king_safety_gain = change_self.get("king_safety", 0.0)

    dest_value = max(
        0.0,
        min(1.0, 0.4 * max(0.0, center_gain) + 0.3 * max(0.0, mobility_gain) + 0.3 * max(0.0, file_pressure_delta)),
    )
    path_cost = max(
        0.0,
        min(
            1.0,
            -mobility_gain * 0.5 + max(0.0, -structure_gain) * 0.3 + max(0.0, -king_safety_gain) * 0.2,
        ),
    )
    precision = max(0.0, min(1.0, dest_value - path_cost))

    opp_mobility_change = change_opp.get("mobility", 0.0)
    opp_center_change = change_opp.get("center_control", 0.0)
    opp_trend = change_opp.get("tactics", 0.0)

    opp_punish = max(0.0, min(1.0, opp_mobility_change + opp_center_change - king_safety_gain))
    alt_miss = max(0.0, min(1.0, (abs(effective_delta)) / 0.5))
    timing = 1.0 - 0.5 * opp_punish - 0.5 * alt_miss
    timing = max(-1.0, min(1.0, timing))

    details = {
        "dest_value": round(dest_value, 3),
        "path_cost": round(path_cost, 3),
        "opp_punish": round(opp_punish, 3),
        "alt_miss": round(alt_miss, 3),
        "opp_trend": round(opp_trend, 3),
    }
    return precision, timing, details


def compute_behavior_scores(
    mobility_gain: float,
    center_gain: float,
    eval_delta: float,
    tension_delta: float,
    structure_drop: float,
    king_safety_change: float,
    opp_mobility_change: float,
) -> Dict[str, float]:
    aggression = max(0.0, min(1.0, tension_delta - max(0.0, structure_drop)))
    maneuver_score = max(-1.0, min(1.0, 0.5 * mobility_gain + 0.3 * center_gain - 0.2 * max(0.0, -eval_delta)))
    safety_bias = max(-1.0, min(1.0, king_safety_change - mobility_gain))
    return {
        "aggression": round(aggression, 3),
        "maneuver": round(maneuver_score, 3),
        "safety": round(safety_bias, 3),
        "opp_mobility": round(opp_mobility_change, 3),
    }


def detect_risk_avoidance(
    king_safety_gain: float,
    eval_loss: float,
    opp_tactics_change: float,
    contact_delta: float,
) -> bool:
    return (
        king_safety_gain > 0.0
        and eval_loss <= 0.60
        and opp_tactics_change <= 0.0
        and contact_delta <= VOLATILITY_DROP_TOL
    )


def is_attacking_pawn_push(board: chess.Board, move: chess.Move, actor: chess.Color) -> bool:
    piece = board.piece_at(move.from_square)
    if not piece or piece.piece_type != chess.PAWN or piece.color != actor:
        return False
    if board.is_capture(move):
        return False
    rank_from = chess.square_rank(move.from_square)
    rank_to = chess.square_rank(move.to_square)
    if actor == chess.WHITE and rank_to <= rank_from:
        return False
    if actor == chess.BLACK and rank_to >= rank_from:
        return False
    return rank_to >= 3 if actor == chess.WHITE else rank_to <= 4


def infer_intent_hint(
    delta_self_mobility: float,
    opp_mobility_delta: float,
    king_safety_gain: float,
    center_gain: float,
    contact_jump: float,
    eval_delta: float,
) -> Tuple[str, Dict[str, float]]:
    signals = {
        "delta_self_mobility": round(delta_self_mobility, 3),
        "opp_mobility_delta": round(opp_mobility_delta, 3),
        "king_safety_gain": round(king_safety_gain, 3),
        "center_gain": round(center_gain, 3),
        "contact_jump": round(contact_jump, 3),
        "eval_delta": round(eval_delta, 3),
    }
    label = "neutral"
    if king_safety_gain >= 0.05 and delta_self_mobility <= 0.05 and opp_mobility_delta <= -0.05:
        label = "consolidation"
    elif opp_mobility_delta <= -0.15 and center_gain >= 0.05 and eval_delta >= -0.3:
        label = "restriction"
    elif contact_jump >= TENSION_CONTACT_DELAY and delta_self_mobility >= 0.2:
        label = "expansion"
    elif delta_self_mobility >= 0.25 and eval_delta >= 0.2:
        label = "initiative"
    elif delta_self_mobility <= -0.2 and eval_delta <= -0.3:
        label = "passive"
    return label, signals


def is_relevant_backward(
    square: str,
    move: chess.Move,
    actor: chess.Color,
    board_after: chess.Board,
    contact_jump: float,
) -> bool:
    sq = chess.parse_square(square)
    piece = board_after.piece_at(sq)
    if not piece or piece.color != actor or piece.piece_type != chess.PAWN:
        return False
    file_delta = abs(chess.square_file(sq) - chess.square_file(move.to_square))
    rank_delta = chess.square_rank(move.to_square) - chess.square_rank(move.from_square)
    if actor == chess.WHITE:
        advance = chess.square_rank(move.to_square) - chess.square_rank(move.from_square)
    else:
        advance = chess.square_rank(move.from_square) - chess.square_rank(move.to_square)
    return file_delta <= 1 and advance >= 1 and (contact_jump <= 0.05 or rank_delta >= 1)


def backward_delta(
    before: List[str],
    after: List[str],
    move: chess.Move,
    actor: chess.Color,
    board_after: chess.Board,
    contact_jump: float,
) -> Tuple[int, List[str]]:
    before_set = set(before)
    after_set = set(after)
    new = [
        square
        for square in after_set - before_set
        if is_relevant_backward(square, move, actor, board_after, contact_jump)
    ]
    return len(new), new


def open_file_score(board: chess.Board, file_idx: int) -> float:
    own_pawns = 0
    opp_pawns = 0
    for rank in range(8):
        sq = chess.square(file_idx, rank)
        piece = board.piece_at(sq)
        if not piece:
            continue
        if piece.piece_type == chess.PAWN:
            if piece.color == board.turn:
                own_pawns += 1
            else:
                opp_pawns += 1
    if own_pawns == 0 and opp_pawns == 0:
        return 1.0
    if own_pawns == 0 and opp_pawns == 1:
        return 0.6
    if own_pawns == 0 and opp_pawns > 1:
        return 0.4
    if own_pawns == 1 and opp_pawns == 0:
        return 0.5
    return 0.0


def file_pressure(
    board_before: chess.Board,
    board_after: chess.Board,
    actor: chess.Color,
    file_idx: int,
    target_square: chess.Square,
) -> Tuple[float, Dict[str, Any]]:
    pressure_info: Dict[str, Any] = {}

    def _pressure(board: chess.Board) -> Tuple[float, Dict[str, Any]]:
        attackers = len(board.attackers(actor, target_square))
        defenders = len(board.attackers(not actor, target_square))
        ad = attackers - defenders
        pressure_info_local = {
            "attackers": attackers,
            "defenders": defenders,
            "ad": ad,
        }

        # X-ray detection along file
        xray = 0.0
        for rank in range(8):
            sq = chess.square(file_idx, rank)
            piece = board.piece_at(sq)
            if not piece or piece.color != actor:
                continue
            if piece.piece_type not in (chess.ROOK, chess.QUEEN):
                continue
            between = chess.SquareSet.between(sq, target_square)
            if not between:
                continue
            blockers = [b for b in between if board.piece_at(b)]
            if not blockers:
                xray = max(xray, 1.0)
            elif len(blockers) == 1 and board.piece_at(blockers[0]).color == actor:
                xray = max(xray, 0.7)
        pressure_info_local["xray"] = xray

        open_score = open_file_score(board, file_idx)
        pressure_info_local["open_file"] = open_score

        combined = 0.5 * ad + 0.3 * xray + 0.2 * open_score
        return combined, pressure_info_local

    before_score, before_info = _pressure(board_before)
    after_score, after_info = _pressure(board_after)
    delta = after_score - before_score
    total = after_score + 0.3 * delta

    pressure_info.update(after_info)
    pressure_info["before"] = before_info
    pressure_info["delta"] = round(delta, 3)
    pressure_info["score"] = round(total, 3)

    return max(0.0, min(1.0, total)), pressure_info


def compute_premature_compensation(
    structure_drop: float,
    mobility_gain: float,
    center_gain: float,
    king_attack_potential: float,
    piece_inflow: float,
    self_king_risk: float,
    opp_reinforce: float,
    tactic_against: float,
) -> float:
    comp = (
        0.4 * mobility_gain
        + 0.3 * center_gain
        + 0.2 * king_attack_potential
        + 0.1 * piece_inflow
        - 0.6 * structure_drop
        - 0.3 * self_king_risk
        - 0.2 * opp_reinforce
        - 0.1 * tactic_against
    )
    return max(-1.0, min(1.0, comp))


def blockage_penalty(
    evaluation_before: Dict[str, Any],
    evaluation_after: Dict[str, Any],
    board_before: chess.Board,
    move: chess.Move,
    actor: chess.Color,
    phase_ratio: float,
    radius: int = 2,
) -> Tuple[float, List[Tuple[str, float, float]]]:
    key = "white" if actor == chess.WHITE else "black"
    before_pieces = evaluation_before["mobility"][key]["pieces"]
    after_pieces = evaluation_after["mobility"][key]["pieces"]

    before_map: Dict[str, float] = {}
    for entries in before_pieces.values():
        for entry in entries:
            before_map[entry["square"]] = entry["mobility"]

    penalty = 0.0
    weight_sum = 0.0
    details: List[Tuple[str, float, float]] = []
    to_sq = move.to_square
    from_sq = move.from_square
    moved_piece = board_before.piece_at(from_sq)

    for entries in after_pieces.values():
        for entry in entries:
            square_name = entry["square"]
            before_mob = before_map.get(square_name)
            if before_mob is None:
                continue
            after_mob = entry["mobility"]
            delta = after_mob - before_mob
            if delta >= 0:
                continue
            square_idx = chess.parse_square(square_name)
            dist = min(chess.square_distance(square_idx, to_sq), chess.square_distance(square_idx, from_sq))
            if dist > radius:
                continue
            weight = 1.0 / (1 + dist)
            if moved_piece and moved_piece.piece_type == chess.PAWN:
                weight *= 1.2
            penalty += (-delta) * weight
            weight_sum += weight
            details.append((square_name, delta, weight))

    if not details:
        return 0.0, []
    normalize = max(weight_sum, 1e-6)
    scaled_penalty = penalty / normalize
    scaled_penalty *= (0.6 + 0.4 * phase_ratio)
    return round(scaled_penalty, 3), details


__all__ = [
    "apply_tactical_gating",
    "backward_delta",
    "blockage_penalty",
    "compute_behavior_scores",
    "compute_premature_compensation",
    "compute_tactical_weight",
    "compute_tau",
    "detect_risk_avoidance",
    "evaluate_maneuver_metrics",
    "file_pressure",
    "infer_intent_hint",
    "is_attacking_pawn_push",
    "is_maneuver_move",
    "is_relevant_backward",
    "open_file_score",
    "_soft_gate_weight",
]
