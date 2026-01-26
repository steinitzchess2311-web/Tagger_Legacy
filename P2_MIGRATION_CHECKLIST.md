# P2 Migration Checklist: Tension, Prophylaxis, Control

> **Objective:** Extract 3 detector families from `legacy/core.py` (2224 lines)
> **Target:** 3 files × ~250-300 lines each
> **Strategy:** Copy-paste → Adapt → Verify → Delete from legacy

---

## 📋 Detector 1: Tension (TensionDetector)

### Location in legacy/core.py

| Component | Lines | Description |
|-----------|-------|-------------|
| Helper: `_control_tension_threshold()` | 256-264 | Phase-dependent threshold |
| Initialization | 576-577 | `tension_creation = False`, `neutral_tension_creation = False` |
| Main Detection Logic | 1750-1936 | Mobility symmetry, contact changes, structural shifts |
| Result Assembly | 2011-2019, 2074, 2090 | Add to metadata |
| Gating Integration | 2121-2125 | `neutral_tension_override` |
| Tag Output | 2181-2182 | Pass to StyleTracker |

**Total lines to migrate:** ~250 lines

### Dependencies

**From `legacy/config.py`:**
- `TENSION_EVAL_MIN`, `TENSION_EVAL_MAX`
- `TENSION_MOBILITY_THRESHOLD`, `TENSION_MOBILITY_NEAR`, `TENSION_MOBILITY_DELAY`
- `TENSION_CONTACT_JUMP`, `TENSION_CONTACT_DELAY`, `TENSION_CONTACT_DIRECT`
- `TENSION_TREND_SELF`, `TENSION_TREND_OPP`
- `TENSION_SUSTAIN_MIN`, `TENSION_SUSTAIN_VAR_CAP`
- `TENSION_SYMMETRY_TOL`
- `NEUTRAL_TENSION_BAND`

**From `legacy/thresholds.py`:**
- `TENSION_CONTACT_DELAY`

**From AnalysisContext (computed elsewhere):**
- `delta_eval_float` - Eval change
- `delta_self_mobility`, `delta_opp_mobility` - Mobility changes
- `contact_delta_played`, `contact_ratio_*` - Contact metrics
- `phase_ratio` - Game phase
- `self_trend`, `opp_trend` - Follow-up trends
- `followup_tail_self` - Next-step mobility
- `structural_shift_signal` - Structural change flag
- `contact_trigger` - Contact event flag

### Algorithm Sketch

```python
class TensionDetector(TagDetector):
    def detect(self, ctx: AnalysisContext) -> List[str]:
        tags = []

        # 1. Eval band check
        if not (TENSION_EVAL_MIN <= ctx.delta_eval <= TENSION_EVAL_MAX):
            return tags

        # 2. Mobility symmetry check
        mobility_cross = ctx.delta_self_mobility * ctx.delta_opp_mobility
        if mobility_cross >= 0:  # Not opposite directions
            return tags

        # 3. Phase check
        phase_bucket = _phase_bucket(ctx.phase_ratio)
        if ctx.phase_ratio <= 0.5:
            return tags

        # 4. Threshold adjustment
        tension_threshold = TENSION_DELTA_END if endgame else TENSION_DELTA_MID

        # 5. Core criteria
        mobility_core = (
            self_mag >= TENSION_MOBILITY_THRESHOLD
            and opp_mag >= TENSION_MOBILITY_THRESHOLD
            and mobility_cross < 0
            and symmetry_ok
        )

        # 6. Delayed criteria
        sustained_window = (variance checks, trend checks)

        # 7. Trigger detection
        if triggered:
            tags.append("tension_creation")

        # 8. Neutral band
        if neutral_band and not triggered:
            tags.append("neutral_tension_creation")

        return tags
```

### Files to Create

1. **`rule_tagger2/detectors/tension.py`** (~250 lines)
   - `TensionDetector` class
   - Helper functions (threshold, phase bucket)
   - Full detection logic

2. **`tests/test_tension_detector.py`** (~80 lines)
   - Unit tests with known positions
   - Comparison with legacy results

---

## 📋 Detector 2: Prophylaxis (ProphylaxisDetector)

### Location in legacy/core.py

| Component | Lines | Description |
|-----------|-------|-------------|
| Initialization | 561-563 | Flags: `prophylactic_move`, `prophylaxis_pattern_override`, etc. |
| Main Detection Logic | 1030-1194 | Preventive score, threat delta, pattern detection |
| Plan Drop | 1196-1246 | Plan disruption via `detect_prophylaxis_plan_drop()` |
| Quality Classification | 1347-1392 | Subtle/balanced/aggressive/failed |
| Result Assembly | 2071, 2102-2103 | Tag output |

**Total lines to migrate:** ~300 lines

### Dependencies

**From `legacy/prophylaxis.py`:**
- `classify_prophylaxis_quality()`
- `clamp_preventive_score()`
- `estimate_opponent_threat()`
- `is_prophylaxis_candidate()`
- `prophylaxis_pattern_reason()`
- `ProphylaxisConfig`

**From `engine_utils/prophylaxis.py`:**
- `detect_prophylaxis_plan_drop()` - Returns `PlanDropResult`

**From `legacy/config.py` / `legacy/thresholds.py`:**
- `CONTROL_TACTICAL_WEIGHT_CEILING`
- `CONTROL_BLUNDER_THREAT_THRESH`
- `CONTROL_VOLATILITY_DROP_CP`
- `CONTROL_OPP_MOBILITY_DROP`
- `CONTROL_TENSION_DELTA`
- `PLAN_DROP_*` (depth, multipv, psi_min, etc.)

**From AnalysisContext:**
- `tactical_weight`
- `volatility_drop_cp`, `opp_mobility_drop`
- `change_played_vs_before["structure"]`, `["king_safety"]`, `["mobility"]`
- `opp_change_played_vs_before["tactics"]`, `["mobility"]`
- `self_trend`, `opp_trend`

### Algorithm Sketch

```python
class ProphylaxisDetector(TagDetector):
    def detect(self, ctx: AnalysisContext) -> List[str]:
        tags = []

        # 1. Candidate check
        if not is_prophylaxis_candidate(ctx.board, ctx.played_move, ...):
            return tags

        # 2. Compute preventive score
        preventive_score = (
            max(0, threat_delta) * 0.5
            + max(0, -opp_mobility_change) * 0.3
            + max(0, -opp_tactics_change) * 0.2
            + max(0, -opp_trend) * 0.15
        )

        # 3. Pattern support override
        pattern_reason = prophylaxis_pattern_reason(...)
        if pattern_support and preventive_score >= trigger * 0.75:
            adjusted_preventive = max(preventive_score, trigger)

        # 4. Prophylactic move detection
        if adjusted_preventive >= PROPHYLAXIS_CONFIG.preventive_trigger:
            prophylactic_move = True

        # 5. Plan drop detection (optional, expensive)
        plan_drop_result = detect_prophylaxis_plan_drop(...)
        if plan_drop_result.passed:
            prophylactic_move = True

        # 6. Quality classification
        if prophylactic_move:
            quality = classify_prophylaxis_quality(...)
            tags.append(quality)  # e.g., "prophylactic_subtle"

        return tags
```

### Files to Create

1. **`rule_tagger2/detectors/prophylaxis.py`** (~300 lines)
   - `ProphylaxisDetector` class
   - Integration with existing prophylaxis helpers
   - Plan drop integration

2. **`tests/test_prophylaxis_detector.py`** (~100 lines)
   - Known prophylactic positions
   - Plan drop scenarios

---

## 📋 Detector 3: Control over Dynamics (ControlDetector)

### Location in legacy/core.py

| Component | Lines | Description |
|-----------|-------|-------------|
| Helper: `_collect_control_metrics()` | 280-340 | Volatility, mobility, king safety, tension |
| Helper: `_format_control_summary()` | 342-374 | Format control notes |
| Initialization | 556-557 | `control_over_dynamics = False`, subtype tracking |
| Subtype Detection | 850-1315 | Piece control, pawn control, simplification, prophylaxis |
| Priority & Selection | 1315-1342 | Select highest priority subtype |
| Result Assembly | 2055, 2159-2160 | Tag output |

**Total lines to migrate:** ~280 lines

### Dependencies

**From `legacy/config.py`:**
- `CONTROL_EVAL_DROP`, `CONTROL_VOLATILITY_DROP_CP`
- `CONTROL_OPP_MOBILITY_DROP`, `CONTROL_KING_SAFETY_THRESH`
- `CONTROL_TENSION_DELTA_*`, `CONTROL_SIMPLIFY_MIN_EXCHANGE`
- `CONTROL_TACTICAL_WEIGHT_CEILING`
- `CONTROL_COOLDOWN_PLIES`
- `CONTROL_PHASE_WEIGHTS`

**From AnalysisContext:**
- `volatility_drop_cp`
- `opp_mobility_drop`, `self_mobility_change`
- `king_safety_gain`, `opp_tactics_change_eval`
- `tension_delta`
- `phase_bucket`, `phase_ratio`
- `current_ply`, `last_cod_ply`, `last_cod_subtype` (for cooldown)

### Algorithm Sketch

```python
class ControlDetector(TagDetector):
    def detect(self, ctx: AnalysisContext) -> List[str]:
        tags = []
        candidates = []

        # 1. Cooldown check
        if self._in_cooldown(ctx.current_ply, ctx.last_cod_ply):
            return tags

        # 2. Piece control subtype
        if (ctx.volatility_drop_cp >= VOLATILITY_DROP_CP * 0.8
            and ctx.opp_mobility_drop >= OPP_MOBILITY_DROP):
            candidates.append(("piece_control", score))

        # 3. Pawn control subtype
        if (ctx.tension_delta <= threshold
            and ctx.opp_mobility_drop >= OPP_MOBILITY_DROP * 0.6):
            candidates.append(("pawn_control", score))

        # 4. Simplification subtype
        if (ctx.king_safety_gain >= KS_THRESH
            and ctx.eval_drop <= EVAL_DROP):
            candidates.append(("control_simplification", score))

        # 5. Prophylaxis subtype (if not handled by ProphylaxisDetector)
        # This may be delegated or merged

        # 6. Select highest priority
        if candidates:
            selected = max(candidates, key=priority_func)
            tags.append("control_over_dynamics")
            tags.append(selected[0])  # specific subtype

        return tags
```

### Files to Create

1. **`rule_tagger2/detectors/control.py`** (~280 lines)
   - `ControlDetector` class
   - Subtype detection logic
   - Priority selection

2. **`tests/test_control_detector.py`** (~80 lines)
   - Known control positions
   - Subtype priority tests

---

## 🔗 Shared Dependencies

### Metrics Computation (to extract to `analysis/`)

These are currently scattered across `legacy/core.py` and `legacy/analysis.py`:

**`analysis/volatility.py`** (~80 lines)
- Volatility computation from eval sequences
- Phase-dependent adjustments

**`analysis/contact.py`** (~60 lines)
- Contact ratio computation
- Contact delta tracking

**`analysis/mobility_trends.py`** (~100 lines)
- Follow-up simulation
- Trend computation (self/opp)

**`analysis/phase.py`** (~40 lines)
- Phase bucket classification
- Phase ratio computation

---

## 📊 Migration Timeline (P2)

| Day | Task | Files | Lines |
|-----|------|-------|-------|
| **Day 1** | TensionDetector skeleton + basic logic | detectors/tension.py | 150 |
| **Day 2** | TensionDetector complete + tests | +test_tension_detector.py | +130 |
| **Day 3** | ProphylaxisDetector skeleton | detectors/prophylaxis.py | 180 |
| **Day 4** | ProphylaxisDetector complete + tests | +test_prophylaxis_detector.py | +200 |
| **Day 5** | ControlDetector skeleton + basic logic | detectors/control.py | 150 |
| **Day 6** | ControlDetector complete + tests | +test_control_detector.py | +180 |
| **Day 7** | Integration testing + golden regression | - | - |

**Total:** ~990 lines (3 detectors + tests)

---

## ✅ Verification Checklist (Per Detector)

Before marking a detector "done":

- [ ] File compiles without errors (`python3 -m compileall`)
- [ ] Unit tests pass (at least 5 test cases)
- [ ] Golden regression: 100% tag match on 10 known positions
- [ ] File size < 350 lines
- [ ] Imports only from:
  - `rule_tagger2.detectors.base`
  - `rule_tagger2.orchestration.context`
  - `rule_tagger2.legacy.config` / `legacy.thresholds` (read-only)
  - `rule_tagger2.legacy.prophylaxis` (helper functions OK for now)
  - Standard library
- [ ] No circular imports
- [ ] Documentation: Docstrings for class and main methods

---

## 🚨 Red Flags to Avoid

1. **Do NOT modify legacy files yet** - Only read from them
2. **Do NOT change threshold values** - Use exact same values from config
3. **Do NOT optimize logic** - Copy-paste first, optimize in P4
4. **Do NOT skip golden tests** - Every detector must match legacy 100%
5. **Do NOT create large detectors** - If > 350 lines, split further

---

## 📝 Next Steps After P2

After these 3 detectors are migrated and verified:

1. Update `pipeline.py` to call them (P3)
2. Run full golden regression (all 10+ positions)
3. Add them to CI gate
4. Document in `REFACTORING_STATUS.md`
5. Move to next 3 detectors (structural, king_safety, initiative)

---

**Status:** Ready for P2 execution
**Frozen at:** Lines 256-2182 in `legacy/core.py`
**Target completion:** 7 days
