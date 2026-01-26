# Pipeline Switching Guide

> Quick reference for switching between new orchestrator and legacy pipeline

---

## 🎯 Overview

The rule tagger supports two pipeline modes:
- **New Orchestrator** (default): Modern detector-based architecture with KBE, failed prophylactic, and enhanced diagnostics
- **Legacy Pipeline**: Original implementation for backward compatibility

---

## 🚀 Quick Switch

### Via Environment Variable

```bash
# Enable new orchestrator (default)
export NEW_PIPELINE=1

# Disable (use legacy)
export NEW_PIPELINE=0
# or
unset NEW_PIPELINE
```

### Via CLI Flags

```bash
# Force new pipeline (overrides env var)
python3 scripts/analyze_player_batch.py --new-pipeline --player Kasparov

# Force legacy pipeline (overrides env var)
python3 scripts/analyze_player_batch.py --legacy --player Kasparov

# Use environment variable setting (default)
python3 scripts/analyze_player_batch.py --player Kasparov
```

### Via Python API

```python
from codex_utils import analyze_position

# Force new pipeline
result = analyze_position(fen, move, use_new=True)

# Force legacy pipeline
result = analyze_position(fen, move, use_new=False)

# Use NEW_PIPELINE environment variable (default)
result = analyze_position(fen, move)
```

---

## 🔍 Detection

Check which pipeline was used by inspecting the result:

```python
from rule_tagger2.core.facade import tag_position

result = tag_position(engine_path, fen, move)
engine_meta = result.analysis_context.get("engine_meta", {})

# Check pipeline mode
is_new = engine_meta.get("__new_pipeline__", False)
orchestrator = engine_meta.get("__orchestrator__", "unknown")

print(f"Pipeline: {'New' if is_new else 'Legacy'}")
print(f"Orchestrator: {orchestrator}")
```

---

## ⚙️ Three-State Logic

The `use_new` parameter supports three states:

| Value | Behavior |
|-------|----------|
| `None` (default) | Consult `NEW_PIPELINE` environment variable |
| `True` | Force new orchestrator (ignore env var) |
| `False` | Force legacy pipeline (ignore env var) |

---

## 🆕 New Pipeline Features

Features **only available** in new orchestrator:

1. **Knight-Bishop Exchange Detection**
   - `accurate_knight_bishop_exchange`
   - `inaccurate_knight_bishop_exchange`
   - `bad_knight_bishop_exchange`

2. **Failed Prophylactic Detection**
   - `failed_prophylactic` tag
   - Diagnostics in `analysis_meta['prophylaxis_diagnostics']['failure_check']`

3. **Enhanced Diagnostics**
   - `analysis_meta['knight_bishop_exchange']`
   - Engine consensus metadata
   - Detector evidence trails

---

## 🔧 Troubleshooting

### Verify Current Mode

```bash
# Check environment variable
echo $NEW_PIPELINE

# Test via Python
python3 -c "from rule_tagger2.core.facade import _use_new_pipeline; print('Mode:', 'NEW' if _use_new_pipeline() else 'LEGACY')"
```

### Force Mode for Testing

```bash
# Test with new pipeline
NEW_PIPELINE=1 python3 your_script.py

# Test with legacy pipeline
NEW_PIPELINE=0 python3 your_script.py
```

### Batch Script Examples

```bash
# Analyze with new pipeline
python3 scripts/analyze_player_batch.py \
  --new-pipeline \
  --player Kasparov \
  --max-games 10

# Analyze with legacy pipeline
python3 scripts/analyze_player_batch.py \
  --legacy \
  --player Kasparov \
  --max-games 10
```

---

## 📊 Reporting Integration

Scripts that respect pipeline mode:

- ✅ `scripts/analyze_player_batch.py` (via `--new-pipeline` / `--legacy`)
- ✅ `scripts/detector_evidence_report.py` (detects and warns if legacy)
- ✅ `codex_utils.analyze_position()` (via `use_new` parameter)

---

## 🎓 Best Practices

1. **Default to NEW_PIPELINE=1** for new projects
2. **Use --legacy flag** only when testing backward compatibility
3. **Check `__new_pipeline__` in `engine_meta`** to verify mode at runtime
4. **Document pipeline mode** in analysis reports for reproducibility

---

## 🔗 Related Documentation

- [CHANGELOG.md](CHANGELOG.md) - Full v2.1 feature list
- [rule_tagger2/core/facade.py](rule_tagger2/core/facade.py) - Implementation details
- [scripts/detector_evidence_report.py](scripts/detector_evidence_report.py) - Evidence visualization

---

*Last Updated: 2025-11-07*
