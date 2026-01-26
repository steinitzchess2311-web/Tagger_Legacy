"""Conversions from legacy payloads to canonical schema."""
from __future__ import annotations

from typing import Dict, List

from .schema import CanonTagRecord


def _collect_tags(raw: Dict[str, object]) -> List[str]:
    meta = (
        raw.get("analysis_context", {}).get("engine_meta")
        if isinstance(raw.get("analysis_context"), dict)
        else None
    ) or raw.get("engine_meta") or {}
    tags_secondary = []
    if isinstance(meta, dict):
        tags_secondary = meta.get("trigger_order") or meta.get("tags_secondary") or []
        if not tags_secondary:
            tag_flags = meta.get("tag_flags") or {}
            if isinstance(tag_flags, dict):
                tags_secondary = [name for name, active in tag_flags.items() if active]
    return list(dict.fromkeys(tags_secondary))


def _base_record(raw: Dict[str, object], version: str) -> CanonTagRecord:
    meta = (
        raw.get("analysis_context", {}).get("engine_meta")
        if isinstance(raw.get("analysis_context"), dict)
        else None
    ) or raw.get("engine_meta") or {}
    claimed = meta.get("ruleset_version") if isinstance(meta, dict) else None
    record = CanonTagRecord(
        ruleset_version=version,
        ruleset_version_claimed=claimed if isinstance(claimed, str) else None,
        version_corrected=bool(claimed and claimed != version),
        eval_before=raw.get("eval_before"),
        eval_played=raw.get("eval_played"),
        eval_best=raw.get("eval_best"),
        tags=_collect_tags(raw),
        engine_meta=meta if isinstance(meta, dict) else {},
        notes=raw.get("notes") if isinstance(raw.get("notes"), dict) else {},
        raw_payload=raw,
    )
    return record


def _collect_sacrifice_tags(record: CanonTagRecord) -> Dict[str, bool]:
    tags = set(record.tags)
    return {
        "tactical": "tactical_sacrifice" in tags,
        "positional": "positional_sacrifice" in tags,
        "inaccurate_tactical": "inaccurate_tactical_sacrifice" in tags,
        "speculative": "speculative_sacrifice" in tags,
        "desperate": "desperate_sacrifice" in tags,
        "combination": "tactical_combination_sacrifice" in tags,
        "initiative": "tactical_initiative_sacrifice" in tags,
        "pos_structure": "positional_structure_sacrifice" in tags,
        "pos_space": "positional_space_sacrifice" in tags,
    }


def normalize_v_2025_10_20(raw: Dict[str, object], version: str) -> CanonTagRecord:
    record = _base_record(raw, version)
    record.sacrifice = _collect_sacrifice_tags(record)
    record.maneuver = {
        "precision": raw.get("maneuver_precision_score"),
        "timing": raw.get("maneuver_timing_score"),
    }
    meta = record.engine_meta
    prophylaxis_components = (
        meta.get("prophylaxis", {}).get("components")
        if isinstance(meta.get("prophylaxis"), dict)
        else {}
    )
    if not isinstance(prophylaxis_components, dict):
        prophylaxis_components = {}
    record.prophylaxis = {
        "preventive_score": prophylaxis_components.get("preventive_score"),
        "effective_preventive": prophylaxis_components.get("effective_preventive"),
        "quality": (
            meta.get("prophylaxis", {}).get("quality")
            if isinstance(meta.get("prophylaxis"), dict)
            else None
        ),
    }
    return record


def normalize_v_2025_11_03(raw: Dict[str, object], version: str) -> CanonTagRecord:
    return normalize_v_2025_10_20(raw, version)
