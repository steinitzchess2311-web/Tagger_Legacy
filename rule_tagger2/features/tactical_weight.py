"""
Tactical weighting helpers for the staged pipeline.
"""
from __future__ import annotations

from rule_tagger2.legacy.analysis import compute_tactical_weight as _legacy_compute


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
    """Thin wrapper over the legacy tactical weight computation."""

    return _legacy_compute(
        delta_eval_cp,
        delta_tactics,
        delta_structure,
        depth_jump_cp,
        deepening_gain_cp,
        score_gap_cp,
        contact_ratio,
        phase_ratio,
        best_is_forcing,
        played_is_forcing,
        mate_threat,
    )
