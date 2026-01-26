"""
Dataclass models for the rule_tagger2 pipeline.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List

from .pipeline import (
    EngineMove,
    EngineCandidates,
    FeatureBundle,
    ModeDecision,
    TagBundle,
    FinalResult,
)

__all__: List[str] = [
    "EngineMove",
    "EngineCandidates",
    "FeatureBundle",
    "ModeDecision",
    "TagBundle",
    "FinalResult",
]


def _load_legacy_dataclasses():
    module_path = Path(__file__).resolve().parent.parent / "models.py"
    spec = importlib.util.spec_from_file_location("_rt2_dataclasses", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_dataclasses()
if _legacy is not None:
    for _name in [
        "Candidate",
        "StyleTracker",
        "TAG_PRIORITY",
        "TENSION_TRIGGER_PRIORITY",
        "TagResult",
    ]:
        globals()[_name] = getattr(_legacy, _name)
        if _name not in __all__:
            __all__.append(_name)
