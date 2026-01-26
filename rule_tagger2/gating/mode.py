"""
Mode selection strategies for the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

from ..models import FeatureBundle, ModeDecision


class ModeSelector(Protocol):
    """Strategy interface for deciding tactical/positional mode."""

    def decide(self, features: FeatureBundle, state: Dict[str, float] | None = None) -> ModeDecision:
        ...


@dataclass
class HardThresholdSelector(ModeSelector):
    """Current legacy behaviour with hard tactical weight thresholds."""

    tactical_enter: float = 0.65
    positional_enter: float = 0.35

    def decide(self, features: FeatureBundle, state: Dict[str, float] | None = None) -> ModeDecision:
        weight = features.tactical_weight
        if weight >= self.tactical_enter:
            mode = "tactical"
        elif weight <= self.positional_enter:
            mode = "positional"
        else:
            mode = "blended"
        debug = {"tactical_weight": round(weight, 3), "thresholds": {
            "tactical_enter": self.tactical_enter,
            "positional_enter": self.positional_enter,
        }}
        return ModeDecision(mode=mode, debug=debug)


@dataclass
class SoftGateSelector(ModeSelector):
    """Placeholder soft gate selector that can be configured later."""

    enter: float = 0.55
    exit: float = 0.4

    def decide(self, features: FeatureBundle, state: Dict[str, float] | None = None) -> ModeDecision:
        # Fallback to hard threshold if no state supplied.
        base = HardThresholdSelector(tactical_enter=self.enter, positional_enter=self.exit)
        return base.decide(features, state)
