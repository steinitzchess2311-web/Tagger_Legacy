"""
Tag detection orchestration and pipeline management.
"""
from .context import AnalysisContext
from .gating import TagGate, apply_gating
from .pipeline import TagDetectionPipeline, run_pipeline
from .result_builder import assemble_result, build_evidence_dict, build_notes_dict

__all__ = [
    "AnalysisContext",
    "TagGate",
    "apply_gating",
    "TagDetectionPipeline",
    "run_pipeline",
    "assemble_result",
    "build_evidence_dict",
    "build_notes_dict",
]
