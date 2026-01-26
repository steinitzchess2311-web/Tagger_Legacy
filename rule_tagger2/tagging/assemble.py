"""
Assembly helpers that bridge legacy TagResult output to the new dataclasses.
"""
from __future__ import annotations

from typing import Any, Dict, List

from rule_tagger2.legacy.core import tag_position

from ..models import FeatureBundle, ModeDecision, TagBundle
from ..pipeline.context import PipelineContext


def _collect_tags(engine_meta: Dict[str, Any]) -> Dict[str, List[str]]:
    tags_primary = engine_meta.get("gating", {}).get("tags_primary") or []
    tags_secondary = engine_meta.get("tags_secondary") or []
    return {
        "primary": list(tags_primary),
        "secondary": list(tags_secondary),
    }


def assemble_tags(
    ctx: PipelineContext,
    features: FeatureBundle,
    mode: ModeDecision,
) -> tuple[TagBundle, Any]:
    """Call the legacy tag_position and translate the results."""

    small_drop_cp = ctx.metadata.get("small_drop_cp", 30)
    legacy_result = tag_position(
        ctx.engine.identifier(),
        ctx.fen,
        ctx.played_move_uci,
        depth=ctx.engine_depth,
        multipv=ctx.engine_multipv,
        cp_threshold=ctx.cp_threshold,
        small_drop_cp=small_drop_cp,
    )

    engine_meta = legacy_result.analysis_context.get("engine_meta", {})
    tags = _collect_tags(engine_meta)
    notes = [f"{key}: {value}" for key, value in legacy_result.notes.items()]
    telemetry = engine_meta.get("telemetry", {})
    cod_debug = {
        "control_over_dynamics": bool(getattr(legacy_result, "control_over_dynamics", False)),
        "cod_simplify": bool(getattr(legacy_result, "cod_simplify", False)),
        "cod_plan_kill": bool(getattr(legacy_result, "cod_plan_kill", False)),
        "cod_freeze_bind": bool(getattr(legacy_result, "cod_freeze_bind", False)),
        "cod_blockade_passed": bool(getattr(legacy_result, "cod_blockade_passed", False)),
        "cod_file_seal": bool(getattr(legacy_result, "cod_file_seal", False)),
        "cod_king_safety_shell": bool(getattr(legacy_result, "cod_king_safety_shell", False)),
        "cod_space_clamp": bool(getattr(legacy_result, "cod_space_clamp", False)),
        "cod_regroup_consolidate": bool(getattr(legacy_result, "cod_regroup_consolidate", False)),
        "cod_slowdown": bool(getattr(legacy_result, "cod_slowdown", False)),
    }
    telemetry.setdefault("cod_flags", cod_debug.copy())
    debug = {
        "legacy_mode": legacy_result.mode,
        "delta_eval": legacy_result.delta_eval,
    }
    debug.update(cod_debug)
    bundle = TagBundle(
        primary=tags["primary"],
        secondary=tags["secondary"],
        notes=notes,
        telemetry=telemetry,
        debug=debug,
    )
    return bundle, legacy_result
