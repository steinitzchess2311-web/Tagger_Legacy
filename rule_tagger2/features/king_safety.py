"""
King safety feature helpers.
"""
from __future__ import annotations

from typing import Dict


def king_safety_delta(metrics_before: Dict[str, float], metrics_after: Dict[str, float]) -> float:
    """Return the delta in king safety from before to after a move."""

    return round(metrics_after.get("king_safety", 0.0) - metrics_before.get("king_safety", 0.0), 3)
