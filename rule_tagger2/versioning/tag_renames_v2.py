"""
Tag Rename Mapping v2

Provides one-time rename mappings for standardizing tag names:
- Spelling corrections
- Naming convention alignment
- Deprecated tag migrations

This module is used by:
- scripts/apply_tag_renames.py (batch file renaming CLI)
- Reporting layer (alias resolution)
- Migration scripts (historical data conversion)

Version: 2.1.0
"""

from typing import Dict

# ============================================================================
# RENAME MAPPINGS
# ============================================================================

# Spelling corrections and standardization
SPELLING_CORRECTIONS: Dict[str, str] = {
    # Common typos (none currently, but reserved for future)
    # "tention_creation": "tension_creation",
}

# Naming convention alignment (snake_case, prefix consistency)
CONVENTION_ALIGNMENT: Dict[str, str] = {
    # Prophylaxis V2 quality rename
    "prophylactic_strong": "prophylactic_direct",
    "prophylactic_soft": "prophylactic_latent",
}

# Deprecated tag migrations (old_name -> new_name)
DEPRECATED_MIGRATIONS: Dict[str, str] = {
    # Example: merging redundant tags
    # "failed_maneuver": "misplaced_maneuver",  # Already aliased in catalog
}

# Complete rename mapping (union of all above)
TAG_RENAMES: Dict[str, str] = {
    **SPELLING_CORRECTIONS,
    **CONVENTION_ALIGNMENT,
    **DEPRECATED_MIGRATIONS,
}

# ============================================================================
# REVERSE MAPPING (for legacy data import)
# ============================================================================

# Reverse mapping: new_name -> [old_name1, old_name2, ...]
TAG_ALIASES: Dict[str, list[str]] = {
    "misplaced_maneuver": ["failed_maneuver"],
    "prophylactic_direct": ["prophylactic_strong"],
    "prophylactic_latent": ["prophylactic_soft"],
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def resolve_tag_name(tag: str) -> str:
    """
    Resolve a tag name to its canonical form.

    If the tag has been renamed, return the new name.
    Otherwise, return the original tag name.

    Args:
        tag: The tag name to resolve

    Returns:
        The canonical tag name
    """
    return TAG_RENAMES.get(tag, tag)


def resolve_tag_list(tags: list[str]) -> list[str]:
    """
    Resolve a list of tag names to canonical forms.

    Args:
        tags: List of tag names (may include old/deprecated names)

    Returns:
        List of canonical tag names
    """
    return [resolve_tag_name(tag) for tag in tags]


def get_all_aliases(canonical_tag: str) -> list[str]:
    """
    Get all known aliases for a canonical tag name.

    Args:
        canonical_tag: The canonical tag name

    Returns:
        List of aliases (old names that map to this tag)
    """
    return TAG_ALIASES.get(canonical_tag, [])


def is_deprecated(tag: str) -> bool:
    """
    Check if a tag name is deprecated (has a newer replacement).

    Args:
        tag: The tag name to check

    Returns:
        True if the tag has been renamed, False otherwise
    """
    return tag in TAG_RENAMES


def print_rename_summary() -> None:
    """Print a summary of all rename mappings"""
    print("=" * 70)
    print("TAG RENAME MAPPINGS SUMMARY")
    print("=" * 70)
    print(f"Total renames: {len(TAG_RENAMES)}")
    print(f"Spelling corrections: {len(SPELLING_CORRECTIONS)}")
    print(f"Convention alignments: {len(CONVENTION_ALIGNMENT)}")
    print(f"Deprecated migrations: {len(DEPRECATED_MIGRATIONS)}")
    print("=" * 70)

    if TAG_RENAMES:
        print("\nRENAME MAPPINGS:")
        for old_name, new_name in sorted(TAG_RENAMES.items()):
            print(f"  {old_name:40s} → {new_name}")
    else:
        print("\n✅ No renames defined (all tags follow convention)")

    print("=" * 70)


# ============================================================================
# MODULE EXECUTION (for testing)
# ============================================================================

if __name__ == "__main__":
    print_rename_summary()

    # Test resolve functions
    print("\nTEST EXAMPLES:")
    print("-" * 70)

    # Test 1: Non-renamed tag
    test_tag = "tension_creation"
    resolved = resolve_tag_name(test_tag)
    print(f"resolve_tag_name('{test_tag}') = '{resolved}'")

    # Test 2: Check aliases
    canonical = "misplaced_maneuver"
    aliases = get_all_aliases(canonical)
    print(f"get_all_aliases('{canonical}') = {aliases}")

    # Test 3: Check deprecation
    print(f"is_deprecated('failed_maneuver') = {is_deprecated('failed_maneuver')}")
    print(f"is_deprecated('tension_creation') = {is_deprecated('tension_creation')}")

    print("-" * 70)
