"""
Utilities for preparing analysis state from feature bundles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import chess

from ..models import EngineCandidates, FeatureBundle


@dataclass(frozen=True)
class PreparedData:
    fen: str
    board: chess.Board
    actor: chess.Color
    played_move: chess.Move
    tactical_weight: float
    best_move: chess.Move
    best_candidate: EngineMove
    in_band: List[EngineMove]
    played_score_cp: int
    played_kind: str
    eval_before_cp: int
    eval_played_cp: int
    eval_best_cp: int
    metrics_before: Dict[str, float]
    metrics_played: Dict[str, float]
    metrics_best: Dict[str, float]
    opp_metrics_before: Dict[str, float]
    opp_metrics_played: Dict[str, float]
    opp_metrics_best: Dict[str, float]
    evaluation_before: Dict[str, Any]
    evaluation_played: Dict[str, Any]
    evaluation_best: Dict[str, Any]
    component_deltas: Dict[str, float]
    change_played_vs_before: Dict[str, float]
    opp_component_deltas: Dict[str, float]
    opp_change_played_vs_before: Dict[str, float]
    coverage_before: int
    coverage_after: int
    coverage_delta: int
    has_dynamic_in_band: bool
    contacts: Dict[str, float]
    followup: Dict[str, any]
    analysis_meta: Dict[str, Any]
    extra: Dict[str, Any]
    engine_out: EngineCandidates


def build_prepared_data(
    engine_out: EngineCandidates,
    features: FeatureBundle,
    *,
    cp_threshold: int,
) -> PreparedData:
    board = chess.Board(features.fen)
    actor = board.turn
    best_candidate = engine_out.best()
    in_band = [move for move in engine_out.candidates if (best_candidate.score_cp - move.score_cp) <= cp_threshold]

    analysis_meta = dict(features.analysis_meta)
    played_kind = analysis_meta.get("played_kind", "unknown")
    eval_before_cp = analysis_meta.get("eval_before_cp", engine_out.eval_before_cp)
    eval_played_cp = analysis_meta.get("eval_played_cp")
    if eval_played_cp is None:
        for move in engine_out.candidates:
            if move.move == features.played_move:
                eval_played_cp = move.score_cp
                break
        else:
            eval_played_cp = best_candidate.score_cp
    eval_best_cp = analysis_meta.get("eval_best_cp", best_candidate.score_cp)

    contacts = features.extra.get("contact", {})
    followup = features.extra.get("followup", {})

    return PreparedData(
        fen=features.fen,
        board=board,
        actor=actor,
        played_move=features.played_move,
        tactical_weight=features.tactical_weight,
        best_move=features.best_move,
        best_candidate=best_candidate,
        in_band=in_band,
        played_score_cp=eval_played_cp,
        played_kind=played_kind,
        eval_before_cp=eval_before_cp,
        eval_played_cp=eval_played_cp,
        eval_best_cp=eval_best_cp,
        metrics_before=features.metrics_before,
        metrics_played=features.metrics_played,
        metrics_best=features.metrics_best,
        opp_metrics_before=features.opp_metrics_before,
        opp_metrics_played=features.opp_metrics_played,
        opp_metrics_best=features.opp_metrics_best,
        evaluation_before=features.evaluation_before,
        evaluation_played=features.evaluation_played,
        evaluation_best=features.evaluation_best,
        component_deltas=features.component_deltas,
        change_played_vs_before=features.change_played_vs_before,
        opp_component_deltas=features.opp_component_deltas,
        opp_change_played_vs_before=features.opp_change_played_vs_before,
        coverage_before=features.extra.get("coverage", {}).get("before", 0),
        coverage_after=features.extra.get("coverage", {}).get("after", 0),
        coverage_delta=features.extra.get("coverage", {}).get("delta", 0),
        has_dynamic_in_band=any(move.kind == "dynamic" for move in in_band),
        contacts=contacts,
        followup=followup,
        analysis_meta=analysis_meta,
        extra=features.extra,
        engine_out=engine_out,
    )
