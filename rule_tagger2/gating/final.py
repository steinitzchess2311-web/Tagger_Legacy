"""
Final tag gating strategies.
"""
from __future__ import annotations

from typing import Dict, List, Protocol, Tuple

from rule_tagger2.legacy.analysis import apply_tactical_gating as legacy_gate


class FinalTagGate(Protocol):
    def gate(
        self,
        tags: List[str],
        *,
        effective_delta: float,
        material_delta: float,
        blockage_penalty: float,
        plan_passed: bool | None,
    ) -> Tuple[List[str], Dict[str, float] | None]:
        ...


class LegacyFinalTagGate(FinalTagGate):
    """Delegates to the legacy gating helper for compatibility."""

    def gate(
        self,
        tags: List[str],
        *,
        effective_delta: float,
        material_delta: float,
        blockage_penalty: float,
        plan_passed: bool | None,
    ) -> Tuple[List[str], Dict[str, float] | None]:
        gated, reason = legacy_gate(tags, effective_delta, material_delta, blockage_penalty, plan_passed)
        if gated is None:
            gated = tags
        return list(dict.fromkeys(gated)), ({"reason": reason} if reason else None)
