import os
from dataclasses import fields
from typing import Any, Dict

from rule_tagger2.core.facade import tag_position as tag_position_impl
from rule_tagger2.models import TagResult

DEFAULT_ENGINE_PATH = os.getenv("STOCKFISH_PATH", "/usr/local/bin/stockfish")


def _dedupe_tags(*sequences) -> list[str]:
    """Return ordered unique tags from provided sequences."""
    ordered = []
    for seq in sequences:
        if not seq:
            continue
        ordered.extend(seq)
    return list(dict.fromkeys(ordered))


def _extract_tag_flags(result: TagResult) -> Dict[str, bool]:
    """Prefer v8 tag flags; fall back to legacy booleans if unavailable."""
    engine_meta = result.analysis_context.get("engine_meta", {})
    tag_flags_v8 = engine_meta.get("tag_flags_v8")
    if tag_flags_v8:
        return {str(name): bool(value) for name, value in tag_flags_v8.items()}

    # dataclasses using postponed evaluation store types as ForwardRefs, so rely on runtime values
    tag_fields = [f.name for f in fields(TagResult)]
    flags: Dict[str, bool] = {}
    for name in tag_fields:
        value = getattr(result, name, None)
        if isinstance(value, bool):
            flags[name] = value
    return flags


def analyze_position(fen: str, move: str, engine_path: str | None = None, use_new: bool | None = None) -> Dict[str, Any]:
    """
    Run the rule-based tagger and normalize the response structure for the UI.

    Args:
        fen: Position FEN string
        move: Move in UCI format
        engine_path: Path to Stockfish engine (optional)
        use_new: Force pipeline version (None=consult NEW_PIPELINE env, True=force new, False=force legacy)
    """
    engine = engine_path or DEFAULT_ENGINE_PATH
    result = tag_position_impl(engine, fen, move, use_new=use_new)

    engine_meta = result.analysis_context.get("engine_meta", {})
    tag_flags = _extract_tag_flags(result)
    triggered = [name for name, active in tag_flags.items() if active]
    gating_info = engine_meta.get("gating") or {}

    tags_final = _dedupe_tags(
        engine_meta.get("tags_final_v8"),
        engine_meta.get("trigger_order"),
        triggered,
    )
    if not tags_final:
        tags_final = triggered.copy()

    tags_secondary = _dedupe_tags(
        engine_meta.get("tags_secondary"),
        tags_final,
        triggered,
    )

    tags_primary = _dedupe_tags(
        engine_meta.get("tags_final_v8"),
        engine_meta.get("trigger_order"),
        gating_info.get("tags_primary"),
        tags_secondary,
        triggered,
    )
    gating_reason = gating_info.get("reason")
    prophylaxis_quality = engine_meta.get("prophylaxis", {}).get("quality")

    return {
        "fen": fen,
        "move": move,
        "mode": result.mode,
        "tactical_weight": result.tactical_weight,
        "eval": {
            "before": result.eval_before,
            "played": result.eval_played,
            "best": result.eval_best,
            "delta": result.delta_eval,
        },
        "tags": {
            "all": tag_flags,
            "active": triggered,
            "secondary": list(dict.fromkeys(tags_secondary)),
            "primary": tags_primary,
            "gating_reason": gating_reason,
            "prophylaxis_quality": prophylaxis_quality,
        },
        "metrics": {
            "self_before": result.metrics_before,
            "self_played": result.metrics_played,
            "self_best": result.metrics_best,
            "opp_before": result.opp_metrics_before,
            "opp_played": result.opp_metrics_played,
            "opp_best": result.opp_metrics_best,
            "component_deltas": result.component_deltas,
            "opp_component_deltas": result.opp_component_deltas,
        },
        "coverage_delta": result.coverage_delta,
        "analysis_context": result.analysis_context,
        "notes": result.notes,
        "engine_meta": engine_meta,
    }
