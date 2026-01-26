"""
Shared semantic pattern detection for control-based tags.

This module provides pure semantic detection functions that can be reused
by both CoD (decision tags with gating) and control_* (semantic tags without gating).
"""

from .control_patterns import (
    SemanticResult,
    is_simplify,
    is_plan_kill,
    is_freeze_bind,
    is_blockade_passed,
    is_file_seal,
    is_king_safety_shell,
    is_space_clamp,
    is_regroup_consolidate,
    is_slowdown,
)

__all__ = [
    "SemanticResult",
    "is_simplify",
    "is_plan_kill",
    "is_freeze_bind",
    "is_blockade_passed",
    "is_file_seal",
    "is_king_safety_shell",
    "is_space_clamp",
    "is_regroup_consolidate",
    "is_slowdown",
]
