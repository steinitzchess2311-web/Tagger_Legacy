"""
Control-based semantic detectors (control_*  tags).

These detectors use the same semantic patterns as CoD but without dynamic gating,
cooldown logic, or mutual exclusion. They can coexist with cod_* tags.

Each control_* tag represents a pure semantic detection:
- control_simplify: Simplification via exchanges
- control_plan_kill: Preventing opponent plans
- control_freeze_bind: Freezing/binding opponent pieces
- control_blockade_passed: Blockading passed pawns
- control_file_seal: Sealing files
- control_king_safety_shell: Reinforcing king safety
- control_space_clamp: Clamping opponent space
- control_regroup_consolidate: Regrouping and consolidating
- control_slowdown: Slowing opponent's play

Unlike cod_* tags, these:
- Have no cooldown between occurrences
- Don't suppress each other
- Don't require dynamic alternatives
- Are purely semantic (no decision-layer logic)
"""

from typing import Any, Dict, List, Optional
from .shared.control_patterns import (
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


def detect_control_patterns(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect all control_* semantic patterns.

    Args:
        ctx: Context dictionary with move analysis data
        cfg: Configuration dictionary

    Returns:
        Dictionary mapping pattern names to detection results:
        {
            "control_simplify": {"detected": bool, "score": float, "why": str, "metrics": dict},
            "control_plan_kill": {...},
            ...
        }
    """
    # Check if control detection is enabled
    if not cfg.get("ENABLE_CONTROL_TAGS", True):
        return {}

    results = {}

    # Detect each pattern independently
    patterns = [
        ("control_simplify", is_simplify),
        ("control_plan_kill", is_plan_kill),
        ("control_freeze_bind", is_freeze_bind),
        ("control_blockade_passed", is_blockade_passed),
        ("control_file_seal", is_file_seal),
        ("control_king_safety_shell", is_king_safety_shell),
        ("control_space_clamp", is_space_clamp),
        ("control_regroup_consolidate", is_regroup_consolidate),
        ("control_slowdown", is_slowdown),
    ]

    for tag_name, detector_func in patterns:
        try:
            semantic_result = detector_func(ctx, cfg)
            results[tag_name] = {
                "detected": semantic_result.passed,
                "score": semantic_result.score,
                "why": semantic_result.why,
                "metrics": semantic_result.metrics,
                "severity": semantic_result.severity,
            }
        except Exception as e:
            # Log error but don't fail the entire detection
            results[tag_name] = {
                "detected": False,
                "score": 0.0,
                "why": f"Error: {str(e)}",
                "metrics": {},
                "severity": None,
            }

    return results


def get_detected_control_tags(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    """
    Get list of detected control_* tag names.

    Args:
        ctx: Context dictionary with move analysis data
        cfg: Configuration dictionary

    Returns:
        List of tag names (e.g., ["control_simplify", "control_file_seal"])
    """
    results = detect_control_patterns(ctx, cfg)
    return [tag_name for tag_name, result in results.items() if result.get("detected", False)]


def get_control_diagnostics(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed diagnostics for all control patterns.

    Useful for debugging and threshold tuning.

    Args:
        ctx: Context dictionary with move analysis data
        cfg: Configuration dictionary

    Returns:
        Dictionary with detection results and metrics for all patterns
    """
    results = detect_control_patterns(ctx, cfg)

    # Add summary statistics
    detected_count = sum(1 for r in results.values() if r.get("detected", False))
    total_score = sum(r.get("score", 0.0) for r in results.values() if r.get("detected", False))

    diagnostics = {
        "patterns": results,
        "summary": {
            "detected_count": detected_count,
            "total_score": total_score,
            "average_score": total_score / detected_count if detected_count > 0 else 0.0,
        },
    }

    return diagnostics


# Export main functions
__all__ = [
    "detect_control_patterns",
    "get_detected_control_tags",
    "get_control_diagnostics",
]
