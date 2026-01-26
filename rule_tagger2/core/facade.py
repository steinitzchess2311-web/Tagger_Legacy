"""
Facade entrypoints for the refactored rule tagger core.

This module provides the main entry point for tag detection with support
for switching between legacy and new pipeline via environment variable.

Environment Variables:
    NEW_PIPELINE: Set to "0" or "false" to use legacy pipeline (fallback)
                  Default: "1" (uses new detector pipeline)

Example:
    # Use new pipeline (default)
    result = tag_position(engine_path, fen, move_uci)

    # Use legacy pipeline (fallback)
    NEW_PIPELINE=0 python script.py
    # or
    result = tag_position(engine_path, fen, move_uci, use_new=False)
"""
from __future__ import annotations

import os
from typing import Any, Optional

from ..legacy.core import tag_position as _legacy_tag_position


def _use_new_pipeline() -> bool:
    """
    Check if new pipeline should be used.

    Returns:
        True by default, False if NEW_PIPELINE is explicitly set to 0 or false
    """
    env_value = os.environ.get("NEW_PIPELINE", "1").lower()
    return env_value not in ("0", "false", "no")


def tag_position(
    engine_path: str,
    fen: str,
    played_move_uci: str,
    depth: int = 14,
    multipv: int = 6,
    cp_threshold: int = 100,
    small_drop_cp: int = 30,
    use_new: Optional[bool] = None,
) -> Any:
    """
    Execute the tagging pipeline with new detector support by default.

    This is the main entry point for tag detection. It routes to either:
    - New detector pipeline (default, recommended)
    - Legacy pipeline (fallback via use_new=False or NEW_PIPELINE=0)

    Args:
        engine_path: Path to chess engine
        fen: FEN string of position
        played_move_uci: Move in UCI format (e.g., "e2e4")
        depth: Engine analysis depth (default 14)
        multipv: Number of principal variations (default 6)
        cp_threshold: Centipawn threshold for alternative moves
        small_drop_cp: Small eval drop threshold
        use_new: If None (default), consult NEW_PIPELINE env var;
                 if True, force new pipeline; if False, force legacy

    Returns:
        TagResult object with tags, notes, and analysis context
    """
    # Check if new pipeline should be used (three-way decision)
    if use_new is None:
        # Default: consult environment variable
        should_use_new = _use_new_pipeline()
    else:
        # Explicit True or False: honor caller's choice
        should_use_new = use_new

    if should_use_new:
        # Import here to avoid circular dependency
        from ..orchestration.pipeline import run_pipeline

        result = run_pipeline(
            engine_path=engine_path,
            fen=fen,
            played_move_uci=played_move_uci,
            depth=depth,
            multipv=multipv,
            cp_threshold=cp_threshold,
            small_drop_cp=small_drop_cp,
            use_legacy=False,  # Use new detectors
        )

        # Mark result as coming from new pipeline
        analysis_context = getattr(result, "analysis_context", None)
        if isinstance(analysis_context, dict):
            engine_meta = analysis_context.setdefault("engine_meta", {})
            engine_meta["__orchestrator__"] = "rule_tagger2.new_pipeline"
            engine_meta["__pipeline_version__"] = "v2_detectors"
    else:
        # Use legacy pipeline (default)
        result = _legacy_tag_position(
            engine_path,
            fen,
            played_move_uci,
            depth=depth,
            multipv=multipv,
            cp_threshold=cp_threshold,
            small_drop_cp=small_drop_cp,
        )

        # Mark result as coming from legacy
        analysis_context = getattr(result, "analysis_context", None)
        if isinstance(analysis_context, dict):
            engine_meta = analysis_context.setdefault("engine_meta", {})
            engine_meta["__orchestrator__"] = "rule_tagger2.legacy"
            engine_meta.setdefault("ruleset_version", "rule_tagger2_2025-01")
            engine_meta["__maneuver_v2__"] = True

    return result
