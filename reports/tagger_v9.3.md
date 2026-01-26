# Tagger v9.3 – tuned on cases1+2 golden (E = 111)

## Summary metrics (cases1 + cases2 golden)
- `perfect_cases`: 43 / 92  
- `total_missing_tags`: 34  
- `total_extra_tags`: 77  
- `error = missing + extra = 111`
- Top extra tags (from `rule_tagger_lichessbot/reports/report_golden_sample/summary.txt`):
  1. `initiative_attempt` (10 occurrences)  
  2. `prophylactic_move` (10)  
  3. `control_over_dynamics` (9)  

These numbers reflect the latest golden evaluation run; rerun `rule_tagger_lichessbot/tests/eval_golden_cases12.py` after any threshold tweak to regen `summary.json` & `summary.txt` and keep the `error` metric moving downward.

## Semantic consistency across consumers
All move tagging now flows through `players/tagger_bridge.py` → `rule_tagger_lichessbot/tag_postprocess.py`, so lichess-bot live analysis, the bulk PGN batch pipeline, and the golden-case offline runs share the same normalized tag semantics (forced/dynamic gating, `normalize_candidate_tags`, `apply_forced_move_tag`, background pruning, etc.).  
`build_golden_from_logs.py` follows the same path when regenerating `golden_cases/casesN.json`, so any update here shows up consistently in:

1. lichess-bot logging and reports  
2. `style_logs` / batch player summaries  
3. Golden-case regression runs (`rule_tagger_lichessbot/tests/eval_golden_cases12.py`)

Always rerun `build_golden_from_logs.py` + `eval_golden_cases12.py` when you change heuristics that affect initiative/prophylactic/COD labels.

## Key tightening in v9.3
- `initiative_attempt` now requires a tension signal, positive eval shift (`≥ INITIATIVE_EVAL_MIN`), and intent hints (expansion/initiative or restrained pushes) before tagging, and it can’t coexist with `deferred_initiative`.  
- `prophylactic_move` demands both threat-response (`threat_reduced`/`opp_restrained`) and consolidation (`self_solidified`/`self_safety_bonus`), with pattern overrides as the only exception.  
- Control-over-dynamics candidates must pass `_control_signal_status` (eval margin plus mobility/tension follow-up) before emitting `control_over_dynamics` or any COD subtype.  
- Postprocess prunes COD tags whenever higher-priority semantics (`initiative_attempt`, `structural_compromise_dynamic`, `missed_tactic`, `tactical_sensitivity`, etc.) are present, keeping prophylactic tags focused on pure defensive scenes.

## Next steps before freeze
1. Keep tracking `perfect_cases`, `total_missing + total_extra`, and the extra-tag histogram after each tweak; accept changes only when the combined `error` improves (or stays flat while extras drop).  
2. Collect `summary.json["mismatches"]` cases for underrunning tags (`initiative_attempt`, `tension_creation`, `structural_compromise_dynamic`, `cod_king_safety_shell`, `positional_*_sacrifice`, `latent_prophylactic`), adjust gating minimally, and rerun the evaluation to confirm localized hits without exploding extras.  
3. Once metrics stabilize (e.g., `perfect_cases ≥ 55`, `error` near the floor, no dominant extra tags), regenerate new golden files via `build_golden_from_logs.py`, document the resulting `cases3/4/…` under `rule_tagger_lichessbot/tests/golden_cases`, and tag this “freeze” as v9.3 before branching into new heuristics.

Maintaining this single tagging route ensures that lichess-bot, bulk analytics, and golden regression all mirror the same label space when we ship v9.3. Let me know when you want me to help draft the next freeze note or regenerate the downstream `cases*.json`.
