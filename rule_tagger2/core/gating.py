"""
Tactical gating utilities and constants.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from rule_tagger2.legacy.analysis import apply_tactical_gating as _legacy_gate
from rule_tagger2.models import TAG_PRIORITY as _LEGACY_TAG_PRIORITY, TENSION_TRIGGER_PRIORITY as _LEGACY_TENSION_PRIORITY

TAG_PRIORITY: Dict[str, int] = dict(_LEGACY_TAG_PRIORITY)
TENSION_TRIGGER_PRIORITY: Dict[str, int] = dict(_LEGACY_TENSION_PRIORITY)

# Maintain compatibility for new public aliases.
if "misplaced_maneuver" in TAG_PRIORITY:
    TAG_PRIORITY.setdefault("failed_maneuver", TAG_PRIORITY["misplaced_maneuver"])


def apply_tactical_gating(
    tags: List[str],
    effective_delta: float,
    material_delta: float,
    blockage_penalty: float,
    plan_passed: Optional[bool],
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Wrapper around the legacy gating logic. Maintains compatibility while the
    refactor migrates orchestration into the new core layout.
    """
    return _legacy_gate(tags, effective_delta, material_delta, blockage_penalty, plan_passed)
