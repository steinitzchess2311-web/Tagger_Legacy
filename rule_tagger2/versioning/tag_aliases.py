"""
Tag Alias Mappings - Backward Compatibility Layer

This module maintains mappings between old tag names and their current canonical forms.
It ensures that old data, reports, and code references continue to work after tag renames
and standardization.

Usage:
    from rule_tagger2.versioning.tag_aliases import resolve_tag, get_canonical_name

    # Resolve old tag name to canonical form
    canonical = get_canonical_name("old_tag_name")

    # Resolve list of tags
    canonical_tags = resolve_tag_list(["tension", "control_over_dynamics"])

Version: 2.0
Last Updated: 2025-11-06
Purpose: Support milestone2 tension boundary split and historical spelling corrections
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set


# ============================================================================
# Alias Mappings
# ============================================================================

# Spelling corrections and historical name variations
SPELLING_ALIASES: Dict[str, str] = {
    # Common typos
    "tension_criation": "tension_creation",
    "tension_creatoin": "tension_creation",
    "netural_tension": "neutral_tension_creation",
    "neutral_tenson": "neutral_tension_creation",
    "prophilaxis": "prophylactic_move",
    "prophilactic": "prophylactic_move",
    "innitiative": "initiative_attempt",
    "initiative_cretion": "initiative_attempt",
    "control_over_dynamic": "control_over_dynamics",
    "manuever": "constructive_maneuver",
    "manouver": "constructive_maneuver",
    "sacrafice": "tactical_sacrifice",
    "sacrifise": "tactical_sacrifice",

    # CoD subtypes spelling
    "cod_simplifiy": "cod_simplify",
    "cod_plan_kil": "cod_plan_kill",
    "cod_freeze_bnd": "cod_freeze_bind",
    "cod_king_saftey": "cod_king_safety_shell",
}

# Standardization: old non-standard names → new standard names
CONVENTION_ALIASES: Dict[str, str] = {
    # Legacy short forms
    "tension": "tension_creation",
    "neutral_tension": "neutral_tension_creation",
    "initiative": "initiative_attempt",
    "maneuver": "constructive_maneuver",
    "prophylaxis": "prophylactic_move",

    # Prophylaxis V2 quality tags (old → new)
    "prophylactic_strong": "prophylactic_direct",
    "prophylactic_soft": "prophylactic_latent",

    # Old CoD generic forms
    "control": "control_over_dynamics",
    "cod": "control_over_dynamics",
    "control_dynamics": "control_over_dynamics",

    # Old sacrifice naming
    "positional_sac": "positional_sacrifice",
    "speculative_sac": "speculative_sacrifice",
    "desperate_sac": "desperate_sacrifice",
    "inaccurate_sac": "inaccurate_tactical_sacrifice",

    # Old structural naming
    "structural_shift": "structural_integrity",
    "structural_change": "structural_compromise_dynamic",

    # Old maneuver forms
    "knight_maneuver": "constructive_maneuver",
    "bishop_maneuver": "constructive_maneuver",
    "rook_lift": "constructive_maneuver",

    # TODO[v2-failed]: Maneuver failure aliases
    "failed_maneuver": "misplaced_maneuver",
}

# Deprecated tags → recommended replacement
DEPRECATED_ALIASES: Dict[str, str] = {
    # Tags marked deprecated in tag_catalog.yml
    # Add entries when tags are deprecated in future versions
}

# Milestone2 tension boundary split: old generic forms → new specific forms
# Note: This requires context to choose correctly - default to more common form
TENSION_V2_ALIASES: Dict[str, str] = {
    # When USE_SPLIT_TENSION_V2=1, these old forms map to new boundary
    # Default mappings for backward compatibility:
    "tension_high": "tension_creation",  # Legacy "high tension" → active tension
    "tension_low": "neutral_tension_creation",  # Legacy "low tension" → neutral tension
    "tension_balanced": "neutral_tension_creation",  # Balanced → neutral
}

# ============================================================================
# Consolidated Mapping
# ============================================================================

def _build_alias_map() -> Dict[str, str]:
    """
    Build consolidated alias map from all sources.

    Priority (highest to lowest):
    1. DEPRECATED_ALIASES (explicit deprecated → replacement)
    2. TENSION_V2_ALIASES (milestone2 boundary split)
    3. SPELLING_ALIASES (typo corrections)
    4. CONVENTION_ALIASES (standardization)

    Returns:
        Dictionary mapping old_name → canonical_name
    """
    alias_map: Dict[str, str] = {}

    # Lower priority first, higher priority overwrites
    alias_map.update(CONVENTION_ALIASES)
    alias_map.update(SPELLING_ALIASES)
    alias_map.update(TENSION_V2_ALIASES)
    alias_map.update(DEPRECATED_ALIASES)

    return alias_map


# Global alias map
_ALIAS_MAP: Dict[str, str] = _build_alias_map()


# ============================================================================
# Public API
# ============================================================================

def get_canonical_name(tag: str) -> str:
    """
    Resolve a tag name to its canonical form.

    Args:
        tag: Tag name (may be old/deprecated form)

    Returns:
        Canonical tag name. Returns input unchanged if no alias found.

    Examples:
        >>> get_canonical_name("tension")
        'tension_creation'
        >>> get_canonical_name("prophilaxis")
        'prophylactic_move'
        >>> get_canonical_name("tension_creation")
        'tension_creation'
    """
    return _ALIAS_MAP.get(tag, tag)


def resolve_tag(tag: str) -> str:
    """
    Alias for get_canonical_name for backward compatibility.

    Args:
        tag: Tag name

    Returns:
        Canonical tag name
    """
    return get_canonical_name(tag)


def resolve_tag_list(tags: List[str]) -> List[str]:
    """
    Resolve a list of tag names to canonical forms.

    Args:
        tags: List of tag names (may contain old/deprecated forms)

    Returns:
        List of canonical tag names (preserves order, no deduplication)

    Examples:
        >>> resolve_tag_list(["tension", "prophylaxis", "control"])
        ['tension_creation', 'prophylactic_move', 'control_over_dynamics']
    """
    return [get_canonical_name(tag) for tag in tags]


def get_all_aliases() -> Dict[str, str]:
    """
    Get complete alias mapping dictionary.

    Returns:
        Dictionary mapping old_name → canonical_name
    """
    return _ALIAS_MAP.copy()


def is_alias(tag: str) -> bool:
    """
    Check if a tag name is an alias (non-canonical form).

    Args:
        tag: Tag name

    Returns:
        True if tag is an alias, False if canonical or unknown

    Examples:
        >>> is_alias("tension")
        True
        >>> is_alias("tension_creation")
        False
    """
    return tag in _ALIAS_MAP


def get_aliases_for(canonical_tag: str) -> List[str]:
    """
    Get all known aliases that map to a canonical tag.

    Args:
        canonical_tag: Canonical tag name

    Returns:
        List of alias names that resolve to this canonical tag

    Examples:
        >>> get_aliases_for("tension_creation")
        ['tension', 'tension_high', 'tension_criation', 'tension_creatoin']
    """
    return [alias for alias, canonical in _ALIAS_MAP.items() if canonical == canonical_tag]


def get_all_known_tags() -> Set[str]:
    """
    Get set of all known tags (canonical + aliases).

    Useful for validation and auto-completion.

    Returns:
        Set of all tag names (canonical and aliases)
    """
    known_tags: Set[str] = set(_ALIAS_MAP.keys())  # All aliases
    known_tags.update(_ALIAS_MAP.values())  # All canonical forms
    return known_tags


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_tags(tags: List[str], strict: bool = False) -> tuple[List[str], List[str]]:
    """
    Validate a list of tags and return (valid, invalid) split.

    Args:
        tags: List of tag names to validate
        strict: If True, treat aliases as invalid (canonical only)

    Returns:
        Tuple of (valid_tags, invalid_tags)

    Examples:
        >>> validate_tags(["tension_creation", "unknown_tag", "tension"], strict=False)
        (['tension_creation', 'tension'], ['unknown_tag'])
        >>> validate_tags(["tension_creation", "unknown_tag", "tension"], strict=True)
        (['tension_creation'], ['unknown_tag', 'tension'])
    """
    valid = []
    invalid = []

    known_tags = get_all_known_tags()
    canonical_only = set(_ALIAS_MAP.values())

    for tag in tags:
        if strict:
            # Strict mode: only accept canonical forms
            if tag in canonical_only:
                valid.append(tag)
            else:
                invalid.append(tag)
        else:
            # Permissive mode: accept canonical + aliases
            if tag in known_tags:
                valid.append(tag)
            else:
                invalid.append(tag)

    return valid, invalid


# ============================================================================
# Migration Helpers
# ============================================================================

def migrate_tag_data(data: Dict[str, any]) -> Dict[str, any]:
    """
    Migrate old tag data dictionary to use canonical names.

    Useful for converting legacy reports, analysis results, or cached data.

    Args:
        data: Dictionary with tag names as keys

    Returns:
        New dictionary with canonical tag names as keys

    Examples:
        >>> migrate_tag_data({"tension": True, "prophylaxis": False})
        {'tension_creation': True, 'prophylactic_move': False}
    """
    migrated = {}
    for old_tag, value in data.items():
        canonical = get_canonical_name(old_tag)
        migrated[canonical] = value
    return migrated


def suggest_canonical(tag: str) -> Optional[str]:
    """
    Suggest canonical form if tag looks like a known pattern.

    Uses fuzzy matching for common patterns (e.g., missing underscores).

    Args:
        tag: Potentially malformed tag name

    Returns:
        Suggested canonical name or None if no match

    Examples:
        >>> suggest_canonical("tensioncreation")
        'tension_creation'
        >>> suggest_canonical("prophylactic")
        'prophylactic_move'
    """
    # First try direct alias lookup
    if tag in _ALIAS_MAP:
        return _ALIAS_MAP[tag]

    # Try lowercase + strip
    normalized = tag.lower().strip()
    if normalized in _ALIAS_MAP:
        return _ALIAS_MAP[normalized]

    # Try common patterns (missing underscores)
    # "tensioncreation" → "tension_creation"
    canonical_forms = set(_ALIAS_MAP.values())
    for canonical in canonical_forms:
        if canonical.replace("_", "") == normalized.replace("_", ""):
            return canonical

    return None


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """CLI tool for tag alias lookup and validation."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Tag alias resolution and validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Resolve single tag
  python3 -m rule_tagger2.versioning.tag_aliases --resolve tension

  # Resolve list of tags
  python3 -m rule_tagger2.versioning.tag_aliases --resolve-list "tension,prophylaxis,control"

  # Get all aliases for a canonical tag
  python3 -m rule_tagger2.versioning.tag_aliases --aliases-for tension_creation

  # Export all aliases to JSON
  python3 -m rule_tagger2.versioning.tag_aliases --export aliases.json

  # Validate tags
  python3 -m rule_tagger2.versioning.tag_aliases --validate "tension_creation,unknown_tag,tension"
        """
    )

    parser.add_argument("--resolve", help="Resolve single tag to canonical form")
    parser.add_argument("--resolve-list", help="Resolve comma-separated list of tags")
    parser.add_argument("--aliases-for", help="Get all aliases for a canonical tag")
    parser.add_argument("--export", help="Export all aliases to JSON file")
    parser.add_argument("--validate", help="Validate comma-separated list of tags")
    parser.add_argument("--strict", action="store_true", help="Strict validation (canonical only)")

    args = parser.parse_args()

    if args.resolve:
        canonical = get_canonical_name(args.resolve)
        print(f"Canonical form: {canonical}")
        if canonical != args.resolve:
            print(f"  (resolved from alias: {args.resolve})")

    elif args.resolve_list:
        tags = [t.strip() for t in args.resolve_list.split(",")]
        canonical_tags = resolve_tag_list(tags)
        print("Resolved tags:")
        for old, new in zip(tags, canonical_tags):
            if old == new:
                print(f"  {old}")
            else:
                print(f"  {old} → {new}")

    elif args.aliases_for:
        aliases = get_aliases_for(args.aliases_for)
        if aliases:
            print(f"Aliases for '{args.aliases_for}':")
            for alias in aliases:
                print(f"  - {alias}")
        else:
            print(f"No aliases found for '{args.aliases_for}'")

    elif args.export:
        alias_map = get_all_aliases()
        with open(args.export, "w") as f:
            json.dump(alias_map, f, indent=2, sort_keys=True)
        print(f"Exported {len(alias_map)} aliases to {args.export}")

    elif args.validate:
        tags = [t.strip() for t in args.validate.split(",")]
        valid, invalid = validate_tags(tags, strict=args.strict)

        print(f"Validation results ({'strict' if args.strict else 'permissive'} mode):")
        print(f"  Valid: {len(valid)} tag(s)")
        for tag in valid:
            print(f"    ✅ {tag}")

        if invalid:
            print(f"  Invalid: {len(invalid)} tag(s)")
            for tag in invalid:
                suggestion = suggest_canonical(tag)
                if suggestion:
                    print(f"    ❌ {tag} (did you mean '{suggestion}'?)")
                else:
                    print(f"    ❌ {tag}")

    else:
        # Default: show summary
        print("Tag Alias System Summary")
        print("=" * 60)
        print(f"Total aliases: {len(_ALIAS_MAP)}")
        print(f"Spelling corrections: {len(SPELLING_ALIASES)}")
        print(f"Convention aliases: {len(CONVENTION_ALIASES)}")
        print(f"Tension v2 aliases: {len(TENSION_V2_ALIASES)}")
        print(f"Deprecated aliases: {len(DEPRECATED_ALIASES)}")
        print()
        print("Use --help for usage examples")


if __name__ == "__main__":
    main()
