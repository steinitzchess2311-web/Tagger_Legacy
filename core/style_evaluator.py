"""
Style detection helpers that map tag distributions to scoring templates.

This module provides a lightweight heuristic detector today, and exposes
hooks so we can plug in data-driven similarity matching later without
touching the scoring pipeline.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Dict, Mapping, Sequence, Tuple

from core.tag_categories import tag_category

# Heuristic weightings used to score each style. The higher the score,
# the more closely the distribution matches that style.
STYLE_SIGNATURES: Dict[str, Dict[str, float]] = {
    "AggressiveModel": {
        "initiative": 1.0,
        "sacrifice": 0.7,
        "prophylaxis": -0.3,
        "intent": -0.2,
    },
    "RestrictiveModel": {
        "prophylaxis": 1.0,
        "intent": 0.8,
        "structural": 0.6,
        "initiative": -0.2,
        "maneuver": 0.4,
    },
    "CounterAttackerModel": {
        "intent": 0.6,
        "tension": 0.8,
        "initiative": 0.2,
        "prophylaxis": 0.2,
    },
    "BalancedModel": {},
}


def _category_sums(tag_ratios: Mapping[str, float]) -> Dict[str, float]:
    sums: Dict[str, float] = defaultdict(float)
    for tag, ratio in tag_ratios.items():
        if ratio <= 0.0:
            continue
        sums[tag_category(tag)] += ratio
    return sums


def _style_signature_score(category_sums: Mapping[str, float], signature: Mapping[str, float]) -> float:
    return sum(category_sums.get(cat, 0.0) * weight for cat, weight in signature.items())


def _normalise_scores(scores: Mapping[str, float]) -> Dict[str, float]:
    if not scores:
        return {"BalancedModel": 1.0}
    min_score = min(scores.values())
    max_score = max(scores.values())
    if max_score - min_score < 1e-9:
        return {max(scores, key=scores.get): 1.0}
    normalised: Dict[str, float] = {}
    for style, value in scores.items():
        normalised[style] = (value - min_score) / (max_score - min_score)
    total = sum(normalised.values())
    if total == 0:
        return {"BalancedModel": 1.0}
    return {style: value / total for style, value in normalised.items()}


def cosine_similarity(vec_a: Mapping[str, float], vec_b: Mapping[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not vec_a or not vec_b:
        return 0.0
    keys = set(vec_a) | set(vec_b)
    dot = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in keys)
    norm_a = sqrt(sum(vec_a.get(k, 0.0) ** 2 for k in keys))
    norm_b = sqrt(sum(vec_b.get(k, 0.0) ** 2 for k in keys))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def normalise_ratios(tag_ratios: Mapping[str, float]) -> Dict[str, float]:
    """Normalise ratios to unit length for similarity comparisons."""
    norm = sqrt(sum(value * value for value in tag_ratios.values()))
    if norm == 0.0:
        return dict(tag_ratios)
    return {tag: value / norm for tag, value in tag_ratios.items()}


def detect_style(
    tag_ratios: Mapping[str, float],
    *,
    reference_profiles: Mapping[str, Mapping[str, float]] | None = None,
) -> Dict[str, float]:
    """
    Determine the style mix for a given tag distribution.
    Returns a dict of style_name → weight (summing to 1.0).

    If reference profiles are provided the detector uses cosine similarity,
    otherwise it falls back to heuristic signatures over category sums.
    """
    if reference_profiles:
        target = normalise_ratios(tag_ratios)
        similarities = {
            style: cosine_similarity(target, normalise_ratios(profile))
            for style, profile in reference_profiles.items()
        }
        best = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
        if not best:
            return {"BalancedModel": 1.0}
        top_style, top_score = best[0]
        if len(best) == 1 or top_score <= 0:
            return {top_style: 1.0}
        mix: Dict[str, float] = {top_style: top_score}
        # Blend in the second-best style if it is close.
        if len(best) > 1 and best[1][1] > 0:
            second_style, second_score = best[1]
            if top_score - second_score <= 0.1:
                mix[second_style] = second_score
        total = sum(mix.values())
        return {style: weight / total for style, weight in mix.items()}

    category_sums = _category_sums(tag_ratios)
    scores = {style: _style_signature_score(category_sums, signature) for style, signature in STYLE_SIGNATURES.items()}
    return _normalise_scores(scores)


def blend_styles(order: Sequence[Tuple[str, float]], top_k: int = 2) -> Dict[str, float]:
    """
    Helper to build a style mix from ordered similarity tuples.
    Ensures the weights sum to 1.0 and at most top_k items are kept.
    """
    selected = [(style, score) for style, score in order[:top_k] if score > 0]
    if not selected:
        return {"BalancedModel": 1.0}
    total = sum(score for _, score in selected)
    return {style: score / total for style, score in selected}
