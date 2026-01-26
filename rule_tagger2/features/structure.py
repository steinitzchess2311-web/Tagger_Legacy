"""
Structure-related feature helpers.
"""
from __future__ import annotations

from typing import Dict


def structure_delta(metrics_before: Dict[str, float], metrics_after: Dict[str, float]) -> float:
    return round(metrics_after.get("structure", 0.0) - metrics_before.get("structure", 0.0), 3)


def mobility_delta(metrics_before: Dict[str, float], metrics_after: Dict[str, float]) -> float:
    return round(metrics_after.get("mobility", 0.0) - metrics_before.get("mobility", 0.0), 3)
