# Control over Dynamics v2

This note summarises the nine Control-over-Dynamics (CoD) subtypes now exposed
through the legacy tagger. The implementation lives in
`rule_tagger2/legacy/core.py` and is surfaced via the `control_schema_version=2`
field on `TagResult`.

## Subtype overview

| Subtype | Key signals |
| --- | --- |
| `simplify` | Heavy exchange or multi-piece trade that drops volatility without material loss |
| `plan_kill` | Successful plan-drop sample or strong preventive score (threat delta, mobility squeeze) |
| `freeze_bind` | Structural gain plus opponent mobility/tension collapse |
| `blockade_passed` | Blocking the advance square in front of an opponent passed pawn |
| `file_seal` | Significant drop in opponent contact pressure / break candidates on a file |
| `king_safety_shell` | King-safety gain that neutralises tactical pressure or mobility |
| `space_clamp` | Net space gain accompanied by opponent mobility drop |
| `regroup_consolidate` | Volatility reduction while consolidating king safety/structure with minimal self mobility |
| `slowdown` | Refusing a dynamic continuation in favour of large volatility, mobility and tension reduction |

The priority order is controlled by `CONTROL.PRIORITY` (default: simplify →
plan_kill → freeze_bind → blockade_passed → file_seal → king_safety_shell →
space_clamp → regroup_consolidate → slowdown). `select_cod_subtype` will only
emit a single subtype per move and enforces `CONTROL.COOLDOWN_PLIES` between
repeated triggers of the same subtype.

## Notes template

On activation the tagger emits a canonical note string, for example:

```
CoD.plan_kill: plan drop killed opponent plan; gates=[evalΔ:12, volΔ:24.0,
                tensionΔ:-1.5, opMobΔ:+5.0] suppressed=simplify cooldown=1
```

The `suppressed=` field lists other candidates that were deprioritised. When
`CONTROL.DEBUG_CONTEXT` is true an additional `control_ctx_debug` entry is
emitted with the raw context snapshot.

## Debugging checklist

- Enable context snapshots via either `metrics_thresholds.yml` (`control_debug_context: true`) or the environment variable `CONTROL_DEBUG_CONTEXT=1`.
- Inspect `analysis_context["control_dynamics"]` for the detector gate log, the candidate list, suppressed entries and cooldown bookkeeping.
- Use `scripts/batch_cod_diagnostics.py` to export CSV/Parquet diagnostics for a PGN corpus (see README for usage).

## 漏斗指标与调参与相别优先级

- **Funnel context**: selector now records `context.candidates` (per-subtype boolean map), `context.suppressed_by` (first candidate blocked by cooldown/priority) and `context.cooldown_hit`. With `CONTROL.DEBUG_CONTEXT` enabled the main note appends `cand=[...] suppressed_by=...` for quick spot checks.
- **Diagnostics export**: `scripts/batch_cod_diagnostics.py` appends `cand_*`, `suppressed_by`, and `cooldown_hit` columns to CSV/Parquet output and prints per-subtype candidate/suppressed/final rates plus END/MID ratio after each run.
- **Gate tuning switches**: `CONTROL.PLAN_KILL_STRICT`, `CONTROL.VOL_GATE_FOR_PLAN`, `CONTROL.PRIORITY_END`, `CONTROL.RARE_TYPES`, `CONTROL.PHASE_WEIGHTS`, and `CONTROL.TIE_BREAK_DELTA` live in `metrics_thresholds.yml` (or env overrides) so we can tighten plan_kill, prioritise rare subtypes in END phases, and experiment without code changes. Baseline thresholds (`OP_MOBILITY_DROP`, `TENSION_DEC_MIN`, `SPACE_MIN`, `PASSED_PUSH_MIN`) are also exposed for quick YAML tweaks.
- **Rare subtype protection**: selector tie-breaks flip to `CONTROL.RARE_TYPES` (freeze_bind, space_clamp, blockade_passed by default) when the gate score delta is within `TIE_BREAK_DELTA` and the phase weight table favours the rare candidate, reducing plan_kill/file_seal suppression in late-game positions.

## Schema compatibility

- `TagResult.control_over_dynamics` remains the aggregate boolean.
- Individual subtype booleans are available through the existing `cod_*`
  fields and are propagated into the new tagging bundle debug payload.
- `control_schema_version` is set to `2` for clients that need to branch on the
  enhanced metadata.
