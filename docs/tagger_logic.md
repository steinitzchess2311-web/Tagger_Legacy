# Tagger Logic Overview

```
┌────────────────────────────┐
│ runner.py (CLI/batch API)  │
└──────────────┬─────────────┘
               │calls
┌──────────────▼─────────────┐
│        tag_position        │
│      (core.py:521+)        │
└──────────────┬─────────────┘
          evaluates
               │
┌──────────────▼─────────────┐
│ engine/analysis.py         │─ Stockfish probing, metrics, phase/coverage
│ engine/loaders.py          │─ Position ingestion (JSON/PGN)
└──────────────┬─────────────┘
          feeds metrics into
               │
┌──────────────▼─────────────┐
│ analysis/gating.py         │─ τ computation, tactical mode/gating
│ analysis/behavior.py       │─ Maneuver precision/timing, aggression, risk
│ analysis/structure.py      │─ Pawn structure deltas, file pressure, blockage
│ analysis/intent.py         │─ Intent label inference
└──────────────┬─────────────┘
               │updates
┌──────────────▼─────────────┐
│ models.TagResult & notes   │
└──────────────┬─────────────┘
               │exposed via
┌──────────────▼─────────────┐
│ __init__.py exports        │─ Public API (tag_position, batch_tag_positions,…)
└────────────────────────────┘
```

* **Engine helpers** isolate *all* Stockfish I/O and evaluator metrics so the core logic never touches `chess.engine` directly after the initial call.
* **Analysis modules** contain pure heuristics for a single concern (structure, maneuvers, intent, tactical gating), keeping every file <400 lines.
* **Runner** is the only place that knows about the legacy RuleSystem v8 wrapper; it chooses the implementation and handles batch/CLI UX.
* **Core** now focuses on orchestrating the per-move analysis: it wires engine telemetry into the analysis helpers, aggregates tag flags, and returns a `TagResult`.

## Post-processing the Tag List

`rule_tagger_lichessbot/tag_postprocess.py` contains lightweight helpers that run after `tag_position` returns and before the candidate payload is handed back to the imitator. These helpers keep a few special-purpose tags in check without leaking protocol noise into the core detectors.

### Winning/Losing Context Labels

The context labels `winning_position_handling` and `losing_position_handling` describe meta-evaluation bands (`τ > 1.05` or `< 0.95`). As soon as either label is observed on a candidate we drop every other tag so that the label stands alone in the output. If gating ever removes the label, we reintroduce it from `engine_meta["context"]["label"]` when present.

### Dynamic versus Control

The `control_dynamics` telemetry bucket exposes `has_dynamic_in_band` and the chosen move kind. When a dynamic move is played while a dynamic alternative exists, we append a `"dynamic_over_control"` tag so that downstream scoring can tell dynamic choices apart from the usual `control_over_dynamics` family. The tag is synthetic—no detector needs to be rewritten—but it lives in the same namespace as official tags so it can flow through the golden-case checks.

### Forced Moves

When the best candidate is at least 180 centipawns ahead of the runner-up *and* the style scorer ultimately plays that exact move, the tags emitted for that move are replaced with `["forced_move"]`. This keeps forced lines isolated so they are not mixed into the rest of the tag pool, and the threshold can still be tuned through the `FORCED_MOVE_THRESHOLD_CP` environment variable (default 180).
