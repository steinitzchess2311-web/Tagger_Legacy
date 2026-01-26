"""
Version fingerprint heuristics for rule tagger outputs.
"""
from __future__ import annotations

from typing import Dict, Optional

FINGERPRINTS: Dict[str, Dict[str, float]] = {
    "rulestack_2025-10-20": {
        "tension_mobility_min": 0.38,
        "contact_ratio_min": 0.04,
        "maneuver_eval_tolerance": 0.12,
        "prophylaxis_preventive_trigger": 0.15,
    },
    "rulestack_2025-11-03": {
        "tension_mobility_min": 0.38,
        "contact_ratio_min": 0.04,
        "maneuver_eval_tolerance": 0.12,
        "prophylaxis_preventive_trigger": 0.08,
    },
}

KEYS = [
    "tension_mobility_min",
    "contact_ratio_min",
    "maneuver_eval_tolerance",
    "prophylaxis_preventive_trigger",
]


def infer_version_by_fingerprint(meta: Dict[str, object]) -> Optional[str]:
    """Attempt to infer ruleset version from telemetry thresholds."""
    if not meta:
        return None
    tele = (meta.get("prophylaxis") or {}).get("telemetry") if isinstance(meta.get("prophylaxis"), dict) else {}
    thresholds = (meta.get("tension_support") or {}).get("thresholds") if isinstance(meta.get("tension_support"), dict) else {}
    candidates = []
    for version, fingerprint in FINGERPRINTS.items():
        score = 0
        for key in KEYS:
            value = None
            if isinstance(thresholds, dict):
                value = thresholds.get(key)
            if value is None and isinstance(tele, dict):
                value = tele.get(key)
            if value is None:
                continue
            if abs(value - fingerprint[key]) <= 1e-3:
                score += 1
        candidates.append((score, version))
    candidates.sort(reverse=True)
    if candidates and candidates[0][0] >= 2:
        return candidates[0][1]
    return None
