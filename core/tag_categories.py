"""
Utility helpers for mapping fine-grained tags to scoring categories.

The scoring kernel consumes this module to figure out which category
each tag belongs to, so we keep the mapping in a dedicated place
instead of sprinkling it across the scoring code.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, Mapping

# Granular tag → category mapping. Only tags that influence the
# scoring kernel need to be enumerated here; anything not present
# falls back to "misc".
_TAG_TO_CATEGORY: Dict[str, str] = {
    # Prophylaxis
    "soft_success_piece_prophylactic": "prophylaxis",
    "failed_eval_piece_prophylactic": "prophylaxis",
    "failed_blocked_piece_prophylactic": "prophylaxis",
    "strong_structure_reinforcement": "prophylaxis",
    "strong_threat_neutralization": "prophylaxis",
    "deferred_initiative.masking_delay": "prophylaxis",

    # Maneuver
    "latent_active_maneuver": "maneuver",
    "latent_restrictive_maneuver": "maneuver",
    "failed_direction_maneuver": "maneuver",
    "failed_direction_maneuver.temporary": "maneuver",
    "failed_direction_maneuver.strategic": "maneuver",
    "failed_direction_maneuver.true": "maneuver",
    "failed_blocked_maneuver": "maneuver",
    "failed_blocked_maneuver.temporary": "maneuver",
    "failed_blocked_maneuver.strategic": "maneuver",
    "failed_redundant_maneuver": "maneuver",
    "failed_redundant_maneuver.temporary": "maneuver",
    "regroup_intentional": "maneuver",
    "regroup_forced": "maneuver",
    "failed_maneuver": "maneuver",
    "failed_maneuver.temporary": "maneuver",
    "failed_maneuver.strategic": "maneuver",
    "failed_maneuver.true": "maneuver",

    # Intent
    "intent_defensive": "intent",
    "intent_resigned": "intent",
    "intent_spatial_restriction": "intent",
    "intent_threat_restriction": "intent",
    "intent_attack_initiation": "intent",
    "intent_spatial_expansion": "intent",

    # Initiative
    "initiative_calculated_attempt": "initiative",
    "initiative_speculative_attempt": "initiative",
    "delayed_initiative_preparatory": "initiative",
    "delayed_initiative_misread": "initiative",

    # Tension
    "neutral_tension_creation": "tension",
    "tension_creation_positional": "tension",
    "tension_creation_tactical": "tension",
    "premature_tension": "tension",

    # Exchange
    "equal_exchange_accuracy": "exchange",
    "favorable_exchange_accuracy": "exchange",
    "exchange_misvaluation": "exchange",
    "exchange_mistiming": "exchange",

    # Sacrifice
    "positional_structure_sacrifice": "sacrifice",
    "positional_space_sacrifice": "sacrifice",
    "tactical_combination_sacrifice": "sacrifice",
    "tactical_initiative_sacrifice": "sacrifice",
    "speculative_sacrifice": "sacrifice",
    "desperate_sacrifice": "sacrifice",

    # Structural
    "structural_stability": "structural",
    "structural_control": "structural",
    "structural_tradeoff_dynamic": "structural",
    "structural_collapse_dynamic": "structural",

    # Meta / tactical hygiene
    "missed_tactic": "meta",
    "conversion_precision": "meta",
    "tactical_sensitivity": "meta",
}

_CATEGORY_DEFAULT = "misc"


def tag_category(tag: str) -> str:
    """Return the scoring category associated with a tag."""
    return _TAG_TO_CATEGORY.get(tag, _CATEGORY_DEFAULT)


def group_tags(tags: Iterable[str]) -> Dict[str, list[str]]:
    """
    Group a collection of tags by their categories.

    This is used in reporting code when we want to show the dominant
    contributors per category.
    """
    grouped: Dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        grouped[tag_category(tag)].append(tag)
    return grouped


def categories() -> Mapping[str, Iterable[str]]:
    """Expose the full category → tags mapping."""
    inverse: Dict[str, list[str]] = defaultdict(list)
    for tag, category in _TAG_TO_CATEGORY.items():
        inverse[category].append(tag)
    return inverse
