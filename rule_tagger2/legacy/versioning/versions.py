"""Single entry point for rule_tagger output version management."""
from __future__ import annotations

from typing import Any, Dict

from .fingerprints import infer_version_by_fingerprint
from .normalizers import normalize_v_2025_10_20, normalize_v_2025_11_03
from .schema import CanonTagRecord

REGISTRY = {
    "rulestack_2025-10-20": normalize_v_2025_10_20,
    "rulestack_2025-11-03": normalize_v_2025_11_03,
}

SUPPORTED = set(REGISTRY.keys())


def _extract_meta(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    context = raw.get("analysis_context")
    if isinstance(context, dict):
        engine_meta = context.get("engine_meta")
        if isinstance(engine_meta, dict):
            return engine_meta
    engine_meta = raw.get("engine_meta")
    return engine_meta if isinstance(engine_meta, dict) else {}


def detect_version(raw: Dict[str, Any]) -> str:
    meta = _extract_meta(raw)
    claimed = meta.get("ruleset_version")
    if isinstance(claimed, str) and claimed in SUPPORTED:
        return claimed
    inferred = infer_version_by_fingerprint(meta)
    if inferred:
        return inferred
    if isinstance(claimed, str):
        return claimed
    return "unknown"


def normalize_to_canon(raw: Dict[str, Any]) -> CanonTagRecord:
    version = detect_version(raw)
    normalizer = REGISTRY.get(version)
    if normalizer is None:
        normalizer = normalize_v_2025_10_20
    return normalizer(raw, version)
