# Tension Boundary Decision Guide

> **Version:** 2.0
> **Last Updated:** 2025-11-06
> **Purpose:** Define precise boundaries between `tension_creation` and `neutral_tension_creation` tags

---

## Table of Contents

1. [Overview](#overview)
2. [Decision Tree](#decision-tree)
3. [Core Distinctions](#core-distinctions)
4. [Threshold Parameters](#threshold-parameters)
5. [Examples & Counter-Examples](#examples--counter-examples)
6. [Edge Cases](#edge-cases)
7. [Implementation Notes](#implementation-notes)

---

## Overview

The **tension** tag family captures moves that introduce or maintain dynamic complexity in a position. The key distinction is between:

- **`tension_creation`**: Moves that actively increase tactical complexity with meaningful threats
- **`neutral_tension_creation`**: Moves that maintain complexity without creating immediate threats

This document provides clear decision criteria to distinguish between these two tags.

---

## Decision Tree

```
Is there measurable position dynamics change?
│
├─ NO → No tension tag
│
└─ YES → Continue to Q2
    │
    Is there a significant evaluation advantage or tactical threat?
    │
    ├─ YES (score_gap ≥ 15cp OR material advantage OR forcing moves)
    │   └─ Tag: tension_creation
    │
    └─ NO → Continue to Q3
        │
        Is there meaningful mobility/contact change?
        │
        ├─ YES (mobility Δ ≥ 0.10 OR contact Δ ≥ 0.01)
        │   └─ Tag: neutral_tension_creation
        │
        └─ NO → No tension tag (insufficient evidence)
```

---

## Core Distinctions

### Tension Creation (Active)

**Definition**: Moves that create **immediate tactical threats** or **forcing sequences** that demand opponent response.

**Key Characteristics**:
- ✅ Evaluation advantage (score_gap ≥ 15cp)
- ✅ Forcing moves (checks, captures, threats)
- ✅ Material imbalance creation
- ✅ Direct attacks on opponent pieces/king
- ✅ Opening tactical sequences

**Typical Scenarios**:
- Pawn breaks in closed positions
- Piece sacrifices for initiative
- Central pawn advances with tactical ideas
- Opening files/diagonals with immediate threats
- Creating pins, forks, or discovered attacks

### Neutral Tension Creation (Passive)

**Definition**: Moves that **maintain** or **slightly increase** complexity without creating immediate threats.

**Key Characteristics**:
- ✅ Balanced evaluation (|score_gap| < 15cp)
- ✅ Non-forcing moves
- ✅ Increases piece mobility (Δ ≥ 0.10)
- ✅ Increases contact complexity (Δ ≥ 0.01)
- ✅ Symmetrical pawn structures

**Typical Scenarios**:
- Developing moves in the opening
- Quiet pawn advances maintaining tension
- Rook lifts without immediate threats
- Bishop fianchetto preparations
- Maintaining pawn chains

---

## Threshold Parameters

### Primary Thresholds (Tension Creation)

| Parameter | Threshold | Description |
|-----------|-----------|-------------|
| `min_score_gap` | 15 cp | Minimum evaluation advantage to trigger tension_creation |
| `min_mobility_delta` | 0.05 | Minimum mobility change for active tension |
| `min_contact_ratio` | 0.02 | Minimum contact ratio change indicating forcing moves |
| `forcing_move_bonus` | +20 cp | Bonus for checks, captures, or mate threats |

### Evidence Gates (Neutral Tension Creation)

| Parameter | Threshold | Description |
|-----------|-----------|-------------|
| `min_mobility_evidence` | 0.10 | Minimum mobility change to avoid false positives |
| `min_contact_evidence` | 0.01 | Minimum contact change to avoid false positives |
| `max_eval_drop` | -50 cp | Maximum acceptable evaluation drop |

### Configuration

Thresholds are loaded from `config/metrics_thresholds.yml`:

```yaml
tension:
  min_score_gap: 15
  min_mobility_delta: 0.05
  min_contact_ratio: 0.02
  forcing_move_bonus: 20
  min_mobility_evidence: 0.10
  min_contact_evidence: 0.01
  max_eval_drop: -50
```

---

## Examples & Counter-Examples

### Example 1: Tension Creation (Pawn Break)

**Position**: Closed Sicilian, move d4 (White)

```
FEN: r1bqkb1r/pp1n1ppp/2p1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 7
Move: d4 (UCI: d2d4)
```

**Metrics**:
- Score gap: +35 cp (before: +10, after: +45)
- Mobility delta: +0.18
- Contact ratio: +0.03 (opening center)

**Decision**: ✅ `tension_creation`

**Reasoning**:
- Evaluation advantage ≥ 15cp ✓
- Opens central files with tactical ideas
- Forces opponent response (cxd4 or maintain pawn)

---

### Example 2: Neutral Tension Creation (Development)

**Position**: Italian Game, move Bc5 (Black)

```
FEN: r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4
Move: Bc5 (UCI: f8c5)
```

**Metrics**:
- Score gap: +5 cp → +3 cp (balanced)
- Mobility delta: +0.12
- Contact ratio: +0.01

**Decision**: ✅ `neutral_tension_creation`

**Reasoning**:
- Evaluation balanced (|5| < 15cp) ✗ for active tension
- Mobility increase ≥ 0.10 ✓
- Development move maintaining complexity
- No immediate threats

---

### Counter-Example 1: No Tension (Quiet Move)

**Position**: Closed position, move h3 (White)

```
FEN: r1bq1rk1/ppp1bppp/2np1n2/4p3/2BPP3/2P2N2/PP3PPP/RNBQ1RK1 w - - 0 8
Move: h3 (UCI: h2h3)
```

**Metrics**:
- Score gap: 0 cp
- Mobility delta: +0.02 (below threshold)
- Contact ratio: 0.00

**Decision**: ❌ No tension tag

**Reasoning**:
- No evaluation advantage
- Mobility change < 0.10
- No contact change
- Prophylactic move (prevents Bg4), not tension

---

### Counter-Example 2: False Neutral (Opening Book)

**Position**: Starting position, move e4 (White)

```
FEN: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
Move: e4 (UCI: e2e4)
```

**Metrics**:
- Score gap: +25 cp (opening advantage)
- Mobility delta: +0.08 (below evidence gate)
- Contact ratio: 0.00

**Decision**: ❌ No tension tag (insufficient evidence)

**Reasoning**:
- **Evidence gate failure**: mobility Δ < 0.10 AND contact Δ < 0.01
- Opening book moves often have inflated scores
- No meaningful dynamic content yet

---

## Edge Cases

### Edge Case 1: Mutual Tension (Symmetrical Breaks)

**Scenario**: Both sides have pawn breaks available, maintaining balanced tension.

**Example**: d4-d5 vs e5-e4 in French Defense

**Decision**:
- If evaluation balanced: `neutral_tension_creation`
- If one side gains advantage: `tension_creation`

**Rationale**: Symmetry indicates mutual threats, not one-sided advantage.

---

### Edge Case 2: Delayed Tactics (Seeds for Later)

**Scenario**: Move prepares tactical blow 2-3 moves later, but no immediate threat.

**Example**: Rook lift (Ra3-h3) preparing kingside attack

**Decision**:
- Current move: `neutral_tension_creation` (no immediate threat)
- Follow-up attacking move: `tension_creation`

**Rationale**: Tag reflects **immediate** position characteristics, not future plans.

---

### Edge Case 3: Endgame Activation

**Scenario**: King activation or pawn push in simplified endgame.

**Example**: Ke2-d3 centralizing king in K+P endgame

**Metrics**:
- Score gap: varies with position
- Mobility: often low in endgame
- Contact: minimal

**Decision**:
- Apply **relaxed thresholds** in endgame:
  - min_mobility_evidence: 0.05 (reduced from 0.10)
  - Allow endgame_phase_bonus: +10 cp

**Rationale**: Endgames have lower absolute mobility/contact values.

---

## Implementation Notes

### TensionDetector Logic (Simplified)

```python
# In rule_tagger2/detectors/tension.py

def _detect_tension_type(self, ctx: AnalysisContext) -> Optional[str]:
    """Determine tension type based on decision tree."""

    # Q1: Measurable dynamics?
    if not self._has_dynamics_change(ctx):
        return None

    # Q2: Significant advantage or threat?
    if self._has_tactical_advantage(ctx):
        return "tension_creation"

    # Q3: Evidence gate for neutral tension
    if self._passes_evidence_gate(ctx):
        return "neutral_tension_creation"

    return None  # Insufficient evidence

def _has_tactical_advantage(self, ctx: AnalysisContext) -> bool:
    """Check for active tension indicators."""
    thresholds = load_thresholds()

    # Evaluation advantage
    if abs(ctx.score_gap_cp) >= thresholds['min_score_gap']:
        return True

    # Forcing moves
    if ctx.is_check or ctx.is_capture or ctx.mate_threat:
        return True

    # Material imbalance
    if ctx.material_delta_pawns >= 1.0:
        return True

    return False

def _passes_evidence_gate(self, ctx: AnalysisContext) -> bool:
    """Minimum evidence to avoid false positives."""
    thresholds = load_thresholds()

    # Require at least ONE of:
    mobility_ok = ctx.mobility_delta >= thresholds['min_mobility_evidence']
    contact_ok = ctx.contact_ratio_delta >= thresholds['min_contact_evidence']

    return mobility_ok or contact_ok
```

### A/B Testing Hook

The `USE_SPLIT_TENSION_V2` environment variable controls boundary version:

```python
# In pipeline or detector initialization
use_v2_boundary = bool(int(os.getenv("USE_SPLIT_TENSION_V2", "0")))

if use_v2_boundary:
    # Apply stricter evidence gates
    thresholds['min_mobility_evidence'] = 0.10
    thresholds['min_contact_evidence'] = 0.01
else:
    # Legacy behavior (no evidence gates)
    thresholds['min_mobility_evidence'] = 0.05
    thresholds['min_contact_evidence'] = 0.005
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-05-15 | Initial boundary definition |
| 2.0 | 2025-11-06 | Added evidence gates, decision tree, and A/B testing support |

---

## References

- [Tag Catalog](../rule_tagger2/core/tag_catalog.yml): Full tag definitions
- [Tension Detector](../rule_tagger2/detectors/tension.py): Implementation
- [Metrics Thresholds](../config/metrics_thresholds.yml): Configuration values
- [Tag Hierarchy Report](../reports/tags_hierarchy.md): Visual tag relationships
