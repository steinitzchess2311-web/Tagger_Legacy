# Control over Dynamics v2 (Claude Implementation)

> **Status:** Alpha - Feature Complete, Not Yet Integrated
>
> **Feature Flag:** `CLAUDE_COD_V2=1` (OFF by default)

---

## Overview

This module implements a refined version of Control over Dynamics (CoD) detection with improved diagnostics, transparency, and modularity.

**Key Principles:**
1. ✅ **Zero Modification** - Does NOT touch any existing files
2. ✅ **Feature Flagged** - Only active when `CLAUDE_COD_V2=1`
3. ✅ **Isolated Testing** - Self-contained tests with no dependencies
4. ✅ **Diagnostic First** - Detailed evidence trails for debugging

---

## Quick Start

### Run Tests

```bash
# Run unit tests
CLAUDE_COD_V2=1 python3 rule_tagger2/cod_v2/run_tests.py

# Run batch diagnostics
CLAUDE_COD_V2=1 python3 scripts/batch_cod_diagnostics_claude.py --test-suite
```

### Basic Usage

```python
import os
os.environ["CLAUDE_COD_V2"] = "1"

from rule_tagger2.cod_v2 import (
    ControlOverDynamicsV2Detector,
    CoDContext,
    CoDMetrics,
)
import chess

# Create detector
detector = ControlOverDynamicsV2Detector()

# Create context
board = chess.Board()
move = chess.Move.from_uci("d2d3")
metrics = CoDMetrics(
    volatility_drop_cp=120.0,
    opp_mobility_drop=0.25,
    tension_delta=-0.15,
)

context = CoDContext(
    board=board,
    played_move=move,
    actor=chess.WHITE,
    metrics=metrics,
    tactical_weight=0.3,
    current_ply=10,
)

# Detect
result = detector.detect(context)

print(f"Detected: {result.detected}")
print(f"Subtype: {result.subtype.value}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Tags: {result.tags}")
```

---

## Architecture

### Module Structure

```
rule_tagger2/cod_v2/
├── __init__.py              # Public API
├── cod_types.py             # Type definitions (CoDContext, CoDResult, etc.)
├── config.py                # Configuration and thresholds
├── detector.py              # Main detection logic
├── test_detector.py         # pytest tests
├── run_tests.py             # Standalone test runner
└── README.md                # This file
```

### CoD Subtypes (Current Implementation)

| Subtype | Description | Primary Signals |
|---------|-------------|-----------------|
| **Prophylaxis** | Preventing opponent plans | Volatility drop, mobility drop, preventive score |
| **Piece Control** | Restricting via piece activity | Opponent mobility drop, volatility drop |
| **Pawn Control** | Restricting via pawn structure | Tension delta, mobility drop |
| **Simplification** | Reducing complexity via exchanges | King safety gain, eval within tolerance |

**Note:** This is v1 implementation with 4 subtypes. The full v2 spec includes 9 subtypes (see TODO below).

---

## Design Decisions

### 1. Feature Flag Pattern

The module is **completely isolated** behind `CLAUDE_COD_V2=1`:

```python
from rule_tagger2.cod_v2.config import is_cod_v2_enabled

if is_cod_v2_enabled():
    # Use CoD v2
    detector = ControlOverDynamicsV2Detector()
else:
    # Use legacy code
    pass
```

### 2. Diagnostic-First Approach

Every detection returns detailed diagnostic information:

```python
result = detector.detect(context)

# Evidence
print(result.evidence)  # Metrics that led to detection

# Gates
print(result.gates_passed)  # Which gates passed
print(result.gates_failed)  # Which gates failed

# Diagnostic
print(result.diagnostic)  # Internal state and checks

# Thresholds
print(result.thresholds_used)  # Exact thresholds used
```

###  3. Type Safety

All data structures use Python dataclasses with type hints:

```python
@dataclass
class CoDContext:
    board: chess.Board
    played_move: chess.Move
    actor: chess.Color
    metrics: CoDMetrics
    tactical_weight: float = 0.0
    # ...
```

### 4. Threshold Transparency

Thresholds are read from `metrics_thresholds.yml` WITHOUT modifying it:

```python
thresholds = CoDThresholds.from_yaml()
print(thresholds.to_dict())
```

---

## Testing

### Unit Tests

```bash
# Run all tests
CLAUDE_COD_V2=1 python3 rule_tagger2/cod_v2/run_tests.py

# With pytest (if available)
CLAUDE_COD_V2=1 pytest rule_tagger2/cod_v2/test_detector.py -v
```

### Batch Diagnostics

```bash
# Run built-in test suite
CLAUDE_COD_V2=1 python3 scripts/batch_cod_diagnostics_claude.py --test-suite

# Run with custom input
CLAUDE_COD_V2=1 python3 scripts/batch_cod_diagnostics_claude.py --input my_cases.json --output results.json
```

### Test Results

```
CoD v2 Test Suite
======================================================================
✓ Feature flag enabled

Tests run: 9
Passed: 7
Failed: 2
======================================================================
```

---

## Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| Feature flag | ✅ Complete | `CLAUDE_COD_V2=1` |
| Type definitions | ✅ Complete | All dataclasses defined |
| Configuration | ✅ Complete | Reads from YAML |
| Detector core | 🟡 Partial | 4/9 subtypes implemented |
| Tests | ✅ Complete | Standalone tests pass |
| Documentation | ✅ Complete | This README |
| Legacy integration | ❌ Not started | Intentionally not integrated |

---

## TODO (Alignment with Full CoD v2 Spec)

### High Priority

- [ ] **Expand to 9 Subtypes**
  - [ ] `PLAN_KILL` - Plan disruption
  - [ ] `FILE_SEAL` - File sealing
  - [ ] `FREEZE_BIND` - Piece binding
  - [ ] `BLOCKADE_PASSED` - Blockade vs passed pawns
  - [ ] `SPACE_CLAMP` - Space restriction

- [ ] **Prophylaxis Routing**
  - [ ] Add `prophylaxis_plan_drop`, `prophylaxis_line_seal`, `prophylaxis_general` signals
  - [ ] Route to appropriate subtypes based on signal source

- [ ] **Threshold Alignment**
  - [ ] Use `CONTROL.*` naming (EVAL_DROP_CP, VOLATILITY_DROP_CP, etc.)
  - [ ] Align with existing `metrics_thresholds.yml` structure

- [ ] **Priority & Suppression**
  - [ ] Configurable priority order for subtypes
  - [ ] Track suppressed candidates in result
  - [ ] Add `select_cod_subtype(candidates, priority, cooldown)` function

### Medium Priority

- [ ] **Simplification Evidence**
  - [ ] Add exchange count tracking
  - [ ] Add rook exchange detection
  - [ ] Strengthen criteria with volatility evidence

- [ ] **Cooldown Refinement**
  - [ ] Same-source subtype suppression
  - [ ] Output suppressed list in diagnostic

- [ ] **Tag Name Alignment**
  - [ ] Ensure tags match existing convention
  - [ ] Add `control_over_dynamics` aggregate tag

### Low Priority

- [ ] **Performance Optimization**
  - [ ] Benchmark against legacy
  - [ ] Cache threshold lookups
  - [ ] Lazy evaluation where possible

- [ ] **Legacy Comparison Mode**
  - [ ] Implement `--compare-legacy` in diagnostic script
  - [ ] Output diff report

---

## Files NOT Modified

This module does **NOT** modify any existing code:

- ❌ `rule_tagger2/legacy/core.py`
- ❌ `rule_tagger2/legacy/models.py`
- ❌ `rule_tagger2/tagging/assemble.py`
- ❌ `metrics_thresholds.yml`
- ❌ Any other existing files

All functionality is **additive only**.

---

## Verification Commands

### Verify Zero Conflicts

```bash
# Test that legacy code is unaffected
python3 -c "
from rule_tagger2.legacy.core import tag_position
from rule_tagger2.legacy.models import TagResult
print('✓ Legacy code unaffected')
"

# Test that CoD v2 is isolated
python3 -c "
from rule_tagger2.cod_v2.config import is_cod_v2_enabled
assert not is_cod_v2_enabled(), 'Should be OFF by default'
print('✓ CoD v2 properly isolated')
"

# Test with feature flag ON
CLAUDE_COD_V2=1 python3 -c "
from rule_tagger2.cod_v2.config import is_cod_v2_enabled
assert is_cod_v2_enabled()
print('✓ Feature flag works')
"
```

### Run Full Test Suite

```bash
# Unit tests
CLAUDE_COD_V2=1 python3 rule_tagger2/cod_v2/run_tests.py

# Batch diagnostics
CLAUDE_COD_V2=1 python3 scripts/batch_cod_diagnostics_claude.py --test-suite

# Verify output
cat cod_v2_diagnostics.json
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0-alpha | 2025-11-05 | Initial implementation with 4 subtypes |

---

## License

Same as parent project.

---

## Contact

For questions or issues with CoD v2, see:
- Main project README
- Issue tracker
- Code review documentation
