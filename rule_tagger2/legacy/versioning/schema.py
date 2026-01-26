from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CANON_SCHEMA_VERSION = "canon_v1"


@dataclass
class CanonTagRecord:
    """Canonical representation of a rule tagger move analysis."""

    ruleset_version: str
    ruleset_version_claimed: Optional[str]
    version_corrected: bool
    canon_schema: str = CANON_SCHEMA_VERSION

    eval_before: Optional[float] = None
    eval_played: Optional[float] = None
    eval_best: Optional[float] = None

    tags: List[str] = field(default_factory=list)

    sacrifice: Dict[str, bool] = field(default_factory=dict)
    maneuver: Dict[str, Any] = field(default_factory=dict)
    prophylaxis: Dict[str, Any] = field(default_factory=dict)

    engine_meta: Dict[str, Any] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)

    raw_payload: Dict[str, Any] = field(default_factory=dict)

