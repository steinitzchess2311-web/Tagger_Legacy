# RuleSystem v8.2 Overview

This document summarises the incremental changes introduced on top of the v5 rule tagger.  
Implementation now lives in the unified `rule_tagger2` facade (`rule_tagger2.core.facade.tag_position`) which supersedes the historical `rule_tagger_v8.py` compatibility layer.

## Key Objectives
- Replace hard-coded thresholds with data/percentile driven defaults (configurable via `config/metrics_thresholds.auto.json`).
- Introduce tag families and per-family mutual exclusion to avoid tag inflation.
- Emit pawn vs. piece variations for prophylaxis / control-over-dynamics / maneuver families.
- Provide granular sacrifice classification and expose intent signals as numeric weights.
- Split high-usage parent tags into semantically precise child tags (initiative attempts, exchanges, structural integrity, intents, etc.).
- Preserve backwards compatibility through alias mapping and system version metadata.

## Files
- `rule_tagger2/legacy/core.py`: post-processing orchestration that powers the facade.
- `config/metrics_thresholds.auto.json`: default percentile look-up table.
- `tools/calibrate_thresholds.py`: helper script for re-generating percentile data from a historical corpus.

## Metadata Additions
- `analysis_context["engine_meta"]["system_version"] = "RuleSystem_v8.2"`
- `analysis_context["engine_meta"]["tag_flags_v8"]`: boolean map of all v8 tags.
- `analysis_context["engine_meta"]["tags_final_v8"]`: ordered list filtered according to the canonical order.
- `analysis_context["engine_meta"]["aliases"]`: migration map for deprecated keys (e.g. `risk_avoidance`).
- `analysis_context["engine_meta"]["intent_flags_numeric"]`: continuous values for intent signals.
- `analysis_context["engine_meta"]["tag_facets"]`: per-family breakdown indicating which child tag(s) justified a parent label (e.g. `initiative_attempt` → `initiative_calculated_attempt`).

## Tag Families (Mutually Exclusive)
- Pawn prophylaxis: `strong_pawn_move_prophylactic`, `soft_pawn_move_prophylactic`, `failed_pawn_move_prophylactic`
- Piece prophylaxis: `strong_piece_move_prophylactic` (→ `strong_threat_neutralization` / `strong_structure_reinforcement`), `soft_piece_move_prophylactic` (→ `soft_success_piece_prophylactic` / `soft_mitigated_piece_prophylactic`), `failed_piece_move_prophylactic` (→ `failed_eval_piece_prophylactic` / `failed_blocked_piece_prophylactic`)
- Piece exchange: `accurate_exchange_accuracy` (→ `favorable_exchange_accuracy` / `equal_exchange_accuracy`), `neutral_exchange_accuracy`, `inaccurate_exchange_accuracy` (→ `exchange_misvaluation` / `exchange_mistiming`)
- Tension: `accurate_tension_creation` (→ `tension_creation_tactical` / `tension_creation_positional`), `inaccurate_tension_creation` (→ `premature_tension` / `misdirected_tension`), `accurate_tension_release`, `inaccurate_tension_release`
- Pawn structure: `structural_integrity` (→ `structural_stability` / `structural_control`), `structural_compromise_dynamic` (→ `structural_tradeoff_dynamic` / `structural_collapse_dynamic`), `structural_compromise_static`
- Piece maneuver: `latent_improved_maneuver` (→ `latent_active_maneuver` / `latent_restrictive_maneuver`), `neutral_maneuver`, `temporally_regroup` (→ `regroup_intentional` / `regroup_forced`), `failed_maneuver` (→ `failed_direction_maneuver` / `failed_blocked_maneuver` / `failed_redundant_maneuver`), `constructive_maneuver` (→ `constructive_immediate` / `constructive_preparatory`)
- Initiative: `initiative_attempt` (→ `initiative_calculated_attempt` / `initiative_speculative_attempt`), `direct_initiative`, `deferred_initiative` (→ `delayed_initiative_preparatory` / `delayed_initiative_misread`), `lost_initiative`
- Sacrifice: `tactical_sacrifice` (→ `tactical_combination_sacrifice` / `tactical_initiative_sacrifice`), `positional_sacrifice` (→ `positional_structure_sacrifice` / `positional_space_sacrifice`), `inaccurate_tactical_sacrifice`, `speculative_sacrifice`, `desperate_sacrifice`
- Intent: `intent_expansion` (→ `intent_spatial_expansion` / `intent_attack_initiation`), `intent_restriction` (→ `intent_spatial_restriction` / `intent_threat_restriction`), `intent_passive` (→ `intent_defensive` / `intent_resigned`), `intent_neutral`

## Percentile Thresholds
Thresholds are loaded at runtime from `metrics_thresholds.auto.json`. The defaults are meant to be replaced by running `python tools/calibrate_thresholds.py --out config/metrics_thresholds.auto.json` on a representative corpus.

## Intent Flags
Intent signals are now emitted as continuous scores in `intent_flags_numeric`.  
Boolean view (abs(value) ≥ 0.5) is preserved under `intent_expansion`, `intent_restriction`, `intent_passive`, `intent_neutral`.

## Output Order
`analysis_context["engine_meta"]["tags_final"]` stores the canonical order for the emitted tags.  
Only triggered tags are emitted while respecting the required ordering.

---
For additional implementation specifics refer to inline comments within `rule_tagger2/legacy/core.py`.
