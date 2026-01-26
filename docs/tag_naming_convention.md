# Tag Naming Convention

**Version:** 2.1
**Last Updated:** 2025-11-05
**Status:** Active

---

## Overview

This document defines the naming conventions for chess style tags in the `style_tag_v9` project. Consistent tag naming improves code readability, reduces errors, and facilitates automatic validation.

All tags must follow these conventions. Non-compliant tag names should be flagged during code review and CI checks.

---

## Core Principles

### 1. **snake_case Format**

All tag names MUST use `snake_case` (lowercase with underscores).

✅ **Good:**
- `tension_creation`
- `neutral_tension_creation`
- `control_over_dynamics`

❌ **Bad:**
- `TensionCreation` (PascalCase)
- `tension-creation` (kebab-case)
- `TENSION_CREATION` (UPPER_CASE)

---

### 2. **Family Prefix**

Tags within the same family SHOULD share a common prefix when logical.

✅ **Good:**
- `cod_simplify`, `cod_plan_kill`, `cod_freeze_bind` (control family)
- `structural_integrity`, `structural_compromise_dynamic` (structural family)

✅ **Acceptable:**
- `tension_creation`, `premature_attack` (tension family, different prefixes OK)

❌ **Bad:**
- `simplify_control`, `control_plan_kill` (inconsistent prefix ordering)

---

### 3. **Tense Consistency**

Tags describing **actions** SHOULD use present tense or gerund (-ing) form.
Tags describing **states** SHOULD use nouns or adjectives.

✅ **Actions (Present/Gerund):**
- `tension_creation` (gerund: creating tension)
- `initiative_exploitation` (gerund: exploiting initiative)
- `prophylactic_move` (present: move that is prophylactic)

✅ **States (Noun/Adjective):**
- `structural_integrity` (noun: state of having integrity)
- `first_choice` (noun: the first choice)
- `tactical_sensitivity` (noun: degree of sensitivity)

❌ **Bad:**
- `tension_created` (past tense, avoid)
- `exploiting_initiative` (too verbose, prefer `initiative_exploitation`)

---

### 4. **Quality Suffixes**

When distinguishing quality levels, use descriptive suffixes consistently.

✅ **Good:**
- `tactical_sacrifice` (accurate/sound)
- `inaccurate_tactical_sacrifice` (minor flaw)
- `speculative_sacrifice` (uncertain)
- `desperate_sacrifice` (poor situation)

✅ **Also Good:**
- `constructive_maneuver` (positive)
- `neutral_maneuver` (neutral)
- `misplaced_maneuver` (negative)

❌ **Bad:**
- `sacrifice_good`, `sacrifice_bad` (suffix should be descriptive, not vague)
- `sacrifice_1`, `sacrifice_2` (never use numeric suffixes)

---

### 5. **Neutral Prefix Convention**

Tags representing **neutral** evaluation bands SHOULD use `neutral_` prefix.

✅ **Good:**
- `neutral_tension_creation` (tension in neutral eval band)
- `neutral_maneuver` (maneuver without clear advantage)

❌ **Bad:**
- `tension_neutral_creation` (prefix should come first)
- `neutral_tension` (too vague, specify the action)

---

### 6. **Avoid Redundancy**

Do not repeat the family name if the tag already implies it.

✅ **Good:**
- `control_over_dynamics` (parent)
- `cod_simplify` (child, uses abbreviation)

❌ **Bad:**
- `control_over_dynamics_simplify` (redundant, too long)
- `control_simplify_control` (repeats "control")

---

### 7. **Clarity Over Brevity**

Prefer descriptive names over abbreviations, except for well-established families.

✅ **Good:**
- `structural_compromise_dynamic` (clear)
- `cod_king_safety_shell` (CoD is well-established abbreviation)

❌ **Bad:**
- `struct_comp_dyn` (too abbreviated)
- `kss_move` (cryptic abbreviation)

---

## Common Anti-Patterns

### ❌ Anti-Pattern 1: Inconsistent Casing
```python
# BAD
"TensionCreation"
"Tension_Creation"
"TENSION_CREATION"

# GOOD
"tension_creation"
```

### ❌ Anti-Pattern 2: Mixing Prefixes and Suffixes
```python
# BAD
"sacrifice_tactical"  # inconsistent ordering
"tactical_sacrifice"  # correct

# GOOD
"tactical_sacrifice"
"tactical_combination_sacrifice"
"tactical_initiative_sacrifice"
```

### ❌ Anti-Pattern 3: Using Numbers as Qualifiers
```python
# BAD
"maneuver_1"
"maneuver_2"
"maneuver_quality_3"

# GOOD
"constructive_maneuver"
"neutral_maneuver"
"misplaced_maneuver"
```

### ❌ Anti-Pattern 4: Verb Tense Confusion
```python
# BAD
"tension_created"  # past tense
"creating_tension"  # present continuous (too verbose)

# GOOD
"tension_creation"  # gerund noun
```

### ❌ Anti-Pattern 5: Overly Generic Names
```python
# BAD
"good_move"
"bad_move"
"special_move"

# GOOD
"first_choice"
"missed_tactic"
"prophylactic_move"
```

---

## Family-Specific Conventions

### Initiative Family
- **Prefix:** `initiative_` or standalone
- **Examples:** `initiative_exploitation`, `initiative_attempt`, `deferred_initiative`

### Tension Family
- **Prefix:** `tension_`, `premature_`, or `file_`
- **Examples:** `tension_creation`, `neutral_tension_creation`, `premature_attack`, `file_pressure_c`

### Maneuver Family
- **Prefix:** None (use descriptive adjective)
- **Examples:** `constructive_maneuver`, `neutral_maneuver`, `misplaced_maneuver`, `maneuver_opening`

### Sacrifice Family
- **Prefix:** None (use qualifier + `sacrifice`)
- **Examples:** `tactical_sacrifice`, `positional_sacrifice`, `speculative_sacrifice`, `desperate_sacrifice`

### Control Family (CoD)
- **Prefix:** `cod_` for subtypes, `prophylactic_` for related tags
- **Examples:** `control_over_dynamics`, `cod_simplify`, `cod_plan_kill`, `prophylactic_move`

### Structural Family
- **Prefix:** `structural_`
- **Examples:** `structural_integrity`, `structural_compromise_dynamic`, `structural_compromise_static`

### Meta Family
- **Prefix:** None (use descriptive noun)
- **Examples:** `tactical_sensitivity`, `first_choice`, `missed_tactic`, `conversion_precision`

---

## Validation and Enforcement

### 1. **Schema Validator**
Run `tag_schema_validator.py` to check for:
- Invalid characters (non-lowercase, non-underscore)
- Reserved keywords (conflict with Python builtins)
- Duplicate names across families

### 2. **CI Lint Check**
The CI pipeline includes a "tag name lint" step that:
- Validates all tag names against this convention
- Blocks PRs introducing non-compliant names
- Suggests corrections for common errors

### 3. **Code Review Checklist**
When adding new tags, reviewers should verify:
- [ ] Uses `snake_case`
- [ ] Follows family prefix convention
- [ ] Tense is consistent (action vs state)
- [ ] No redundancy or abbreviations
- [ ] Not using numeric suffixes
- [ ] Descriptive and clear

---

## Migration and Renaming

### Deprecation Process
1. Mark old tag as `deprecated: true` in `tag_catalog.yml`
2. Add new tag name to `aliases` list
3. Update `tag_renames_v2.py` with mapping
4. Run migration script: `python3 scripts/apply_tag_renames.py`
5. After 2 releases, remove deprecated tag entirely

### Example
```yaml
# tag_catalog.yml
old_tag_name:
  deprecated: true
  aliases: ["new_tag_name"]
  since_version: "2.0"

new_tag_name:
  deprecated: false
  aliases: []
  since_version: "2.1"
```

---

## References

- **Tag Catalog:** [`rule_tagger2/core/tag_catalog.yml`](../rule_tagger2/core/tag_catalog.yml)
- **Schema Validator:** [`rule_tagger2/core/tag_schema_validator.py`](../rule_tagger2/core/tag_schema_validator.py)
- **Rename Mapping:** [`rule_tagger2/versioning/tag_renames_v2.py`](../rule_tagger2/versioning/tag_renames_v2.py)

---

## Changelog

| Version | Date       | Changes                                      |
|---------|------------|----------------------------------------------|
| 2.1     | 2025-11-05 | Initial version with 7 core principles       |
| 2.0     | 2025-10-01 | Legacy naming (pre-convention)               |

---

**Questions or Suggestions?**
Open an issue in the project repository with the `tag-naming` label.
