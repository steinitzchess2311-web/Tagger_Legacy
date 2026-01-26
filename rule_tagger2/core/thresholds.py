"""
Threshold loading and frozen view helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from rule_tagger2.legacy.thresholds import THRESHOLDS as LEGACY_THRESHOLDS

@dataclass(frozen=True)
class Thresholds:
    values: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


def load_thresholds() -> Thresholds:
    return Thresholds(values=dict(LEGACY_THRESHOLDS))
