"""Central helpers for deciding whether to run the legacy or new rule-tagger pipeline."""

from __future__ import annotations

import os

PIPELINE_AUTO = "auto"
PIPELINE_NEW = "new"
PIPELINE_LEGACY = "legacy"


def use_new_pipeline_env() -> bool:
    """
    Return True if the NEW_PIPELINE environment variable enables the detector pipeline.
    """
    env_value = os.environ.get("NEW_PIPELINE", "1").lower()
    return env_value not in ("0", "false", "no")


def pipeline_mode_from_env() -> str:
    """
    Describe the current pipeline mode derived from NEW_PIPELINE.
    """
    return PIPELINE_NEW if use_new_pipeline_env() else PIPELINE_LEGACY


def use_new_from_mode(mode: str) -> bool:
    """
    Convert a pipeline mode label into the boolean that tag_position expects.
    """
    if mode == PIPELINE_NEW:
        return True
    if mode == PIPELINE_LEGACY:
        return False
    raise ValueError(f"Unsupported pipeline mode: {mode}")


__all__ = ["PIPELINE_AUTO", "PIPELINE_NEW", "PIPELINE_LEGACY", "pipeline_mode_from_env", "use_new_from_mode"]
