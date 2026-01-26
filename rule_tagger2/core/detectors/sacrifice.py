"""
Sacrifice detector logic.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..context import PositionContext, ThresholdsView


def detect_sacrifice(
    ctx: PositionContext,
    thresholds: ThresholdsView,
) -> Tuple[Dict[str, bool], Dict[str, str], Dict[str, Any]]:
    raise NotImplementedError
