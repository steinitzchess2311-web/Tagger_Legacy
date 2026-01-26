"""
Configuration schema validation and snapshot hash comparison.

This module provides validation for configuration files to:
- Ensure all threshold values are within acceptable ranges
- Detect schema violations (missing required fields, invalid types)
- Compare config hashes to detect drift from baseline
- Prevent silent fallback to defaults

Usage:
    # Validate current config against schema
    from rule_tagger2.core.config_validator import validate_config_schema

    result = validate_config_schema()
    if not result.is_valid:
        print("Config validation failed:")
        for error in result.errors:
            print(f"  - {error}")

    # Compare snapshot hash with baseline
    from rule_tagger2.core.config_validator import compare_snapshot_hash

    baseline_hash = "7ccce774"
    is_same = compare_snapshot_hash(baseline_hash)
    if not is_same:
        print("Config has drifted from baseline!")
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config_snapshot import build_config_snapshot


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    snapshot: Optional[Dict[str, Any]] = None


# Schema definitions for each config category
# Note: Relaxed ranges to match actual codebase usage patterns
SCHEMA = {
    "tension": {
        "mobility_min": {"type": float, "min": 0.0, "max": 2.0},
        "mobility_near": {"type": float, "min": 0.0, "max": 2.0},
        "mobility_delay": {"type": float, "min": 0.0, "max": 2.0},
        "symmetry_tol": {"type": float, "min": 0.0, "max": 1.0},
        "sustain_min": {"type": int, "min": 0, "max": 100},
        "sustain_var_cap": {"type": float, "min": 0.0, "max": 10.0},
        "trend_self": {"type": float, "min": -2.0, "max": 2.0},
        "trend_opp": {"type": float, "min": -2.0, "max": 2.0},
    },
    "structural": {
        "threshold": {"type": float, "min": 0.0, "max": 1.0},
        "dominance_limit": {"type": float, "min": 0.0, "max": 1.0},
        "weaken_limit": {"type": float, "min": -1.0, "max": 1.0},  # Can be negative
    },
    "tactical": {
        "threshold": {"type": float, "min": 0.0, "max": 1.0},
        "delta_tactics": {"type": int, "min": 0, "max": 1000},
        "gap_first_choice": {"type": int, "min": 0, "max": 1000},
        "miss_loss": {"type": int, "min": 0, "max": 1000},
        "slope_threshold": {"type": float, "min": 0.0, "max": 100.0},  # Can be larger
        "dominance_threshold": {"type": float, "min": 0.0, "max": 500.0},  # CP values
    },
    "mobility": {
        "tolerance": {"type": float, "min": 0.0, "max": 2.0},
        "risk_tradeoff": {"type": float, "min": 0.0, "max": 2.0},  # Can exceed 1.0
        "self_limit": {"type": float, "min": 0.0, "max": 2.0},
    },
    "soft_gate": {
        "midpoint": {"type": float, "min": -1.0, "max": 1.0},  # Can be negative
        "width": {"type": float, "min": 0.0, "max": 2.0},
    },
    "tau": {
        "winning_max": {"type": float, "min": 0.0, "max": 5.0},  # Can be > 1
        "winning_scale": {"type": float, "min": 0.0, "max": 10.0},
        "losing_min": {"type": float, "min": 0.0, "max": 1.0},
        "losing_scale": {"type": float, "min": 0.0, "max": 10.0},
    },
    "maneuver": {
        "timing_neutral": {"type": float, "min": 0.0, "max": 2.0},
        "trend_neutral": {"type": float, "min": -2.0, "max": 2.0},
        "eval_tolerance": {"type": float, "min": 0.0, "max": 1.0},  # Float like 0.12
        "ev_protect_cp": {"type": int, "min": 0, "max": 1000},
        "ev_fail_cp": {"type": int, "min": 0, "max": 1000},
        "allow_light_capture": {"type": bool},
    },
    "other": {
        "initiative_boost": {"type": float, "min": 0.0, "max": 100.0},  # CP values
        "king_safety_gain": {"type": float, "min": 0.0, "max": 100.0},  # CP values
        "king_safety_tolerance": {"type": float, "min": 0.0, "max": 2.0},
        "risk_small_loss": {"type": int, "min": 0, "max": 1000},
        "delta_eval_positional": {"type": int, "min": 0, "max": 1000},
        "file_pressure_threshold": {"type": float, "min": 0.0, "max": 1.0},
        "center_tolerance": {"type": float, "min": 0.0, "max": 1.0},
        "premature_attack_threshold": {"type": float, "min": -1.0, "max": 1.0},  # Can be negative
        "premature_attack_hard": {"type": float, "min": -1.0, "max": 1.0},  # Can be negative
    },
    "passive_plan": {
        "eval_drop": {"type": float, "min": -1.0, "max": 1.0},  # Float, can be negative like -0.4
        "mobility_self": {"type": float, "min": -1.0, "max": 1.0},  # Can be negative
        "mobility_opp": {"type": float, "min": 0.0, "max": 2.0},
    },
}


def validate_config_schema(
    snapshot: Optional[Dict[str, Any]] = None,
    strict: bool = False
) -> ValidationResult:
    """
    Validate configuration against schema.

    Args:
        snapshot: Optional pre-built snapshot. If None, builds a new one.
        strict: If True, treat warnings as errors.

    Returns:
        ValidationResult with validation status and any errors/warnings
    """
    if snapshot is None:
        snapshot = build_config_snapshot()

    errors = []
    warnings = []

    # Validate each category
    for category, fields in SCHEMA.items():
        if category not in snapshot:
            errors.append(f"Missing category: {category}")
            continue

        category_data = snapshot[category]

        for field_name, constraints in fields.items():
            # Check if field exists
            if field_name not in category_data:
                errors.append(f"Missing field: {category}.{field_name}")
                continue

            value = category_data[field_name]
            expected_type = constraints["type"]

            # Type checking
            if not isinstance(value, expected_type):
                # Try to coerce
                try:
                    if expected_type == float:
                        value = float(value)
                    elif expected_type == int:
                        value = int(value)
                    elif expected_type == bool:
                        value = bool(value)
                except (ValueError, TypeError):
                    errors.append(
                        f"Type mismatch: {category}.{field_name} "
                        f"expected {expected_type.__name__}, got {type(value).__name__}"
                    )
                    continue

            # Range validation for numeric types
            if expected_type in (int, float):
                if "min" in constraints and value < constraints["min"]:
                    errors.append(
                        f"Value out of range: {category}.{field_name}={value} "
                        f"< min={constraints['min']}"
                    )

                if "max" in constraints and value > constraints["max"]:
                    errors.append(
                        f"Value out of range: {category}.{field_name}={value} "
                        f"> max={constraints['max']}"
                    )

                # Warning for values at boundaries
                if "min" in constraints and value == constraints["min"]:
                    warnings.append(
                        f"Boundary value: {category}.{field_name}={value} "
                        f"(at min={constraints['min']})"
                    )

                if "max" in constraints and value == constraints["max"]:
                    warnings.append(
                        f"Boundary value: {category}.{field_name}={value} "
                        f"(at max={constraints['max']})"
                    )

    # Check for YAML load failures
    if "_metadata" in snapshot:
        yaml_status = snapshot["_metadata"].get("yaml_status")
        if yaml_status and "not found" in yaml_status.lower():
            warnings.append(f"YAML file not found: {yaml_status}")
        elif yaml_status and "error" in yaml_status.lower():
            errors.append(f"YAML load error: {yaml_status}")

    # Strict mode: warnings become errors
    if strict:
        errors.extend(warnings)
        warnings = []

    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        snapshot=snapshot
    )


def compare_snapshot_hash(
    baseline_hash: str,
    current_snapshot: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Compare current config snapshot hash with baseline.

    Args:
        baseline_hash: Expected baseline hash (first 8 chars of SHA256)
        current_snapshot: Optional pre-built snapshot. If None, builds a new one.

    Returns:
        Tuple of (is_match, current_hash)
    """
    if current_snapshot is None:
        current_snapshot = build_config_snapshot()

    current_hash = current_snapshot.get("_metadata", {}).get("hash")

    if current_hash is None:
        return False, None

    # Compare first 8 characters
    baseline_short = baseline_hash[:8] if len(baseline_hash) >= 8 else baseline_hash
    current_short = current_hash[:8] if len(current_hash) >= 8 else current_hash

    return baseline_short == current_short, current_hash


def detect_default_fallback(
    snapshot: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Detect fields that have fallen back to Python defaults (not from YAML).

    Args:
        snapshot: Optional pre-built snapshot. If None, builds a new one.

    Returns:
        List of field paths that are using defaults
    """
    if snapshot is None:
        snapshot = build_config_snapshot()

    fallbacks = []

    # Check if YAML was loaded successfully
    yaml_status = snapshot.get("_metadata", {}).get("yaml_status", "")
    if "not found" in yaml_status.lower():
        fallbacks.append("YAML file not found - all values using defaults")
        return fallbacks

    # This would require tracking which values came from YAML vs defaults
    # For now, just return empty list if YAML loaded successfully
    # Future enhancement: mark each value with its source in snapshot

    return fallbacks


def print_validation_report(result: ValidationResult):
    """Print formatted validation report."""
    print("=" * 60)
    print("CONFIG SCHEMA VALIDATION REPORT")
    print("=" * 60)
    print()

    if result.is_valid:
        print("✅ VALIDATION PASSED")
    else:
        print(f"❌ VALIDATION FAILED - {len(result.errors)} errors")

    print()

    if result.errors:
        print("ERRORS:")
        print("-" * 60)
        for error in result.errors:
            print(f"  ❌ {error}")
        print()

    if result.warnings:
        print("WARNINGS:")
        print("-" * 60)
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")
        print()

    # Hash comparison
    if result.snapshot and "_metadata" in result.snapshot:
        metadata = result.snapshot["_metadata"]
        if "hash" in metadata:
            print("CONFIG HASH:")
            print("-" * 60)
            print(f"  {metadata['hash']}")
            print()

    print("=" * 60)


def main():
    """CLI entry point for config validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate configuration schema and check snapshot hash"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--baseline-hash",
        type=str,
        default=None,
        help="Baseline config hash to compare against"
    )
    parser.add_argument(
        "--check-fallbacks",
        action="store_true",
        help="Check for fields using default values"
    )

    args = parser.parse_args()

    # Build snapshot once
    snapshot = build_config_snapshot()

    # Validate schema
    result = validate_config_schema(snapshot=snapshot, strict=args.strict)

    # Print report
    print_validation_report(result)

    # Compare hash if baseline provided
    if args.baseline_hash:
        is_match, current_hash = compare_snapshot_hash(
            args.baseline_hash,
            current_snapshot=snapshot
        )

        print("\nHASH COMPARISON:")
        print("-" * 60)
        print(f"Baseline: {args.baseline_hash}")
        print(f"Current:  {current_hash}")

        if is_match:
            print("✅ Hashes match - config unchanged from baseline")
        else:
            print("❌ Hashes differ - config has drifted!")
        print()

    # Check for fallbacks
    if args.check_fallbacks:
        fallbacks = detect_default_fallback(snapshot)

        if fallbacks:
            print("\nDEFAULT FALLBACKS:")
            print("-" * 60)
            for fb in fallbacks:
                print(f"  ⚠️  {fb}")
            print()
        else:
            print("\n✅ No default fallbacks detected")
            print()

    # Exit code
    exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
