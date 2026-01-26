"""
Result assembly and formatting.

This module assembles the final tag result from detector outputs,
ensuring consistent format with legacy output.

Current Status: P1 - Skeleton
"""
from typing import Any, Dict, List, Optional


def assemble_result(
    tags: List[str],
    evidence: Dict[str, Any],
    notes: Dict[str, str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Assemble final result dictionary.

    P1: Minimal implementation matching legacy format
    P2+: Enhanced with detector evidence, confidence scores, etc.

    Args:
        tags: List of final tags
        evidence: Evidence dictionary (metrics, thresholds, etc.)
        notes: Human-readable notes about detections
        metadata: Additional metadata

    Returns:
        Result dictionary compatible with legacy format
    """
    result = {
        "tags": tags,
        "evidence": evidence,
        "notes": notes,
        "metadata": metadata or {},
        "version": "refactor-p1",
    }

    return result


def build_evidence_dict(
    metrics_used: Dict[str, float],
    thresholds_used: Dict[str, float],
    checks_passed: List[str],
    checks_failed: List[str],
) -> Dict[str, Any]:
    """
    Build standardized evidence dictionary.

    Args:
        metrics_used: Metrics that were computed
        thresholds_used: Thresholds that were applied
        checks_passed: List of check names that passed
        checks_failed: List of check names that failed

    Returns:
        Evidence dictionary
    """
    return {
        "metrics": metrics_used,
        "thresholds": thresholds_used,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
    }


def build_notes_dict(detector_notes: Dict[str, str]) -> Dict[str, str]:
    """
    Build standardized notes dictionary from detector outputs.

    Args:
        detector_notes: Notes from each detector

    Returns:
        Consolidated notes dictionary
    """
    # P1: Simple passthrough
    # P2+: Format with detector attribution
    return detector_notes
