"""
Aggregate feature construction for the staged pipeline.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import chess

from rule_tagger2.legacy.analysis import (
    detect_risk_avoidance,
    infer_intent_hint,
)
from rule_tagger2.legacy.config import STYLE_COMPONENT_KEYS
from rule_tagger2.legacy.engine import (
    contact_profile,
    defended_square_count,
    evaluation_and_metrics,
    material_balance,
    metrics_delta,
)
from rule_tagger2.legacy.move_utils import classify_move

from ..engine import EngineClient
from ..models import EngineCandidates, FeatureBundle
from .maneuver import evaluate_maneuver_metrics
from .structure import mobility_delta, structure_delta
from .tactical_weight import compute_tactical_weight


def _compute_delta_sequence(
    base: Dict[str, float],
    sequence: List[Dict[str, float]],
) -> List[Dict[str, float]]:
    deltas: List[Dict[str, float]] = []
    for metrics in sequence:
        deltas.append({key: round(metrics[key] - base[key], 3) for key in STYLE_COMPONENT_KEYS})
    return deltas


def _ema_trend(deltas: List[Dict[str, float]]) -> float:
    if not deltas:
        return 0.0
    weights = [0.6, 0.3, 0.1][: len(deltas)]
    total = sum(weights)
    trend = sum(w * deltas[idx]["mobility"] for idx, w in enumerate(weights))
    return trend / total if total else 0.0


def _window_stats(deltas: List[Dict[str, float]], steps: int = 2) -> Tuple[float, float]:
    if len(deltas) < steps:
        return 0.0, 0.0
    window = deltas[:steps]
    values = [abs(entry["mobility"]) for entry in window]
    mean = sum(values) / len(values)
    variance = sum((val - mean) ** 2 for val in values) / len(values)
    return mean, variance


def build_feature_bundle(
    fen: str,
    played_move_uci: str,
    engine_out: EngineCandidates,
    *,
    engine_client: EngineClient,
    cp_threshold: int,
    eval_depth: int,
    followup_depth: int,
    followup_steps: int,
) -> FeatureBundle:
    board = chess.Board(fen)
    actor = board.turn
    played_move = chess.Move.from_uci(played_move_uci)
    if played_move not in board.legal_moves:
        raise ValueError(f"Illegal move {played_move_uci} for position {fen}")

    best_move = engine_out.best().move
    best_is_forcing = board.is_capture(best_move) or board.gives_check(best_move)
    played_is_forcing = board.is_capture(played_move) or board.gives_check(played_move)

    played_score_cp = None
    played_kind = classify_move(board, played_move)

    for candidate in engine_out.candidates:
        if candidate.move == played_move:
            played_score_cp = candidate.score_cp
            played_kind = candidate.kind
            break

    if played_score_cp is None or (engine_out.best().score_cp - played_score_cp) > cp_threshold:
        played_score_cp = engine_client.eval_move(
            fen,
            played_move_uci,
            depth=eval_depth,
        )

    best_board = board.copy(stack=False)
    best_board.push(best_move)
    played_board = board.copy(stack=False)
    played_board.push(played_move)

    metrics_before, opp_metrics_before, evaluation_before = evaluation_and_metrics(board, actor)
    metrics_played, opp_metrics_played, evaluation_played = evaluation_and_metrics(played_board, actor)
    metrics_best, opp_metrics_best, evaluation_best = evaluation_and_metrics(best_board, actor)

    component_deltas = metrics_delta(metrics_played, metrics_best)
    opp_component_deltas = metrics_delta(opp_metrics_played, opp_metrics_best)
    change_played_vs_before = metrics_delta(metrics_before, metrics_played)
    opp_change_played_vs_before = metrics_delta(opp_metrics_before, opp_metrics_played)

    material_before = material_balance(board, actor)
    material_after = material_balance(played_board, actor)
    material_delta_self = round(material_after - material_before, 3)

    coverage_before = defended_square_count(board, actor)
    coverage_after = defended_square_count(played_board, actor)
    coverage_delta = coverage_after - coverage_before

    contact_ratio_before, _, _, _ = contact_profile(board)
    contact_ratio_played, _, _, _ = contact_profile(played_board)
    contact_ratio_best, _, _, _ = contact_profile(best_board)
    contact_delta_played = contact_ratio_played - contact_ratio_before
    contact_delta_best = contact_ratio_best - contact_ratio_before

    delta_eval_cp = engine_out.best().score_cp - played_score_cp
    eval_before_cp = engine_out.eval_before_cp
    eval_best_cp = engine_out.best().score_cp
    eval_played_cp = played_score_cp

    delta_eval_played_vs_before = eval_played_cp - eval_before_cp
    delta_eval_float = round(delta_eval_played_vs_before / 100.0, 3)

    delta_tactics_best_vs_before = (
        evaluation_best["components"]["tactics"] - evaluation_before["components"]["tactics"]
    )
    delta_structure_best_vs_before = (
        evaluation_best["components"]["structure"] - evaluation_before["components"]["structure"]
    )

    tactical_weight = compute_tactical_weight(
        delta_eval_cp,
        delta_tactics_best_vs_before,
        delta_structure_best_vs_before,
        engine_out.analysis_meta.get("depth_jump_cp", 0),
        engine_out.analysis_meta.get("deepening_gain_cp", 0),
        engine_out.analysis_meta.get("score_gap_cp", 0),
        engine_out.analysis_meta.get("contact_ratio", contact_ratio_before),
        engine_out.analysis_meta.get("phase_ratio", 1.0),
        best_is_forcing,
        played_is_forcing,
        engine_out.analysis_meta.get("mate_threat", False),
    )

    base_self_before, base_opp_before, seq_self_before, seq_opp_before = engine_client.simulate_followup(
        fen,
        actor,
        steps=followup_steps,
        depth=followup_depth,
    )
    base_self_played, base_opp_played, seq_self_played, seq_opp_played = engine_client.simulate_followup(
        played_board.fen(),
        actor,
        steps=followup_steps,
        depth=followup_depth,
    )
    base_self_best, base_opp_best, seq_self_best, seq_opp_best = engine_client.simulate_followup(
        best_board.fen(),
        actor,
        steps=followup_steps,
        depth=followup_depth,
    )

    follow_self_deltas = _compute_delta_sequence(base_self_before, seq_self_played)
    follow_opp_deltas = _compute_delta_sequence(base_opp_before, seq_opp_played)
    follow_self_deltas_best = _compute_delta_sequence(base_self_before, seq_self_best)
    follow_opp_deltas_best = _compute_delta_sequence(base_opp_before, seq_opp_best)

    self_trend = _ema_trend(follow_self_deltas)
    opp_trend = _ema_trend(follow_opp_deltas)
    self_trend_best = _ema_trend(follow_self_deltas_best)
    opp_trend_best = _ema_trend(follow_opp_deltas_best)

    follow_window_mean, follow_window_var = _window_stats(follow_self_deltas)

    dest_structure_delta = structure_delta(metrics_before, metrics_played)
    dest_mobility_delta = mobility_delta(metrics_before, metrics_played)
    risk_avoid = detect_risk_avoidance(
        change_played_vs_before.get("king_safety", 0.0),
        abs(delta_eval_float),
        opp_change_played_vs_before.get("tactics", 0.0),
        contact_delta_played,
    )

    intent_label, intent_signals = infer_intent_hint(
        change_played_vs_before.get("mobility", 0.0),
        opp_change_played_vs_before.get("mobility", 0.0),
        change_played_vs_before.get("king_safety", 0.0),
        change_played_vs_before.get("center_control", 0.0),
        contact_delta_played,
        delta_eval_float,
    )

    extra = {
        "played_kind": played_kind,
        "best_kind": classify_move(board, best_move),
        "material": {
            "before": material_before,
            "after": material_after,
            "delta_self": material_delta_self,
        },
        "coverage": {
            "before": coverage_before,
            "after": coverage_after,
            "delta": coverage_delta,
        },
        "contact": {
            "before": round(contact_ratio_before, 3),
            "played": round(contact_ratio_played, 3),
            "best": round(contact_ratio_best, 3),
            "delta_played": round(contact_delta_played, 3),
            "delta_best": round(contact_delta_best, 3),
        },
        "followup": {
            "self_deltas": follow_self_deltas,
            "opp_deltas": follow_opp_deltas,
            "self_deltas_best": follow_self_deltas_best,
            "opp_deltas_best": follow_opp_deltas_best,
            "self_trend": round(self_trend, 3),
            "opp_trend": round(opp_trend, 3),
            "self_trend_best": round(self_trend_best, 3),
            "opp_trend_best": round(opp_trend_best, 3),
            "window_mean": round(follow_window_mean, 3),
            "window_var": round(follow_window_var, 3),
        },
        "risk_avoidance": risk_avoid,
        "intent_hint": {
            "label": intent_label,
            "signals": intent_signals,
        },
        "delta_played_vs_before": change_played_vs_before,
        "opp_delta_played_vs_before": opp_change_played_vs_before,
    }

    analysis_meta = dict(engine_out.analysis_meta)
    analysis_meta.update(
        {
            "played_kind": played_kind,
            "best_kind": extra["best_kind"],
            "eval_before_cp": eval_before_cp,
            "eval_played_cp": eval_played_cp,
            "eval_best_cp": eval_best_cp,
            "delta_eval_cp": delta_eval_cp,
            "delta_eval_float": delta_eval_float,
            "contact_delta_played": contact_delta_played,
            "contact_delta_best": contact_delta_best,
            "follow_trends": {
                "self": self_trend,
                "opp": opp_trend,
                "self_best": self_trend_best,
                "opp_best": opp_trend_best,
            },
            "risk_avoidance": risk_avoid,
            "intent_hint": extra["intent_hint"],
        }
    )

    return FeatureBundle(
        fen=fen,
        played_move=played_move,
        best_move=best_move,
        tactical_weight=tactical_weight,
        metrics_before=metrics_before,
        metrics_played=metrics_played,
        metrics_best=metrics_best,
        opp_metrics_before=opp_metrics_before,
        opp_metrics_played=opp_metrics_played,
        opp_metrics_best=opp_metrics_best,
        change_played_vs_before=change_played_vs_before,
        opp_change_played_vs_before=opp_change_played_vs_before,
        evaluation_before=evaluation_before,
        evaluation_played=evaluation_played,
        evaluation_best=evaluation_best,
        component_deltas=component_deltas,
        opp_component_deltas=opp_component_deltas,
        analysis_meta=analysis_meta,
        extra=extra,
    )
