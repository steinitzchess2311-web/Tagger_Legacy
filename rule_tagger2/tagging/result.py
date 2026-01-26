"""
Legacy-compatible tag result computation using prepared analysis data.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

import chess

from engine_utils.prophylaxis import PlanDropResult, detect_prophylaxis_plan_drop

from rule_tagger2.legacy.analysis import (
    blockage_penalty,
    compute_behavior_scores,
    compute_premature_compensation,
    detect_risk_avoidance,
    evaluate_maneuver_metrics,
    file_pressure,
    infer_intent_hint,
)
from rule_tagger2.legacy.config import (
    CENTER_FILES,
    CENTER_TOLERANCE,
    CONTROL_EVAL_DROP,
    DELTA_EVAL_POSITIONAL,
    INITIATIVE_BOOST,
    KING_SAFETY_GAIN,
    KING_SAFETY_TOLERANCE,
    MOBILITY_RISK_TRADEOFF,
    MOBILITY_TOLERANCE,
    NEUTRAL_TENSION_BAND,
    RISK_SMALL_LOSS,
    STRUCTURE_DOMINANCE_LIMIT,
    STRUCTURE_THRESHOLD,
    STYLE_COMPONENT_KEYS,
    TACTICAL_DELTA_TACTICS,
    TACTICAL_DOMINANCE_THRESHOLD,
    TACTICAL_GAP_FIRST_CHOICE,
    TACTICAL_MISS_LOSS,
    TACTICAL_SLOPE_THRESHOLD,
    TACTICAL_THRESHOLD,
    TENSION_CONTACT_DELAY,
    TENSION_CONTACT_DIRECT,
    TENSION_CONTACT_JUMP,
    TENSION_EVAL_MAX,
    TENSION_EVAL_MIN,
    TENSION_MOBILITY_DELAY,
    TENSION_MOBILITY_NEAR,
    TENSION_MOBILITY_THRESHOLD,
    TENSION_SUSTAIN_MIN,
    TENSION_SUSTAIN_VAR_CAP,
    TENSION_SYMMETRY_TOL,
    TENSION_TREND_OPP,
    TENSION_TREND_SELF,
)
from rule_tagger2.legacy.move_utils import classify_move, is_attacking_pawn_push, is_dynamic, is_quiet
from ..models import TAG_PRIORITY, TENSION_TRIGGER_PRIORITY, TagResult
from rule_tagger2.legacy.prophylaxis import (
    PROPHYLAXIS_CONFIG,
    clamp_preventive_score,
    classify_prophylaxis_quality,
    estimate_opponent_threat,
    is_prophylaxis_candidate,
    prophylaxis_pattern_reason,
)
from rule_tagger2.legacy.thresholds import (
    AGGRESSION_THRESHOLD,
    FILE_PRESSURE_THRESHOLD,
    LOSING_TAU_MIN,
    LOSING_TAU_SCALE,
    MANEUVER_CONSTRUCTIVE,
    MANEUVER_MISPLACED,
    MANEUVER_NEUTRAL,
    MOBILITY_SELF_LIMIT,
    PASSIVE_PLAN_EVAL_DROP,
    PASSIVE_PLAN_MOBILITY_OPP,
    PASSIVE_PLAN_MOBILITY_SELF,
    PLAN_DROP_DEPTH,
    PLAN_DROP_ENABLED,
    PLAN_DROP_EVAL_CAP,
    PLAN_DROP_MULTIPV,
    PLAN_DROP_OPP_MOBILITY_GATE,
    PLAN_DROP_PLAN_LOSS_MIN,
    PLAN_DROP_PSI_MIN,
    PLAN_DROP_RUNTIME_CAP_MS,
    PLAN_DROP_SAMPLE_RATE,
    PLAN_DROP_VARIANCE_CAP,
    PREMATURE_ATTACK_HARD,
    PREMATURE_ATTACK_THRESHOLD,
    RISK_AVOIDANCE_MOBILITY_DROP,
    SOFT_BLOCK_SCALE,
    SOFT_GATE_MIDPOINT,
    SOFT_GATE_WIDTH,
    STATIC_BLOCKAGE_MARGIN,
    STATIC_BLOCKAGE_THRESHOLD_BASE,
    STRUCTURE_WEAKEN_LIMIT,
    THRESHOLDS,
    VOLATILITY_DROP_TOL,
    WINNING_TAU_MAX,
    WINNING_TAU_SCALE,
)

from ..engine import EngineClient
from ..pipeline.prep import PreparedData


def compute_tag_result(
    engine: EngineClient,
    prepared: PreparedData,
    *,
    cp_threshold: int,
    small_drop_cp: int,
) -> TagResult:
    """Reproduce the legacy tag computation using precomputed data."""

    board = chess.Board(prepared.fen)
    actor = prepared.actor
    played_move = prepared.played_move
    best = prepared.best_candidate
    best_move = prepared.best_move

    analysis_meta = deepcopy(prepared.analysis_meta)

    metrics_before = prepared.metrics_before
    metrics_played = prepared.metrics_played
    metrics_best = prepared.metrics_best
    opp_metrics_before = prepared.opp_metrics_before
    opp_metrics_played = prepared.opp_metrics_played
    opp_metrics_best = prepared.opp_metrics_best

    evaluation_before = prepared.evaluation_before
    evaluation_played = prepared.evaluation_played
    evaluation_best = prepared.evaluation_best

    component_deltas = prepared.component_deltas
    change_played_vs_before = prepared.change_played_vs_before
    opp_component_deltas = prepared.opp_component_deltas
    opp_change_played_vs_before = prepared.opp_change_played_vs_before

    coverage_before = prepared.coverage_before
    coverage_after = prepared.coverage_after
    coverage_delta = prepared.coverage_delta

    in_band = prepared.in_band
    has_dynamic_in_band = prepared.has_dynamic_in_band

    eval_before_cp = prepared.eval_before_cp
    eval_played_cp = prepared.eval_played_cp
    eval_best_cp = prepared.eval_best_cp

    eval_before = round(eval_before_cp / 100.0, 2)
    eval_played = round(eval_played_cp / 100.0, 2)
    eval_best = round(eval_best_cp / 100.0, 2)
    delta_eval = round((eval_best_cp - eval_played_cp) / 100.0, 2)

    played_score_cp = prepared.played_score_cp
    played_kind = prepared.played_kind

    contact_data = prepared.contacts
    contact_ratio_before = contact_data.get("before", 0.0)
    contact_ratio_played = contact_data.get("played", 0.0)
    contact_ratio_best = contact_data.get("best", 0.0)
    contact_delta_played = contact_data.get("delta_played", 0.0)
    contact_delta_best = contact_data.get("delta_best", 0.0)

    analysis_meta.setdefault("tension_support", {})
    analysis_meta["tension_support"].setdefault("thresholds", {})
    analysis_meta["tension_support"].update(
        {
            "contact_ratio_before": round(contact_ratio_before, 3),
            "contact_ratio_played": round(contact_ratio_played, 3),
            "contact_ratio_best": round(contact_ratio_best, 3),
            "contact_delta_played": round(contact_delta_played, 3),
            "contact_delta_best": round(contact_delta_best, 3),
            "thresholds": {
                "tension_mobility_min": TENSION_MOBILITY_THRESHOLD,
                "tension_mobility_near": TENSION_MOBILITY_NEAR,
                "contact_ratio_min": TENSION_CONTACT_JUMP,
                "contact_ratio_delay": TENSION_CONTACT_DELAY,
                "tension_mobility_delay": TENSION_MOBILITY_DELAY,
                "tension_trend_self": TENSION_TREND_SELF,
                "tension_trend_opp": TENSION_TREND_OPP,
            },
        }
    )

    self_vs_best = {key: round(-component_deltas[key], 3) for key in STYLE_COMPONENT_KEYS}
    opp_vs_best = {key: round(-opp_component_deltas[key], 3) for key in STYLE_COMPONENT_KEYS}

    followup = prepared.followup
    follow_self_deltas = followup.get("self_deltas", [])
    follow_opp_deltas = followup.get("opp_deltas", [])
    follow_self_deltas_best = followup.get("self_deltas_best", [])
    follow_opp_deltas_best = followup.get("opp_deltas_best", [])
    self_trend = followup.get("self_trend", 0.0)
    opp_trend = followup.get("opp_trend", 0.0)
    self_trend_best = followup.get("self_trend_best", 0.0)
    opp_trend_best = followup.get("opp_trend_best", 0.0)
    follow_window_mean = followup.get("window_mean", 0.0)
    follow_window_var = followup.get("window_var", 0.0)

    notes: Dict[str, str] = {}
    delta_self_mobility = change_played_vs_before["mobility"]
    delta_opp_mobility = opp_change_played_vs_before["mobility"]
    control_over_dynamics = False
    deferred_initiative = False
    risk_avoidance = False
    prophylactic_move = False
    prophylaxis_pattern_override = False
    prophylaxis_score = 0.0
    analysis_meta.setdefault("prophylaxis", {})
    analysis_meta["prophylaxis"].setdefault("telemetry", {})
    structural_integrity = False
    structural_compromise_dynamic = False
    structural_compromise_static = False
    tactical_sensitivity = False
    initiative_exploitation = False
    initiative_attempt = False
    tension_creation = False
    neutral_tension_creation = False
    premature_attack = False
    constructive_maneuver = False
    neutral_maneuver = False
    misplaced_maneuver = False
    file_pressure_c_flag = False
    first_choice = False
    missed_tactic = False
    conversion_precision = False
    panic_move = False
    tactical_recovery = False
    maneuver_precision_score = 0.0
    maneuver_timing_score = 0.0
    behavior_scores: Dict[str, float] = {}
    plan_drop_result: Optional[PlanDropResult] = None

    delta_eval_cp = eval_best_cp - played_score_cp
    delta_eval_played_vs_before = played_score_cp - eval_before_cp
    delta_eval_float = delta_eval_played_vs_before / 100.0
    structure_gain = change_played_vs_before["structure"]
    tactics_gain = change_played_vs_before["tactics"]
    center_gain = change_played_vs_before["center_control"]

    tau = 1.0
    if eval_before >= 3.0:
        tau = min(WINNING_TAU_MAX, 1.0 + WINNING_TAU_SCALE * (eval_before - 3.0))
    elif eval_before <= -2.0:
        tau = max(LOSING_TAU_MIN, 1.0 + LOSING_TAU_SCALE * (eval_before + 2.0))

    effective_delta = delta_eval_float / max(tau, 1e-6)

    material_before = prepared.extra.get("material", {}).get("before")
    material_after = prepared.extra.get("material", {}).get("after")
    if material_before is None:
        material_before = 0.0
    if material_after is None:
        material_after = 0.0
    material_delta_self = round(material_after - material_before, 3)

    analysis_meta.setdefault("material", {})
    analysis_meta["material"].update(
        {
            "before": material_before,
            "after": material_after,
            "delta": material_delta_self,
        }
    )
    analysis_meta.setdefault("context", {})
    analysis_meta["context"].update(
        {
            "tau": round(tau, 3),
            "eval_before": eval_before,
            "eval_delta": delta_eval_float,
            "effective_delta": round(effective_delta, 3),
        }
    )

    intent_label = prepared.extra.get("intent_hint", {}).get("label")
    intent_signals = prepared.extra.get("intent_hint", {}).get("signals", {})
    if not intent_label:
        intent_label, intent_signals = infer_intent_hint(
            delta_self_mobility,
            delta_opp_mobility,
            change_played_vs_before["king_safety"],
            center_gain,
            contact_delta_played,
            delta_eval_float,
        )
    analysis_meta.setdefault("intent_hint", {})
    analysis_meta["intent_hint"].update({"label": intent_label, "signals": intent_signals})

    restriction_candidate = (
        intent_label == "restriction"
        and delta_opp_mobility <= -PLAN_DROP_OPP_MOBILITY_GATE
        and change_played_vs_before["king_safety"] >= 0.0
        and prepared.tactical_weight < 0.65
    )
    passive_candidate = (
        intent_label == "passive"
        and (
            delta_eval_float <= PASSIVE_PLAN_EVAL_DROP
            or (
                delta_self_mobility <= PASSIVE_PLAN_MOBILITY_SELF
                and delta_opp_mobility >= PASSIVE_PLAN_MOBILITY_OPP
            )
        )
        and prepared.tactical_weight < 0.65
    )
    plan_candidate = restriction_candidate or passive_candidate
    intent_meta = analysis_meta["intent_hint"]
    intent_meta["restriction_candidate"] = restriction_candidate
    intent_meta["passive_candidate"] = passive_candidate

    mover_piece = board.piece_at(played_move.from_square)
    is_pawn_move = bool(mover_piece and mover_piece.piece_type == chess.PAWN)
    is_center_pawn_push = bool(
        is_pawn_move
        and chess.square_file(played_move.to_square) in CENTER_FILES
        and chess.square_file(played_move.from_square) in CENTER_FILES
    )

    plan_meta = analysis_meta.setdefault("prophylaxis_plan", {})
    plan_meta.update(
        {
            "candidate": plan_candidate,
            "restriction": restriction_candidate,
            "passive": passive_candidate,
        }
    )

    if plan_candidate and PLAN_DROP_ENABLED:
        plan_drop_result = detect_prophylaxis_plan_drop(
            engine.identifier(),
            board,
            board.copy(stack=False),
            depth=PLAN_DROP_DEPTH,
            multipv=PLAN_DROP_MULTIPV,
            sample_rate=PLAN_DROP_SAMPLE_RATE,
            variance_cap=PLAN_DROP_VARIANCE_CAP,
            runtime_cap_ms=PLAN_DROP_RUNTIME_CAP_MS,
        )
        if plan_drop_result:
            plan_pass = (
                plan_drop_result.sampled
                and plan_drop_result.stable
                and plan_drop_result.psi >= PLAN_DROP_PSI_MIN
                and plan_drop_result.plan_loss >= PLAN_DROP_PLAN_LOSS_MIN
                and delta_eval_float >= PLAN_DROP_EVAL_CAP
                and "sample_skipped" not in plan_drop_result.reasons
            )
            plan_meta.update(
                {
                    "psi": plan_drop_result.psi,
                    "pei": plan_drop_result.pei,
                    "plan_loss": plan_drop_result.plan_loss,
                    "depth": plan_drop_result.depth,
                    "multipv": plan_drop_result.multipv,
                    "stable": plan_drop_result.stable,
                    "runtime_ms": plan_drop_result.runtime_ms,
                    "sampled": plan_drop_result.sampled,
                    "reasons": plan_drop_result.reasons,
                    "variance_before": plan_drop_result.variance_before,
                    "variance_after": plan_drop_result.variance_after,
                    "passed": plan_pass,
                }
            )
            if plan_pass and not prophylactic_move:
                prophylactic_move = True
            if plan_pass:
                plan_note = f"plan disruption: psi {plan_drop_result.psi:.2f}, loss {plan_drop_result.plan_loss:.2f}"
                if "prophylactic_move" in notes:
                    notes["prophylactic_move"] = f"{notes['prophylactic_move']} | {plan_note}"
                else:
                    notes["prophylactic_move"] = plan_note
                existing = notes.get("prophylaxis_type")
                if existing:
                    notes["prophylaxis_type"] = f"{existing} | {plan_note}"
                else:
                    notes["prophylaxis_type"] = plan_note
        else:
            plan_meta.setdefault("sampled", False)
            plan_meta.setdefault("passed", None)
    else:
        analysis_meta.setdefault("prophylaxis", {})
        plan_meta.setdefault("sampled", False)
        plan_meta.setdefault("passed", None)

    analysis_meta["prophylaxis"].setdefault(
        "components", {"preventive_score": 0.0, "self_safety_bonus": 0.0}
    )
    analysis_meta["prophylaxis"].setdefault("telemetry", {})
    analysis_meta["prophylaxis"]["telemetry"].setdefault("pattern_override", False)

    prophylaxis_quality = None
    telemetry = analysis_meta["prophylaxis"].setdefault("telemetry", {})
    components = analysis_meta["prophylaxis"].get("components", {})
    preventive_score = components.get("preventive_score", 0.0)
    signal_threshold = PROPHYLAXIS_CONFIG.preventive_trigger * 0.85
    has_prophylaxis_signal = (
        prophylactic_move
        or bool(telemetry.get("pattern_override"))
        or preventive_score >= signal_threshold
    )
    if has_prophylaxis_signal:
        pattern_override = bool(telemetry.get("pattern_override"))
        soft_weight = 1.0 / (1.0 + pow(2.718281828, -(effective_delta - SOFT_GATE_MIDPOINT) / SOFT_GATE_WIDTH))
        self_safety_bonus = components.get("self_safety_bonus", 0.0)
        threat_delta = components.get("threat_delta", 0.0)
        volatility_drop_cp = components.get("volatility_drop_cp", 0.0)
        adjusted_preventive = preventive_score
        if pattern_override and adjusted_preventive < PROPHYLAXIS_CONFIG.preventive_trigger:
            adjusted_preventive = PROPHYLAXIS_CONFIG.preventive_trigger
        quality, quality_score = classify_prophylaxis_quality(
            has_prophylaxis_signal,
            adjusted_preventive,
            effective_delta,
            prepared.tactical_weight,
            soft_weight,
            eval_before_cp=eval_before_cp,
            drop_cp=delta_eval_played_vs_before,
            threat_delta=threat_delta,
            volatility_drop=volatility_drop_cp,
            config=PROPHYLAXIS_CONFIG,
        )
        prophylaxis_quality = quality
        if plan_candidate and plan_meta.get("passed") is False:
            prophylaxis_quality = "prophylactic_meaningless"
            quality_score = 0.0
        elif plan_candidate and plan_meta.get("passed") and prophylaxis_quality == "prophylactic_latent":
            prophylaxis_quality = "prophylactic_direct"
            quality_score = max(quality_score, 0.8)
        if prophylaxis_quality:
            analysis_meta["prophylaxis"]["quality"] = prophylaxis_quality
            analysis_meta["prophylaxis"]["quality_score"] = quality_score
        else:
            analysis_meta["prophylaxis"].pop("quality", None)
            analysis_meta["prophylaxis"].pop("quality_score", None)
        analysis_meta["prophylaxis"]["components"].update(
            {
                "preventive_score": preventive_score,
                "self_safety_bonus": self_safety_bonus,
                "soft_weight": round(soft_weight, 3),
                "effective_delta": round(effective_delta, 3),
                "pattern_override": pattern_override,
                "threat_delta": threat_delta,
                "volatility_drop_cp": volatility_drop_cp,
            }
        )
    prophylaxis_quality = analysis_meta["prophylaxis"].get("quality")
    quality_score = analysis_meta["prophylaxis"].get("quality_score")
    if prophylaxis_quality and quality_score is not None:
        notes.setdefault(
            "prophylaxis_quality",
            f"{prophylaxis_quality} (score {quality_score:+.2f})",
        )

    # ... (additional legacy logic continues here, identical to original implementation)

    raise NotImplementedError("compute_tag_result copy incomplete")
