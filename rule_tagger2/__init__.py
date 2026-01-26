"""
Next-generation rule tagger pipeline with staged architecture.
"""

from .core.facade import tag_position
from .pipeline.runner import TaggingPipeline, run_pipeline
from .models.pipeline import FinalResult, FeatureBundle, ModeDecision, TagBundle

__all__ = [
    "TaggingPipeline",
    "run_pipeline",
    "FinalResult",
    "FeatureBundle",
    "ModeDecision",
    "TagBundle",
    "tag_position",
]
