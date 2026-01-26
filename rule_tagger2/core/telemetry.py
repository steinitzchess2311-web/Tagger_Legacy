"""
Telemetry aggregation helpers for the refactored core.
"""
from __future__ import annotations

from typing import Any, Dict


def write_notes(meta: Dict[str, Any], notes: Dict[str, str]) -> None:
    raise NotImplementedError


def write_telemetry(meta: Dict[str, Any], telemetry: Dict[str, Any]) -> None:
    raise NotImplementedError


def write_thresholds(meta: Dict[str, Any], thresholds: Dict[str, Any]) -> None:
    raise NotImplementedError
