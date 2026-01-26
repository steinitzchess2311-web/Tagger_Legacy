"""
Version management helpers for rule_tagger outputs.
"""

from .versions import detect_version, normalize_to_canon, REGISTRY, SUPPORTED  # noqa: F401
from .schema import CanonTagRecord, CANON_SCHEMA_VERSION  # noqa: F401
