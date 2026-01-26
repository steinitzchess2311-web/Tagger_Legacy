"""
Control over Dynamics v2 (Claude Implementation)

This module implements a refined version of Control over Dynamics detection
with improved diagnostics and clarity. It is isolated from the legacy system
and activated only via CLAUDE_COD_V2=1 environment variable.

IMPORTANT: This module does NOT modify any existing files:
- legacy/core.py
- models.py
- assemble.py
- metrics_thresholds.yml

All functionality is additive and feature-flagged.
"""
from .detector import ControlOverDynamicsV2Detector
from .cod_types import CoDContext, CoDResult, CoDSubtype, CoDMetrics

__all__ = [
    "ControlOverDynamicsV2Detector",
    "CoDContext",
    "CoDResult",
    "CoDSubtype",
    "CoDMetrics",
]

__version__ = "2.0.0-alpha"
