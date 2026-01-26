"""
Shared datamodels reused across the refactored core.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess

from rule_tagger2.legacy.config import STYLE_COMPONENT_KEYS


@dataclass
class Candidate:
    move: chess.Move
    score_cp: int
    kind: str


@dataclass
class TagResult:
    played_move: str
    played_kind: str
    best_move: str
    best_kind: str
    eval_before: float
    eval_played: float
    eval_best: float
    delta_eval: float
    control_over_dynamics: bool
    control_over_dynamics_subtype: Optional[str]
    cod_simplify: bool
    cod_plan_kill: bool
    cod_freeze_bind: bool
    cod_blockade_passed: bool
    cod_file_seal: bool
    cod_king_safety_shell: bool
    cod_space_clamp: bool
    cod_regroup_consolidate: bool
    cod_slowdown: bool
    control_simplify: bool
    control_plan_kill: bool
    control_freeze_bind: bool
    control_blockade_passed: bool
    control_file_seal: bool
    control_king_safety_shell: bool
    control_space_clamp: bool
    control_regroup_consolidate: bool
    control_slowdown: bool
    control_schema_version: int
    deferred_initiative: bool
    risk_avoidance: bool
    structural_integrity: bool
    structural_compromise_dynamic: bool
    structural_compromise_static: bool
    tactical_sensitivity: bool
    prophylactic_move: bool
    prophylaxis_score: float
    initiative_exploitation: bool
    initiative_attempt: bool
    tension_creation: bool
    neutral_tension_creation: bool
    premature_attack: bool
    constructive_maneuver: bool
    constructive_maneuver_prepare: bool
    neutral_maneuver: bool
    misplaced_maneuver: bool
    maneuver_opening: bool
    opening_central_pawn_move: bool
    opening_rook_pawn_move: bool
    tactical_sacrifice: bool
    positional_sacrifice: bool
    inaccurate_tactical_sacrifice: bool
    speculative_sacrifice: bool
    desperate_sacrifice: bool
    tactical_combination_sacrifice: bool
    tactical_initiative_sacrifice: bool
    positional_structure_sacrifice: bool
    positional_space_sacrifice: bool
    file_pressure_c: bool
    first_choice: bool
    missed_tactic: bool
    conversion_precision: bool
    panic_move: bool
    tactical_recovery: bool
    accurate_knight_bishop_exchange: bool
    inaccurate_knight_bishop_exchange: bool
    bad_knight_bishop_exchange: bool
    failed_prophylactic: bool
    metrics_before: Dict[str, float]
    metrics_played: Dict[str, float]
    metrics_best: Dict[str, float]
    component_deltas: Dict[str, float]
    opp_metrics_before: Dict[str, float]
    opp_metrics_played: Dict[str, float]
    opp_metrics_best: Dict[str, float]
    opp_component_deltas: Dict[str, float]
    coverage_delta: int
    tactical_weight: float
    mode: str
    analysis_context: Dict[str, Any]
    notes: Dict[str, str]
    maneuver_precision_score: float
    maneuver_timing_score: float
    prepare_quality_score: float
    prepare_consensus_score: float


TAG_PRIORITY = {
    "initiative_exploitation": 1,
    "initiative_attempt": 2,
    "file_pressure_c": 3,
    "tension_creation": 4,
    "neutral_tension_creation": 5,
    "premature_attack": 6,
    "constructive_maneuver": 7,
    "constructive_maneuver_prepare": 7,
    "neutral_maneuver": 8,
    "misplaced_maneuver": 9,
    "maneuver_opening": 9,
    "opening_central_pawn_move": 9,
    "opening_rook_pawn_move": 9,
    "tactical_sacrifice": 10,
    "positional_sacrifice": 10,
    "inaccurate_tactical_sacrifice": 11,
    "speculative_sacrifice": 12,
    "desperate_sacrifice": 13,
    "tactical_combination_sacrifice": 14,
    "tactical_initiative_sacrifice": 14,
    "positional_structure_sacrifice": 15,
    "positional_space_sacrifice": 15,
    "prophylactic_move": 10,
    "prophylactic_direct": 10,
    "prophylactic_latent": 11,
    "prophylactic_meaningless": 12,
    "structural_blockage": 13,
    "control_over_dynamics": 14,
    "cod_simplify": 14,
    "cod_plan_kill": 14,
    "cod_freeze_bind": 14,
    "cod_blockade_passed": 14,
    "cod_file_seal": 14,
    "cod_king_safety_shell": 14,
    "cod_space_clamp": 14,
    "cod_regroup_consolidate": 14,
    "cod_slowdown": 14,
    "control_simplify": 15,
    "control_plan_kill": 15,
    "control_freeze_bind": 15,
    "control_blockade_passed": 15,
    "control_file_seal": 15,
    "control_king_safety_shell": 15,
    "control_space_clamp": 15,
    "control_regroup_consolidate": 15,
    "control_slowdown": 15,
    "deferred_initiative": 15,
    "risk_avoidance": 16,
    "structural_compromise_dynamic": 17,
    "structural_compromise_static": 18,
    "structural_integrity": 19,
    "tactical_sensitivity": 20,
    "first_choice": 21,
    "missed_tactic": 22,
    "conversion_precision": 23,
    "panic_move": 24,
    "tactical_recovery": 25,
    "accurate_knight_bishop_exchange": 20,
    "inaccurate_knight_bishop_exchange": 21,
    "bad_knight_bishop_exchange": 22,
    "failed_prophylactic": 12,
}


TENSION_TRIGGER_PRIORITY = {
    "contact_direct": 1,
    "contact_comp": 2,
    "symmetry_core": 3,
    "structural_support": 4,
    "delayed_trend": 5,
}


@dataclass
class StyleTracker:
    totals: Dict[str, float] = field(default_factory=lambda: {key: 0.0 for key in STYLE_COMPONENT_KEYS})
    count: int = 0

    def update(self, snapshot: Dict[str, float]) -> None:
        self.count += 1
        for key in STYLE_COMPONENT_KEYS:
            self.totals[key] += snapshot.get(key, 0.0)

    def profile(self) -> Dict[str, float]:
        if self.count == 0:
            return {key: 0.0 for key in STYLE_COMPONENT_KEYS}
        return {key: round(self.totals[key] / self.count, 3) for key in STYLE_COMPONENT_KEYS}


__all__ = [
    "Candidate",
    "StyleTracker",
    "TAG_PRIORITY",
    "TENSION_TRIGGER_PRIORITY",
    "TagResult",
]
