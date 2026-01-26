"""
Compatibility shim that re-exports models from rule_tagger2.
"""
from __future__ import annotations

from rule_tagger2.models import (  # noqa: F401
    Candidate,
    StyleTracker,
    TAG_PRIORITY,
    TENSION_TRIGGER_PRIORITY,
    TagResult,
)

__all__ = [
    "Candidate",
    "StyleTracker",
    "TAG_PRIORITY",
    "TENSION_TRIGGER_PRIORITY",
    "TagResult",
]
