"""
Scoring kernel for aggregating fine-grained tag distributions.

The kernel consumes:
  • config/tag_weights_v9.json          → base weights & penalties
  • config/style_templates.json         → style-specific multipliers
  • core/tag_categories.py              → tag → category mapping
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Tuple, Union

from core.tag_categories import tag_category

REPO_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = REPO_ROOT / "config" / "tag_weights_v9.json"
STYLE_TEMPLATES_PATH = REPO_ROOT / "config" / "style_templates.json"

StyleMix = Mapping[str, float]


@dataclass(frozen=True)
class TagContribution:
    tag: str
    category: str
    ratio: float
    base_weight: float
    style_multiplier: float
    contribution: float


def _load_json(path: Path) -> MutableMapping[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache()
def load_tag_weights(path: Path = WEIGHTS_PATH) -> Dict[str, object]:
    payload = _load_json(path)
    # basic sanity: ensure keys exist
    payload.setdefault("weights", {})
    payload.setdefault("penalties", {})
    payload.setdefault("defaults", {})
    return payload


@lru_cache()
def load_style_templates(path: Path = STYLE_TEMPLATES_PATH) -> Dict[str, object]:
    return _load_json(path)


def _normalise_mix(style: Union[str, StyleMix], templates: Mapping[str, object]) -> Dict[str, float]:
    if isinstance(style, str):
        return {style: 1.0}
    mix = {name: float(weight) for name, weight in style.items() if float(weight) > 0}
    if not mix:
        return {"BalancedModel": 1.0}
    total = sum(mix.values())
    if total == 0:
        return {"BalancedModel": 1.0}
    # remove unknown styles gracefully
    cleaned: Dict[str, float] = {}
    for name, weight in mix.items():
        if name in templates:
            cleaned[name] = weight / total
    return cleaned or {"BalancedModel": 1.0}


def build_style_multipliers(
    style: Union[str, StyleMix],
    *,
    templates: Mapping[str, object] | None = None,
    base_weights: Mapping[str, float] | None = None,
) -> Dict[str, float]:
    """
    Produce per-tag multipliers based on the chosen style mix.
    Returns a dict[tag] → multiplier.
    """
    templates = templates or load_style_templates()
    base_weights = base_weights or load_tag_weights()["weights"]

    style_mix = _normalise_mix(style, templates)
    multipliers: Dict[str, float] = {tag: 0.0 for tag in base_weights}

    for style_name, weight in style_mix.items():
        template = templates.get(style_name) or templates.get("BalancedModel", {})
        category_multipliers = template.get("category_multipliers", {})
        default_multiplier = category_multipliers.get("default", 1.0)
        tag_overrides = template.get("tag_overrides", {})

        for tag in multipliers:
            category = tag_category(tag)
            mult = category_multipliers.get(category, default_multiplier)
            mult *= tag_overrides.get(tag, 1.0)
            multipliers[tag] += mult * weight

    return multipliers


_NEUTRAL_TAGS: Tuple[str, ...] = (
    "intent_neutral",
    "neutral_maneuver",
    "neutral_exchange_accuracy",
    "neutral_tension_creation",
)

_REDUNDANT_FAILURE_TAGS: Tuple[str, ...] = (
    "failed_maneuver",
    "failed_piece_move_prophylactic",
    "failed_pawn_move_prophylactic",
)

_FAILURE_SEVERITY_SUFFIXES: Tuple[str, ...] = (".temporary", ".strategic", ".true")


def collapse_failure_severity(tag_ratios: Mapping[str, float]) -> Dict[str, float]:
    """
    Reduce failure severity variants back to their base tags.
    Only the `.true` portion is treated as a scoring penalty.
    """
    collapsed: Dict[str, float] = {tag: float(ratio) for tag, ratio in tag_ratios.items()}
    severity_groups: Dict[str, Dict[str, float]] = {}

    for tag, ratio in tag_ratios.items():
        for suffix in _FAILURE_SEVERITY_SUFFIXES:
            if tag.endswith(suffix):
                base = tag[: -len(suffix)]
                severity_groups.setdefault(base, {})[suffix] = float(ratio)
                break

    for base, group in severity_groups.items():
        collapsed[base] = group.get(".true", 0.0)

    for tag in list(collapsed):
        if any(tag.endswith(suffix) for suffix in _FAILURE_SEVERITY_SUFFIXES):
            collapsed.pop(tag, None)

    return collapsed


def _clamp(value: float, floor: float, ceiling: float) -> float:
    if value < floor:
        return floor
    if value > ceiling:
        return ceiling
    return value


def compute_penalties(
    tag_ratios: Mapping[str, float],
    penalties_cfg: Mapping[str, float],
) -> Dict[str, float]:
    neutral_penalty = penalties_cfg.get("neutral", 0.0) * sum(tag_ratios.get(tag, 0.0) for tag in _NEUTRAL_TAGS)
    redundant_penalty = penalties_cfg.get("redundant", 0.0) * sum(tag_ratios.get(tag, 0.0) for tag in _REDUNDANT_FAILURE_TAGS)
    return {
        "neutral_penalty": neutral_penalty,
        "redundant_penalty": redundant_penalty,
        "total_penalty": neutral_penalty + redundant_penalty,
    }


def compute_performance(
    tag_ratios: Mapping[str, float],
    *,
    style: Union[str, StyleMix] = "BalancedModel",
    weights_path: Path = WEIGHTS_PATH,
    templates_path: Path = STYLE_TEMPLATES_PATH,
) -> Dict[str, object]:
    """
    Compute aggregate performance under the given style mix.
    Returns a dictionary containing raw score, normalised percent,
    estimated Elo, penalty breakdown and detailed tag contributions.
    """
    weights_payload = load_tag_weights(weights_path)
    base_weights: Mapping[str, float] = weights_payload["weights"]  # type: ignore[index]
    penalties_cfg: Mapping[str, float] = weights_payload["penalties"]  # type: ignore[index]
    defaults_cfg: Mapping[str, float] = weights_payload["defaults"]  # type: ignore[index]

    templates = load_style_templates(templates_path)
    style_multipliers = build_style_multipliers(style, templates=templates, base_weights=base_weights)

    effective_ratios = collapse_failure_severity(tag_ratios)

    contributions: list[TagContribution] = []
    raw_score = 0.0
    for tag, weight in base_weights.items():
        ratio = float(effective_ratios.get(tag, 0.0))
        if ratio == 0.0 or weight == 0.0:
            continue
        style_multiplier = style_multipliers.get(tag, 1.0)
        contribution = ratio * weight * style_multiplier
        raw_score += contribution
        contributions.append(
            TagContribution(
                tag=tag,
                category=tag_category(tag),
                ratio=ratio,
                base_weight=weight,
                style_multiplier=style_multiplier,
                contribution=contribution,
            )
        )

    penalty_payload = compute_penalties(effective_ratios, penalties_cfg)
    net_score = raw_score - penalty_payload["total_penalty"]

    score_floor = float(defaults_cfg.get("score_floor", -1.0))
    score_ceiling = float(defaults_cfg.get("score_ceiling", 1.0))
    span = score_ceiling - score_floor if score_ceiling != score_floor else 1.0
    normalised = _clamp((net_score - score_floor) / span, 0.0, 1.0)

    elo_base = float(defaults_cfg.get("elo_base", 1200.0))
    elo_scale = float(defaults_cfg.get("elo_scale", 1600.0))
    estimated_elo = elo_base + normalised * elo_scale

    sorted_contribs = sorted(contributions, key=lambda item: item.contribution, reverse=True)
    top_positive = [c for c in sorted_contribs if c.contribution > 0][:3]
    top_negative = [c for c in sorted(sorted_contribs, key=lambda item: item.contribution) if c.contribution < 0][:3]

    return {
        "style_mix": _normalise_mix(style, templates),
        "raw_score": raw_score,
        "penalties": penalty_payload,
        "net_score": net_score,
        "performance_percent": round(normalised * 100, 2),
        "estimated_elo": round(estimated_elo, 1),
        "contributions": [c.__dict__ for c in contributions],
        "top_positive": [c.__dict__ for c in top_positive],
        "top_negative": [c.__dict__ for c in top_negative],
        "ratios_used": effective_ratios,
    }
