"""
Pipeline context container used across stages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..engine import EngineClient
from ..models import EngineCandidates, FeatureBundle, ModeDecision, TagBundle, FinalResult


@dataclass
class PipelineContext:
    fen: str
    played_move_uci: str
    engine: EngineClient
    engine_depth: int
    engine_multipv: int
    cp_threshold: int
    followup_depth: int = 6
    followup_steps: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    engine_out: Optional[EngineCandidates] = None
    features: Optional[FeatureBundle] = None
    mode: Optional[ModeDecision] = None
    tags: Optional[TagBundle] = None
    final: Optional[FinalResult] = None
