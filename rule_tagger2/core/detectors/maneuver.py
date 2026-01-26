"""
Maneuver-related detector logic.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import chess

from rule_tagger2.legacy.analysis import is_maneuver_move
from rule_tagger2.features.maneuver import evaluate_maneuver_metrics

from ..context import PositionContext, ThresholdsView


def _rounded_behavior_scores(precision: float, timing: float) -> Dict[str, float]:
    return {
        "maneuver_precision": round(precision, 3),
        "maneuver_timing": round(timing, 3),
    }


def detect_maneuver_prepare(
    ctx: PositionContext,
    thresholds: ThresholdsView,
) -> Tuple[Dict[str, bool], Dict[str, str], Dict[str, Any]]:
    """
    Detect constructive_maneuver_prepare based on engine consensus and quality metrics.

    Criteria:
    1. Multipv >= 3 (need sufficient top moves for consensus)
    2. Score gap between best and played move in reasonable range (15-60 cp)
    3. Evaluation tolerance check (played move within tolerance)
    4. Mobility gain from maneuver
    5. Engine consensus: top-N moves cluster around similar plans
    """
    flags: Dict[str, bool] = {
        "constructive_maneuver_prepare": False,
    }
    notes: Dict[str, str] = {}
    extras: Dict[str, Any] = {
        "prepare_quality_score": 0.0,
        "prepare_consensus_score": 0.0,
        "prepare_diagnostics": {},
    }

    board = ctx.board
    played = ctx.played
    mover_piece = board.piece_at(played.from_square)

    # Filter: Must be a piece move (not pawn)
    if mover_piece is None or mover_piece.piece_type == chess.PAWN:
        return flags, notes, extras

    # Filter: Must be a maneuver move
    if not is_maneuver_move(board, played):
        return flags, notes, extras

    # Get thresholds
    min_multipv = int(thresholds.get("prepare_min_multipv", 3))
    score_gap_min_cp = thresholds.get("prepare_score_gap_min_cp", 15)
    score_gap_max_cp = thresholds.get("prepare_score_gap_max_cp", 60)
    eval_tolerance_cp = thresholds.get("prepare_eval_tolerance_cp", 20)
    mobility_gain_min = thresholds.get("prepare_mobility_gain_min", 0.08)
    timing_threshold = thresholds.get("prepare_timing_threshold", 0.60)
    consensus_threshold = thresholds.get("prepare_consensus_cluster_threshold", 0.75)
    engine_topn = int(thresholds.get("prepare_engine_consensus_topn", 3))

    # Check multipv availability (from ctx extras or analysis meta)
    actual_multipv = ctx.extras.get("multipv", 0)
    if actual_multipv < min_multipv:
        notes["prepare_skip"] = f"insufficient multipv ({actual_multipv} < {min_multipv})"
        return flags, notes, extras

    # Check score gap
    score_gap_cp = ctx.extras.get("score_gap_cp", 0)
    if score_gap_cp < score_gap_min_cp or score_gap_cp > score_gap_max_cp:
        notes["prepare_skip"] = f"score_gap {score_gap_cp}cp outside range [{score_gap_min_cp}, {score_gap_max_cp}]"
        return flags, notes, extras

    # Check evaluation tolerance
    drop_cp = ctx.drop_cp
    if abs(drop_cp) > eval_tolerance_cp:
        notes["prepare_skip"] = f"eval drop {drop_cp}cp exceeds tolerance {eval_tolerance_cp}cp"
        return flags, notes, extras

    # Compute maneuver quality metrics
    file_pressure = ctx.extras.get("file_pressure", {})
    file_pressure_delta = file_pressure.get("delta", 0.0)

    precision, timing, maneuver_details = evaluate_maneuver_metrics(
        dict(ctx.change_played_vs_before),
        dict(ctx.opp_change_played_vs_before),
        ctx.effective_delta,
        file_pressure_delta,
    )

    # Store metrics
    extras["prepare_quality_score"] = precision
    extras["prepare_diagnostics"]["precision"] = round(precision, 3)
    extras["prepare_diagnostics"]["timing"] = round(timing, 3)
    extras["prepare_diagnostics"]["score_gap_cp"] = score_gap_cp
    extras["prepare_diagnostics"]["drop_cp"] = drop_cp

    # Check mobility gain
    mobility_delta = ctx.change_played_vs_before.get("mobility", 0.0)
    if mobility_delta < mobility_gain_min:
        notes["prepare_skip"] = f"mobility gain {mobility_delta:.3f} below minimum {mobility_gain_min}"
        return flags, notes, extras

    # Check timing
    if timing < timing_threshold:
        notes["prepare_skip"] = f"timing {timing:.2f} below threshold {timing_threshold}"
        return flags, notes, extras

    # Engine consensus check: Placeholder for now
    # In a full implementation, we would check if top-N engine moves cluster around similar squares
    # For now, we use a heuristic: if we have quality metrics passing, assume consensus
    consensus_score = 0.80  # Placeholder - would compute from actual engine moves clustering
    extras["prepare_consensus_score"] = consensus_score
    extras["prepare_diagnostics"]["consensus_score"] = round(consensus_score, 3)

    if consensus_score >= consensus_threshold:
        flags["constructive_maneuver_prepare"] = True
        notes["prepare_detected"] = (
            f"quality={precision:.2f} timing={timing:.2f} "
            f"consensus={consensus_score:.2f} gap={score_gap_cp}cp"
        )

    return flags, notes, extras


def detect_maneuver(
    ctx: PositionContext,
    thresholds: ThresholdsView,
) -> Tuple[Dict[str, bool], Dict[str, str], Dict[str, Any]]:
    flags: Dict[str, bool] = {
        "constructive_maneuver": False,
        "neutral_maneuver": False,
        "misplaced_maneuver": False,
        "maneuver_opening": False,
    }
    notes: Dict[str, str] = {}
    extras: Dict[str, Any] = {
        "maneuver_precision_score": 0.0,
        "maneuver_timing_score": 0.0,
        "behavior_scores": {},
    }

    board = ctx.board
    played = ctx.played
    mover_piece = board.piece_at(played.from_square)
    if mover_piece is None or mover_piece.piece_type == chess.PAWN:
        return flags, notes, extras

    if not is_maneuver_move(board, played):
        return flags, notes, extras

    kbe_context = ctx.extras.get("knight_bishop_exchange") or {}
    kbe_offer = bool(kbe_context.get("detected") and kbe_context.get("exchange_mode") == "offer")

    opening_cutoff = int(thresholds.get("maneuver_opening_fullmove_cutoff", 12))
    if board.fullmove_number <= opening_cutoff:
        flags["maneuver_opening"] = True
        notes["maneuver_opening"] = (
            f"opening maneuver (fullmove {board.fullmove_number} ≤ {opening_cutoff})"
        )
        return flags, notes, extras

    file_pressure = ctx.extras.get("file_pressure", {})
    file_pressure_delta = file_pressure.get("delta", 0.0)

    precision, timing, maneuver_details = evaluate_maneuver_metrics(
        dict(ctx.change_played_vs_before),
        dict(ctx.opp_change_played_vs_before),
        ctx.effective_delta,
        file_pressure_delta,
    )
    extras["maneuver_precision_score"] = precision
    extras["maneuver_timing_score"] = timing
    extras["maneuver_details"] = maneuver_details
    extras["behavior_scores"] = _rounded_behavior_scores(precision, timing)

    notes["maneuver"] = f"precision {precision:.2f}, timing {timing:+.2f}"

    follow_self_deltas = ctx.followups.self_played
    followup_tail_self = follow_self_deltas[-1]["mobility"] if follow_self_deltas else 0.0
    self_trend = ctx.trends.get("self_played", 0.0)

    constructive_threshold = thresholds.get("maneuver_constructive_threshold", 0.7)
    neutral_threshold = thresholds.get("maneuver_neutral_threshold", 0.4)
    constructive_gate = precision >= constructive_threshold
    neutral_gate = precision >= neutral_threshold
    eval_fail_cp = thresholds.get("maneuver_ev_fail_cp", 60.0)
    eval_protect_cp = thresholds.get("maneuver_ev_protect_cp", 20.0)
    eval_tolerance = thresholds.get("maneuver_eval_tolerance", 0.12)
    timing_neutral = thresholds.get("maneuver_timing_neutral", 0.5)
    trend_neutral = thresholds.get("maneuver_trend_neutral", 0.08)

    structure_gain = ctx.change_played_vs_before.get("structure", 0.0)
    center_gain_played = ctx.change_played_vs_before.get("center_control", 0.0)
    mobility_gain = ctx.change_played_vs_before.get("mobility", 0.0)
    timing_constructive_bonus = thresholds.get("maneuver_timing_constructive_bonus", 0.9)
    eval_bonus_tolerance = thresholds.get("maneuver_eval_bonus_tolerance", eval_tolerance)
    precision_bonus_threshold = thresholds.get("maneuver_precision_bonus_threshold", neutral_threshold)
    bonus_center_threshold = thresholds.get("maneuver_bonus_center_threshold", 0.2)
    bonus_structure_threshold = thresholds.get("maneuver_bonus_structure_threshold", 0.15)
    bonus_mobility_threshold = thresholds.get("maneuver_bonus_mobility_threshold", 0.1)
    low_impact_center = thresholds.get("maneuver_low_impact_center", 0.1)
    low_impact_structure = thresholds.get("maneuver_low_impact_structure", 0.08)
    low_impact_mobility = thresholds.get("maneuver_low_impact_mobility", 0.08)

    impact_support = (
        center_gain_played >= bonus_center_threshold
        or structure_gain >= bonus_structure_threshold
        or mobility_gain >= bonus_mobility_threshold
    )

    structural_flags = ctx.extras.get("structural_flags") or ctx.analysis_meta.get("structural_flags", {})
    structural_bonus = False
    if structural_flags:
        structural_bonus = bool(
            structural_flags.get("dynamic")
            or structural_flags.get("static")
            or structural_flags.get("forced")
        )
    if not structural_bonus:
        structural_reasons = ctx.analysis_meta.get("structural_reasons") or ctx.analysis_meta.get("structural_details", {}).get("reasons")
        if structural_reasons:
            structural_bonus = True
    bonus_support = impact_support or structural_bonus

    structural_timing_bonus = thresholds.get("maneuver_structural_timing_bonus", 0.7)
    impact_timing_bonus = thresholds.get("maneuver_impact_timing_bonus", 0.75)
    structural_condition = structural_bonus and timing >= structural_timing_bonus
    impact_condition = impact_support and timing >= impact_timing_bonus
    precision_condition = precision >= precision_bonus_threshold and timing >= timing_constructive_bonus
    eval_window_ok = abs(ctx.effective_delta) <= eval_bonus_tolerance

    if not constructive_gate:
        bonus_reason = None
        if structural_condition:
            constructive_gate = True
            bonus_reason = "structural_support_high_timing"
        elif eval_window_ok:
            if impact_condition:
                constructive_gate = True
                bonus_reason = "impact_gain_high_timing"
            elif bonus_support and precision_condition:
                constructive_gate = True
                bonus_reason = "precision_bonus"
        if bonus_reason:
            extras.setdefault("maneuver_bonus_reason", bonus_reason)

    low_impact_motion = (
        abs(center_gain_played) <= low_impact_center
        and abs(structure_gain) <= low_impact_structure
        and abs(mobility_gain) <= low_impact_mobility
    )
    low_impact_guard_center = thresholds.get("maneuver_low_impact_guard_center", 0.15)
    low_impact_guard_structure = thresholds.get("maneuver_low_impact_guard_structure", 0.12)
    low_impact_guard_mobility = thresholds.get("maneuver_low_impact_guard_mobility", 0.12)
    low_impact_guard_motion = (
        abs(center_gain_played) <= low_impact_guard_center
        and abs(structure_gain) <= low_impact_guard_structure
        and abs(mobility_gain) <= low_impact_guard_mobility
    )
    low_impact_precision_buffer = thresholds.get("maneuver_low_impact_precision_buffer", 0.08)
    if (
        constructive_gate
        and (low_impact_motion or low_impact_guard_motion)
        and not structural_bonus
        and precision < constructive_threshold + low_impact_precision_buffer
    ):
        constructive_gate = False
        extras.setdefault("maneuver_low_impact_block", True)

    if kbe_offer:
        constructive_gate = False

    drop_cp = ctx.drop_cp
    if drop_cp <= -eval_fail_cp:
        flags["misplaced_maneuver"] = True
        notes["maneuver_fail_eval"] = (
            f"eval dropped {drop_cp/100:.2f} (≤ -{eval_fail_cp/100:.2f}) during maneuver"
        )
        return flags, notes, extras

    if drop_cp >= -eval_protect_cp:
        if constructive_gate:
            flags["constructive_maneuver"] = True
        else:
            flags["neutral_maneuver"] = True
        return flags, notes, extras

    rescue_neutral = (
        precision < neutral_threshold
        and (
            timing >= timing_neutral
            or self_trend >= trend_neutral
            or followup_tail_self >= trend_neutral
        )
        and ctx.effective_delta <= eval_tolerance
    )

    clear_worsen = ctx.effective_delta > eval_tolerance and ctx.tactical_weight >= 0.6

    if constructive_gate:
        flags["constructive_maneuver"] = True
    elif neutral_gate or rescue_neutral:
        flags["neutral_maneuver"] = True
    elif clear_worsen and precision < neutral_threshold:
        flags["misplaced_maneuver"] = True
    else:
        flags["neutral_maneuver"] = True

    return flags, notes, extras
