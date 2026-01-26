"""
Version management helpers exposed at the rule_tagger2 namespace.
"""
from __future__ import annotations

from ..legacy.versioning import (  # noqa: F401
    CANON_SCHEMA_VERSION,
    CanonTagRecord,
    REGISTRY,
    SUPPORTED,
    detect_version,
    normalize_to_canon,
)

__all__ = [
    "detect_version",
    "normalize_to_canon",
    "CanonTagRecord",
    "CANON_SCHEMA_VERSION",
    "REGISTRY",
    "SUPPORTED",
]
