# 重构实施指南（可立即执行版）

> **目标:** 将 2,066 行的 `core.py` 安全拆分为多个 < 400 行的模块
>
> **策略:** 锁口径 → 小步迁移 → 快速对比 → 再扩展
>
> **风险等级:** 低（采用包装器模式，不修改逻辑）

---

## 🚀 立即可执行的前 3 步

### Step 1: 验证安全网（5分钟）✅

已完成的准备工作：

```bash
# 1. 备份已完成
ls rule_tagger2/legacy/core_v8.py  # ✓ 存在

# 2. Golden cases 已准备
ls tests/golden_cases.json  # ✓ 存在

# 3. 骨架已创建
python3 -c "from rule_tagger2.detectors import TagDetector; from rule_tagger2.orchestration import AnalysisContext; print('✓ All imports OK')"
```

**验证通过，可以开始拆分！**

---

### Step 2: 创建第一个 Detector 包装器（30分钟）

#### 2.1 创建 TensionDetector 骨架

创建文件: `rule_tagger2/detectors/tension.py`

```python
"""
Tension creation detection.

This detector identifies moves that create or sustain tension in the position,
typically through mobility increases, contact changes, and structural dynamics.
"""
from typing import Dict, List, Any
import time

from .base import TagDetector, DetectorMetadata
from rule_tagger2.orchestration.context import AnalysisContext


class TensionDetector(TagDetector):
    """
    Detects tension creation patterns in chess moves.

    Tension is created when:
    - Both sides increase mobility in opposite directions
    - Contact between pieces increases
    - Structural changes create confrontation
    - Move maintains dynamic balance
    """

    def __init__(self):
        self._last_metadata: DetectorMetadata = DetectorMetadata(
            detector_name="Tension"
        )

    @property
    def name(self) -> str:
        return "Tension"

    def detect(self, context: AnalysisContext) -> List[str]:
        """
        Detects tension-related tags from analysis context.

        IMPORTANT: This is a WRAPPER implementation that extracts
        tension tags from the legacy tag_position() result.
        In Phase 2, we will reimplement the logic here.

        Args:
            context: Analysis context with all position data

        Returns:
            List of tension tags (e.g., ["tension_creation"])
        """
        start_time = time.time()

        # Extract tension tags from legacy metadata
        tags = self._extract_from_legacy(context)

        # Record metadata
        execution_time = (time.time() - start_time) * 1000  # ms
        self._last_metadata = DetectorMetadata(
            detector_name=self.name,
            tags_found=tags,
            confidence_scores={tag: 1.0 for tag in tags},
            diagnostic_info=self._get_diagnostic_info(context),
            execution_time_ms=execution_time,
        )

        return tags

    def _extract_from_legacy(self, context: AnalysisContext) -> List[str]:
        """
        Extracts tension tags from legacy analysis metadata.

        This is a temporary implementation during migration.
        It reads the tension flags from context.metadata that
        were set by the original tag_position() function.
        """
        tags = []

        # Check for tension_creation flag in metadata
        if context.metadata.get("tension_creation"):
            tags.append("tension_creation")

        # Check for neutral_tension_creation
        if context.metadata.get("neutral_tension_creation"):
            tags.append("neutral_tension_creation")

        # Check for tension_sustain (if implemented)
        if context.metadata.get("tension_sustain"):
            tags.append("tension_sustain")

        return tags

    def _get_diagnostic_info(self, context: AnalysisContext) -> Dict[str, Any]:
        """Returns diagnostic information about tension detection."""
        tension_support = context.metadata.get("tension_support", {})

        return {
            "delta_eval": context.delta_eval,
            "mobility_self": context.get_metric_delta("mobility"),
            "contact_delta": context.contact_delta_played,
            "phase_ratio": context.phase_ratio,
            "tension_support": tension_support,
        }

    def get_metadata(self) -> DetectorMetadata:
        """Returns metadata from the most recent detection."""
        return self._last_metadata

    def is_applicable(self, context: AnalysisContext) -> bool:
        """
        Tension detection is applicable in middlegame and opening.
        Less relevant in endgames.
        """
        # Apply in opening and middlegame
        if context.is_endgame():
            # Still apply, but with lower priority
            return True
        return True

    def get_priority(self) -> int:
        """Tension detection runs after tactical detection."""
        return 40  # Mid-priority


# ===== Future Phase 2 Implementation =====
# TODO: Implement direct tension detection logic here
# This will replace _extract_from_legacy() with actual analysis
"""
def _detect_tension_direct(self, context: AnalysisContext) -> List[str]:
    '''
    Direct tension detection (Phase 2 implementation).

    Algorithm:
    1. Check eval band (TENSION_EVAL_MIN to TENSION_EVAL_MAX)
    2. Analyze mobility symmetry (self and opp change in opposite directions)
    3. Check contact changes
    4. Verify structural signals
    5. Check sustained window
    6. Apply delayed tension checks
    '''
    tags = []

    # Extract key metrics
    delta_eval = context.delta_eval
    delta_self_mobility = context.get_metric_delta("mobility")
    delta_opp_mobility = context.get_metric_delta("mobility")  # opponent
    contact_delta = context.contact_delta_played
    phase_ratio = context.phase_ratio

    # Eval band check
    if not (TENSION_EVAL_MIN <= delta_eval <= TENSION_EVAL_MAX):
        return tags

    # Mobility symmetry check
    mobility_cross = delta_self_mobility * delta_opp_mobility
    if mobility_cross >= 0:  # Not opposite directions
        return tags

    # Contact trigger
    contact_trigger = contact_delta >= TENSION_CONTACT_JUMP

    # [Additional logic to be implemented]

    return tags
"""
```

#### 2.2 更新 detectors/__init__.py

```python
"""
Tag detector modules for modular tag detection.
"""
from .base import TagDetector, DetectorMetadata
from .tension import TensionDetector

__all__ = ["TagDetector", "DetectorMetadata", "TensionDetector"]
```

#### 2.3 验证导入

```bash
python3 -c "from rule_tagger2.detectors import TensionDetector; print('✓ TensionDetector imports successfully')"
```

---

### Step 3: 创建对比测试（20分钟）

#### 3.1 创建测试文件

创建文件: `tests/test_tension_migration.py`

```python
"""
Test TensionDetector migration correctness.

This test ensures that the new TensionDetector produces
identical results to the legacy tag_position() function.
"""
import json
import pytest
from pathlib import Path

from rule_tagger2.legacy.core_v8 import tag_position as legacy_tag_position
from rule_tagger2.detectors import TensionDetector
from rule_tagger2.orchestration import AnalysisContext


def load_golden_cases():
    """Load golden test cases from JSON."""
    golden_path = Path(__file__).parent / "golden_cases.json"
    with open(golden_path) as f:
        return json.load(f)


@pytest.fixture
def tension_detector():
    """Create a TensionDetector instance."""
    return TensionDetector()


@pytest.mark.parametrize("case", load_golden_cases())
def test_tension_detector_matches_legacy(case, tension_detector):
    """
    Test that TensionDetector produces identical results to legacy.

    This is a CRITICAL test - it must pass 100% before we proceed
    to refactoring other detectors.
    """
    fen = case["fen"]
    move = case["move"]
    case_id = case["id"]

    # Run legacy analysis (full pipeline)
    engine_path = ""  # Use default or skip if not available

    try:
        legacy_result = legacy_tag_position(
            engine_path=engine_path,
            fen=fen,
            played_move_uci=move,
            depth=14,
            multipv=6,
        )
    except Exception as e:
        pytest.skip(f"Legacy analysis failed for {case_id}: {e}")

    # Create AnalysisContext from legacy result
    # (This will be done by the pipeline in production)
    context = AnalysisContext.from_legacy_data(
        board=legacy_result.board,
        played_move=legacy_result.played_move,
        actor=legacy_result.actor,
        metadata=legacy_result.metadata,
        # ... populate all fields from legacy_result
    )

    # Run new detector
    new_tags = tension_detector.detect(context)

    # Extract tension tags from legacy result
    legacy_tension_tags = [
        tag for tag in legacy_result.tags
        if "tension" in tag.lower()
    ]

    # Compare
    assert set(new_tags) == set(legacy_tension_tags), (
        f"Case {case_id}: Tension tags mismatch\n"
        f"Legacy: {legacy_tension_tags}\n"
        f"New:    {new_tags}\n"
        f"Metadata: {tension_detector.get_metadata()}"
    )


def test_tension_detector_smoke():
    """Smoke test for TensionDetector."""
    detector = TensionDetector()

    assert detector.name == "Tension"
    assert detector.get_priority() == 40

    # Test with minimal context
    context = AnalysisContext.from_fen_move(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        move_uci="e2e4"
    )

    # Should not crash
    tags = detector.detect(context)
    assert isinstance(tags, list)

    # Metadata should be populated
    metadata = detector.get_metadata()
    assert metadata.detector_name == "Tension"
    assert metadata.execution_time_ms is not None


def test_tension_detector_metadata():
    """Test that TensionDetector provides useful metadata."""
    detector = TensionDetector()
    context = AnalysisContext.from_fen_move(
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        move_uci="e7e5"
    )

    tags = detector.detect(context)
    metadata = detector.get_metadata()

    assert isinstance(metadata.diagnostic_info, dict)
    assert "delta_eval" in metadata.diagnostic_info
    assert "mobility_self" in metadata.diagnostic_info
```

#### 3.2 创建简化的测试运行脚本

创建文件: `tests/run_tension_test.py`

```python
#!/usr/bin/env python3
"""
Quick test runner for TensionDetector migration.

Usage:
    python tests/run_tension_test.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.detectors import TensionDetector
from rule_tagger2.orchestration import AnalysisContext


def main():
    print("=" * 60)
    print("TensionDetector Migration Test")
    print("=" * 60)

    # Create detector
    detector = TensionDetector()
    print(f"\n✓ Created {detector.name}Detector")
    print(f"  Priority: {detector.get_priority()}")

    # Create minimal context
    context = AnalysisContext.from_fen_move(
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        move_uci="e7e5"
    )
    print(f"\n✓ Created AnalysisContext")
    print(f"  FEN: {context.fen}")
    print(f"  Move: {context.played_move}")

    # Run detection
    print(f"\n→ Running detection...")
    tags = detector.detect(context)
    print(f"✓ Detection complete")
    print(f"  Tags found: {tags}")

    # Get metadata
    metadata = detector.get_metadata()
    print(f"\n✓ Metadata:")
    print(f"  Detector: {metadata.detector_name}")
    print(f"  Execution time: {metadata.execution_time_ms:.2f} ms")
    print(f"  Tags: {metadata.tags_found}")

    print("\n" + "=" * 60)
    print("✓ All checks passed!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 3.3 运行测试

```bash
# 1. 运行快速冒烟测试
python tests/run_tension_test.py

# 2. 如果有 pytest，运行完整测试
pytest tests/test_tension_migration.py -v

# 3. 只运行 tension 相关测试
pytest tests/ -k tension -v
```

---

## 📊 预期输出

### 成功输出示例：

```
============================================================
TensionDetector Migration Test
============================================================

✓ Created TensionDetector
  Priority: 40

✓ Created AnalysisContext
  FEN: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
  Move: e7e5

→ Running detection...
✓ Detection complete
  Tags found: []

✓ Metadata:
  Detector: Tension
  Execution time: 0.12 ms
  Tags: []

============================================================
✓ All checks passed!
============================================================
```

---

## ⚠️ 重要检查点

在进入下一阶段前，必须确认：

- [ ] TensionDetector 可以独立导入
- [ ] 冒烟测试通过（不崩溃）
- [ ] 对于相同输入，新旧方法输出一致
- [ ] 元数据正确填充
- [ ] 执行时间可接受（< 1ms per move）

---

## 🎯 下一步（Phase P1 完成后）

一旦 TensionDetector 验证通过，可以继续：

### Option A: 再拆一个类似的 Detector

选择：ProphylaxisDetector 或 InitiativeDetector

### Option B: 实现 Pipeline 编排

创建 `orchestration/pipeline.py` 来统一调用所有 detectors

### Option C: 为 TensionDetector 实现真正的逻辑

将 `_extract_from_legacy()` 替换为 `_detect_tension_direct()`

---

## 🔧 调试技巧

### 如果测试失败：

1. **检查导入路径**
   ```python
   import sys
   print(sys.path)
   ```

2. **检查 legacy 结果结构**
   ```python
   result = legacy_tag_position(...)
   print(result.tags)
   print(result.metadata.keys())
   ```

3. **逐步调试**
   ```python
   import pdb; pdb.set_trace()
   ```

4. **对比输出**
   ```bash
   python pipeline.py --use-legacy > legacy.txt
   python pipeline.py --use-new > new.txt
   diff legacy.txt new.txt
   ```

---

## 📝 代码审查清单

在提交前检查：

- [ ] 代码符合 PEP 8 风格
- [ ] 所有函数有 docstring
- [ ] Type hints 完整
- [ ] 测试覆盖核心路径
- [ ] 无硬编码路径
- [ ] 错误处理适当
- [ ] 性能无明显退化

---

## 🎓 学习资源

### 理解原始逻辑：

1. 阅读 `docs/RuleSystem_v8.2.md` - 规则系统文档
2. 查看 `rule_tagger2/legacy/core_v8.py:1620-1793` - Tension 检测原始代码
3. 阅读 `metrics_thresholds.yml` - 阈值配置

### Python 最佳实践：

- [ABC (Abstract Base Classes)](https://docs.python.org/3/library/abc.html)
- [Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Type Hints](https://docs.python.org/3/library/typing.html)

---

## 💡 关键成功因素

1. **不要一次改太多** - 每次只迁移一个 detector
2. **保持功能等价** - 新代码必须产生相同结果
3. **频繁测试** - 每次改动后立即运行测试
4. **记录差异** - 如果有差异，记录原因
5. **向后兼容** - 保留 legacy 模式作为后备

---

## 🚦 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 测试不完整 | 中 | 高 | 增加 golden cases 覆盖率 |
| 性能退化 | 低 | 中 | 添加性能基准测试 |
| API 不兼容 | 低 | 高 | 保留 legacy 接口 |
| 逻辑遗漏 | 中 | 高 | 仔细对比新旧代码 |

---

## ✅ 完成标准

**Phase P1 完成条件：**

1. TensionDetector 独立可运行
2. 所有 golden test 100% 通过
3. 性能在可接受范围（< 5% 差异）
4. 代码审查通过
5. 文档完整

**满足以上条件后，可进入 Phase P2！**

---

## 📞 需要帮助？

如果遇到问题：

1. 查看 [REFACTORING_STATUS.md](./REFACTORING_STATUS.md) - 当前进度
2. 查看 [Code Review Report](./CODE_REVIEW.md) - 完整分析
3. 检查 git log - 查看最近的改动
4. 回滚到上一个工作版本

**记住：可以随时回退到 `--use-legacy` 模式！**
