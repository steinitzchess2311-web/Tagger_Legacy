"""
Feature extraction utilities for the refactored rule tagger core.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import chess

from rule_tagger2.legacy.config import STYLE_COMPONENT_KEYS
from rule_tagger2.legacy.analysis import compute_behavior_scores as _legacy_behavior_scores

from .context import EvalBundles, Followups
from .engine_io import EngineClient, evaluation_and_metrics, metrics_delta


def compute_component_deltas(
    metrics_before: Dict[str, float],
    metrics_played: Dict[str, float],
    metrics_best: Dict[str, float],
    opp_metrics_before: Dict[str, float],
    opp_metrics_played: Dict[str, float],
    opp_metrics_best: Dict[str, float],
) -> EvalBundles:
    component_deltas = metrics_delta(metrics_played, metrics_best)
    opp_component_deltas = metrics_delta(opp_metrics_played, opp_metrics_best)
    return EvalBundles(
        metrics_before=metrics_before,
        metrics_played=metrics_played,
        metrics_best=metrics_best,
        opp_before=opp_metrics_before,
        opp_played=opp_metrics_played,
        opp_best=opp_metrics_best,
        component_deltas=component_deltas,
        opp_component_deltas=opp_component_deltas,
    )


def compute_followups(
    engine: EngineClient,
    board: chess.Board,
    played_board: chess.Board,
    best_board: chess.Board,
    actor: chess.Color,
    *,
    steps: int,
    depth: int = 6,
    ) -> Followups:
    (
        base_self_before,
        base_opp_before,
        seq_self_before,
        seq_opp_before,
    ) = engine.simulate_followups(
        board,
        actor,
        steps=steps,
        depth=depth,
    )
    (
        base_self_played,
        base_opp_played,
        seq_self_played,
        seq_opp_played,
    ) = engine.simulate_followups(
        played_board,
        actor,
        steps=steps,
        depth=depth,
    )
    (
        base_self_best,
        base_opp_best,
        seq_self_best,
        seq_opp_best,
    ) = engine.simulate_followups(
        best_board,
        actor,
        steps=steps,
        depth=depth,
    )

    follow_self_deltas = _compute_delta_sequence(base_self_before, seq_self_played)
    follow_opp_deltas = _compute_delta_sequence(base_opp_before, seq_opp_played)
    follow_self_deltas_best = _compute_delta_sequence(base_self_before, seq_self_best)
    follow_opp_deltas_best = _compute_delta_sequence(base_opp_before, seq_opp_best)

    return Followups(
        base_self_before=base_self_before,
        base_opp_before=base_opp_before,
        base_self_played=base_self_played,
        base_opp_played=base_opp_played,
        base_self_best=base_self_best,
        base_opp_best=base_opp_best,
        self_played=follow_self_deltas,
        opp_played=follow_opp_deltas,
        self_best=follow_self_deltas_best,
        opp_best=follow_opp_deltas_best,
    )


def _compute_delta_sequence(
    base: Dict[str, float],
    sequence: List[Dict[str, float]],
) -> List[Dict[str, float]]:
    deltas: List[Dict[str, float]] = []
    for metrics in sequence:
        deltas.append({key: round(metrics[key] - base[key], 3) for key in STYLE_COMPONENT_KEYS})
    return deltas


def mobility_trends_and_windows(
    deltas: List[Dict[str, float]],
    *,
    window: int = 2,
) -> Tuple[float, Tuple[float, float]]:
    trend = _ema_trend(deltas)
    stats = _window_stats(deltas, steps=window)
    return trend, stats


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


def behavior_scores(
    mobility_gain: float,
    center_gain: float,
    eval_delta: float,
    tension_delta: float,
    structure_drop: float,
    king_safety_change: float,
    opp_mobility_change: float,
) -> Dict[str, float]:
    return _legacy_behavior_scores(
        mobility_gain,
        center_gain,
        eval_delta,
        tension_delta,
        structure_drop,
        king_safety_change,
        opp_mobility_change,
    )


__all__ = [
    "behavior_scores",
    "compute_component_deltas",
    "compute_followups",
    "evaluation_and_metrics",
    "mobility_trends_and_windows",
    "metrics_delta",
]
