from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass
class EngineCache:
    analyse_candidates: Dict[Tuple[Any, ...], Tuple[Any, Any, Any]] = field(default_factory=dict)
    eval_specific: Dict[Tuple[Any, ...], Any] = field(default_factory=dict)
    followups: Dict[Tuple[Any, ...], Tuple[Any, Any, Any, Any]] = field(default_factory=dict)
    threats: Dict[Tuple[Any, ...], float] = field(default_factory=dict)
    plans: Dict[Tuple[Any, ...], Any] = field(default_factory=dict)
