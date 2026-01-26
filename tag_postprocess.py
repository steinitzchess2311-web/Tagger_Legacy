"""Post-processing helpers that clean up and augment tag lists produced by rule_tagger."""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List

DEFAULT_FORCED_MOVE_THRESHOLD_CP = 180.0
FORCED_MOVE_THRESHOLD_ENV = "FORCED_MOVE_THRESHOLD_CP"
CONTEXT_EXCLUSIVE_TAGS = {"winning_position_handling", "losing_position_handling"}
BACKGROUND_NOISE_TAGS = {
    "prophylactic_move",
    "prophylactic_direct",
    "direct_prophylactic",
    "prophylactic_meaningless",
    "failed_prophylactic",
    "cod_plan_kill",
    "structural_compromise_static",
    "risk_avoidance",
    "tactical_sensitivity",
}
CONTROL_OVERRIDE_TAGS = {"initiative_attempt", "structural_compromise_dynamic"}
HIGH_PRIORITY_SEMANTIC_TAGS = {
    "structural_compromise_dynamic",
    "structural_compromise_forced",
    "positional_sacrifice",
    "positional_structure_sacrifice",
    "positional_space_sacrifice",
    "cod_king_safety_shell",
    "cod_file_seal",
    "cod_regroup_consolidate",
    "missed_tactic",
    "tactical_sensitivity",
}
MID_PRIORITY_SEMANTIC_TAGS = {
    "maneuver_opening",
    "neutral_maneuver",
    "constructive_maneuver",
    "constructive_maneuver_prepare",
}
MAX_BACKGROUND_WITH_MID_PRIORITY = 1


def _extract_engine_meta(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (
        analysis.get("analysis_context", {})
        .get("engine_meta", {})
        or {}
    )


def normalize_candidate_tags(tags: List[str], analysis: Dict[str, Any]) -> List[str]:
    """Deduplicate tags and apply special-case adjustments."""
    if not tags:
        return []

    seen: set[str] = set()
    normalized: List[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)

    engine_meta = _extract_engine_meta(analysis)
    normalized = _enforce_context_exclusivity(normalized, engine_meta)
    normalized = _apply_forced_move_tag(normalized, analysis)
    if normalized == ["forced_move"]:
        return normalized
    normalized = _add_dynamic_over_control(normalized, engine_meta)
    normalized = _ensure_cod_parent_tag(normalized)
    normalized = _apply_background_pruning(normalized)
    return normalized


def _enforce_context_exclusivity(tags: List[str], engine_meta: Dict[str, Any]) -> List[str]:
    """Ensure winning/losing labels stand alone when detected."""
    exclusive = [tag for tag in tags if tag in CONTEXT_EXCLUSIVE_TAGS]
    if exclusive:
        return exclusive
    label = engine_meta.get("context", {}).get("label")
    if label in CONTEXT_EXCLUSIVE_TAGS:
        return [label]
    return tags


def _add_dynamic_over_control(tags: List[str], engine_meta: Dict[str, Any]) -> List[str]:
    """Tag dynamic play that explicitly favors dynamic choices over control.

    Only applies when:
    1. Engine classifies move as "dynamic" (has_dynamic_in_band && played_kind == "dynamic")
    2. Move shows concrete tactical/aggressive characteristics:
       - Is a capture or gives check, OR
       - Shows significant volatility/contact increase, OR
       - Involves material sacrifice

    This prevents tagging quiet positional moves as "dynamic_over_control".
    """
    # Don't add dynamic_over_control if any control_over_dynamics tag is present
    # These should be mutually exclusive
    if "control_over_dynamics" in tags:
        return tags
    if any(tag.startswith("control_over_dynamics:") or tag.startswith("cod_") for tag in tags):
        return tags

    control_context = engine_meta.get("control_dynamics", {}).get("context", {}) or {}

    # Check engine-level dynamic classification
    has_dynamic_in_band = control_context.get("has_dynamic_in_band", False)
    played_kind = control_context.get("played_kind")

    if not (has_dynamic_in_band and played_kind == "dynamic"):
        return tags

    # Semantic filter: require concrete tactical/aggressive signals
    # Extract move characteristics from engine_meta
    is_capture = engine_meta.get("is_capture", False)
    gives_check = engine_meta.get("gives_check", False)

    # Extract volatility and contact changes
    volatility_delta = control_context.get("volatility_delta", 0.0)
    contact_delta = control_context.get("contact_delta", 0.0)

    # Extract eval drop (for sacrifice detection)
    eval_drop_cp = abs(engine_meta.get("drop_cp", 0))

    # Thresholds for semantic filtering (based on claude.md suggestions)
    DYNAMIC_DOC_VOLATILITY_GAIN = 0.15
    DYNAMIC_DOC_CONTACT_GAIN = 0.10
    DYNAMIC_DOC_SACRIFICE_CP = 80

    # Check if move has concrete dynamic characteristics
    is_tactical = is_capture or gives_check
    is_volatile = volatility_delta >= DYNAMIC_DOC_VOLATILITY_GAIN
    is_contact_increasing = contact_delta >= DYNAMIC_DOC_CONTACT_GAIN
    is_sacrifice = eval_drop_cp >= DYNAMIC_DOC_SACRIFICE_CP

    # Only tag if at least one concrete dynamic signal is present
    if is_tactical or is_volatile or is_contact_increasing or is_sacrifice:
        if "dynamic_over_control" not in tags:
            return tags + ["dynamic_over_control"]

    return tags


def _ensure_cod_parent_tag(tags: List[str]) -> List[str]:
    """Ensure control_over_dynamics parent tag is present when COD subtags exist."""
    # Check if any COD subtag exists (either new format control_over_dynamics:* or legacy cod_*)
    has_cod_subtype = any(
        tag.startswith("control_over_dynamics:") or tag.startswith("cod_")
        for tag in tags
    )

    if has_cod_subtype and "control_over_dynamics" not in tags:
        # Insert parent tag at the beginning to maintain logical order
        return ["control_over_dynamics"] + tags

    return tags


def _apply_background_pruning(tags: List[str]) -> List[str]:
    """Drop noise-heavy tags when a stronger semantic is already present."""
    if not tags:
        return tags
    filtered_tags: List[str] = []
    tag_set = set(tags)
    if tag_set & CONTROL_OVERRIDE_TAGS:
        return [
            tag
            for tag in tags
            if not (
                tag == "control_over_dynamics"
                or tag.startswith("control_over_dynamics:")
                or tag.startswith("cod_")
            )
        ]
    if tag_set & HIGH_PRIORITY_SEMANTIC_TAGS:
        return [tag for tag in tags if tag not in BACKGROUND_NOISE_TAGS]
    if tag_set & MID_PRIORITY_SEMANTIC_TAGS:
        background_kept = 0
        for tag in tags:
            if tag in BACKGROUND_NOISE_TAGS:
                if background_kept >= MAX_BACKGROUND_WITH_MID_PRIORITY:
                    continue
                background_kept += 1
            filtered_tags.append(tag)
        return filtered_tags
    return tags


def _is_played_move_best(analysis: Dict[str, Any]) -> bool:
    eval_info = analysis.get("eval") or {}
    best = eval_info.get("best")
    played = eval_info.get("played")
    if best is None or played is None:
        return False
    return math.isclose(float(best), float(played), abs_tol=1e-6)


def _apply_forced_move_tag(tags: List[str], analysis: Dict[str, Any]) -> List[str]:
    engine_meta = _extract_engine_meta(analysis)
    score_gap = float(engine_meta.get("score_gap_cp") or 0.0)
    if score_gap < DEFAULT_FORCED_MOVE_THRESHOLD_CP:
        return tags
    if not _is_played_move_best(analysis):
        return tags
    return ["forced_move"]


def _load_forced_move_threshold(threshold_cp: float | None = None) -> float:
    if threshold_cp is not None:
        return threshold_cp
    env_value = os.getenv(FORCED_MOVE_THRESHOLD_ENV)
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            pass
    return DEFAULT_FORCED_MOVE_THRESHOLD_CP


def apply_forced_move_tag(
    candidates: List[Dict[str, Any]],
    *,
    picked_uci: str | None = None,
    threshold_cp: float | None = None,
) -> List[str] | None:
    """Tag the picked move as forced when the eval gap is wide."""
    if len(candidates) < 2 or not picked_uci:
        return None
    threshold = _load_forced_move_threshold(threshold_cp)
    scored: List[tuple[float, Dict[str, Any]]] = []
    for candidate in candidates:
        sf_eval = candidate.get("sf_eval")
        try:
            score = float(sf_eval if sf_eval is not None else 0.0)
        except (TypeError, ValueError):
            continue
        scored.append((score, candidate))
    if len(scored) < 2:
        return None
    scored.sort(key=lambda entry: entry[0], reverse=True)
    best_eval, best_candidate = scored[0]
    second_eval = scored[1][0]
    if best_eval - second_eval < threshold:
        return None
    if best_candidate.get("uci") != picked_uci:
        return None
    best_candidate["tags"] = ["forced_move"]
    return best_candidate["tags"]


__all__ = [
    "apply_forced_move_tag",
    "normalize_candidate_tags",
    "DEFAULT_FORCED_MOVE_THRESHOLD_CP",
    "FORCED_MOVE_THRESHOLD_ENV",
]
