# Changelog

## [v2.1-tags-ontology] - 2025-11-07

### 🏷️ Tag Ontology & Naming System
- **Tag Catalog**: Established `rule_tagger2/core/tag_catalog.yml` with 41 tags across 7 families (initiative, tension, maneuver, sacrifice, control, structural, meta)
- **Schema Validator**: Added `rule_tagger2/core/tag_schema_validator.py` enforcing parent-child relationships, aliases, and detector references
- **Naming Convention**: Documented 7 core principles in `docs/tag_naming_convention.md` (snake_case, family prefixes, tense consistency, quality suffixes)
- **Tag Hierarchy Reports**: `scripts/build_tag_hierarchy_report.py` generates `reports/tags_hierarchy.md` and JSON with detector badges and A/B switch annotations
- **Rename Tools**: `rule_tagger2/versioning/tag_renames_v2.py` + `scripts/apply_tag_renames.py` for spelling/convention migrations
- **Usage Scanner**: `scripts/scan_tag_usage.py` detects hardcoded tag names in codebase (CI-ready, zero false positives)
- **Alias Layer**: `rule_tagger2/versioning/tag_aliases.py` maintains backward compatibility for deprecated/misspelled tags

### 🎯 Tension Boundary Refinement
- **Decision Tree**: `docs/tension_boundary.md` clarifies `tension_creation` vs `neutral_tension_creation` split
- **A/B Switch**: `USE_SPLIT_TENSION_V2` environment variable toggles evidence gates (v2: mobility≥0.10, contact≥0.01; legacy: 0.05/0.005)
- **Minimum Evidence Gates**: Neutral tension now requires measurable mobility/contact changes, preventing false positives in quiet positions
- **Regression Testing**: `scripts/tension_ab_eval.py` compares trigger rates, precision/recall across 14+ test positions

### ♞♝ Knight-Bishop Exchange Detection
- **New Detector**: `rule_tagger2/detectors/knight_bishop_exchange.py` with 3 subtypes:
  - `accurate_knight_bishop_exchange` (Δcp < 10)
  - `inaccurate_knight_bishop_exchange` (10 ≤ Δcp < 30)
  - `bad_knight_bishop_exchange` (Δcp ≥ 30)
- **Rules**: (1) Minor piece captures minor piece, (2) Recapture found in opponent's top-N moves, (3) Eval delta determines quality
- **Configuration**: `KBE_DEPTH`, `KBE_TOPN=3`, `KBE_THRESHOLDS=10,30` env vars
- **Pipeline Integration**: Diagnostics cached to `analysis_meta['knight_bishop_exchange']` with recapture rank, opponent candidates
- **Test Coverage**: 6 golden cases (2 accurate, 1 inaccurate, 1 bad + 2 failed prophylactic)
- **V2-kbe Enhancement** (2025-11-08):
  - KBE detector now exposed in `rule_tagger2/detectors/__init__.__all__` for public API
  - KBE results written to `engine_meta["gating"]["kbe_detected"]` and `engine_meta["gating"]["kbe_subtype"]` for pipeline/telemetry/dashboards
  - KBE diagnostics mirrored to `analysis_context["kbe_support"]` for UI/report layer
  - **Note**: KBE detection requires `multipv ≥ 3` to check for recapture in top-N moves; if multipv is insufficient, detector skips and logs diagnostic

### 🛡️ Failed Prophylactic Detection
- **New Tag**: `failed_prophylactic` when prophylactic move allows opponent refutation ≥50cp
- **Detector**: `rule_tagger2/detectors/failed_prophylactic.py` runs post-Prophylaxis, checks opponent top-N responses
- **Configuration**: `PROPHY_FAIL_CP=50`, `PROPHY_FAIL_TOPN=3` env vars
- **Diagnostics**: Failure check details in `analysis_meta['prophylaxis_diagnostics']['failure_check']` with worst eval drop, failing move UCI
- **Evaluation Script**: `scripts/prophylaxis_fail_eval.py` measures failure rate from golden cases

### 📊 Reporting & Monitoring
- **Evidence Reports**: `scripts/detector_evidence_report.py` now includes KBE card showing Δcp, recapture details, opponent candidates
- **Tag Distribution Monitor**: `scripts/tag_distribution_monitor.py` compares legacy vs new trigger rates with chi-squared tests
- **Longtail Monitoring**: `scripts/longtail_tag_monitor.py` tracks 7 rare tags (KL divergence, chi-squared α/z-score thresholds)
- **Config Snapshot**: `rule_tagger2/core/config_snapshot.py` merges defaults/YAML/env, emits SHA256 hash for drift detection
- **Config Validator**: `rule_tagger2/core/config_validator.py` enforces schema, detects default fallbacks

### 🔧 Infrastructure
- **Context Mapping**: `_build_context_from_legacy` now flattens `engine_meta` into `ctx.metadata` for detector access
- **Field Mapping Tests**: `tests/test_context_field_mapping.py` validates 9 mapping scenarios
- **Legacy Split**: Extracted `control_helpers.py`, `cod_detectors.py`, `cod_selection.py` from monolithic `core.py` (3111→2096 lines)
- **TagResult Schema**: Added 4 new fields to legacy cores (`accurate/inaccurate/bad_knight_bishop_exchange`, `failed_prophylactic`)
- **Pipeline Switching**: Added CLI flags `--new-pipeline` / `--legacy` to `scripts/analyze_player_batch.py` and `use_new` parameter to `codex_utils.analyze_position()`
  - Three-state logic: `None` (default, consults `NEW_PIPELINE` env var), `True` (force new), `False` (force legacy)
  - Environment variable: `NEW_PIPELINE=1` enables new orchestrator by default

### 🔄 Breaking Changes
- **Tension Evidence Gates**: Neutral tension now requires minimum mobility (0.10) or contact (0.01) evidence when `USE_SPLIT_TENSION_V2=1`
- **Tag Renames**: See `rule_tagger2/versioning/tag_renames_v2.py` for spelling corrections and convention alignments
  - `innitiative` → `initiative_attempt`
  - `manuever` → `constructive_maneuver`
  - `structural_shift` → `structural_integrity`

### 📦 Migration Guide
1. **Update Tag References**: Run `python3 scripts/apply_tag_renames.py --dry-run` to preview required changes
2. **Validate Catalog**: `python3 -m rule_tagger2.core.tag_schema_validator --strict`
3. **Check Config**: `python3 -m rule_tagger2.core.config_validator --check-fallbacks`
4. **Scan Usage**: `python3 scripts/scan_tag_usage.py --path your_code/` to find unregistered tags
5. **Switch Pipeline**:
   ```bash
   # Use new orchestrator (default behavior via NEW_PIPELINE=1)
   export NEW_PIPELINE=1
   python3 scripts/analyze_player_batch.py --player Kasparov

   # Or force via CLI flag (overrides env var)
   python3 scripts/analyze_player_batch.py --new-pipeline --player Kasparov

   # Revert to legacy pipeline
   python3 scripts/analyze_player_batch.py --legacy --player Kasparov

   # In Python code
   from codex_utils import analyze_position
   result = analyze_position(fen, move, use_new=True)  # Force new
   result = analyze_position(fen, move, use_new=False) # Force legacy
   result = analyze_position(fen, move)                # Use NEW_PIPELINE env var
   ```

---

## 2025-01-28

- Hardened CoD funnel telemetry: selector exposes per-subtype `candidates`, `suppressed_by`, and `cooldown_hit`, diagnostics export the matching `cand_*` columns and print summary rates.
- Retuned detectors: plan_kill now honours `PLAN_KILL_STRICT`/`VOL_GATE_FOR_PLAN`, freeze_bind relaxes to contact ratio / mobility gates, space_clamp accepts non-pawn space gains, and blockade_passed recognises SEE-supported blockades.
- Added rare-subtype tie-break with phase weights (`CONTROL.RARE_TYPES`, `CONTROL.PHASE_WEIGHTS`, `CONTROL.TIE_BREAK_DELTA`) and END-specific priority (`CONTROL.PRIORITY_END`).
- Updated YAML defaults (`OP_MOBILITY_DROP=1`, `TENSION_DEC_MIN=0`, `SPACE_MIN=1`, `PASSED_PUSH_MIN=0`) to align with new tuning levers.

## 2025-01-27

- Updated `rule_tagger2/legacy/core.py` with CoD v2 detectors, cooldown-aware selection, and richer notes (schema version 2).
- Added `scripts/batch_cod_diagnostics.py` for CSV/Parquet batch diagnostics.
- Added manual detector smoke tests in `tests/manual_cod_cases.py`.
- Propagated control-over-dynamics flags into the tagging assemble output.
- Documented the new behaviour in `docs/cod_v2.md` and refreshed `README_REFACTORING.md`.
