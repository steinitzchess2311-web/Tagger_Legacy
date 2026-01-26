# 下一步操作指南

> P2 Day 2 已完成，以下是后续步骤的详细命令

---

## 1. 运行 Golden Regression 测试

### 基础运行
```bash
python3 scripts/run_golden_regression.py --engine /usr/local/bin/stockfish
```

### Verbose 模式 (推荐首次运行)
```bash
python3 scripts/run_golden_regression.py --engine /usr/local/bin/stockfish -v
```

### 只测试特定case
```bash
# 只测试包含 "tension" 的 case
python3 scripts/run_golden_regression.py --filter tension -v

# 测试单个 case
python3 scripts/run_golden_regression.py --filter case_001 -v
```

### 查看失败报告
```bash
cat test_failures_tension.json
```

---

## 2. 快速功能测试

```bash
# 测试基本功能
python3 scripts/test_pipeline_quick.py

# 使用环境变量切换
NEW_PIPELINE=1 python3 scripts/test_pipeline_quick.py

# 使用 legacy (默认)
NEW_PIPELINE=0 python3 scripts/test_pipeline_quick.py
```

---

## 3. 验证编译和文件大小

### 编译检查
```bash
python3 -m compileall rule_tagger2/core/facade.py
python3 -m compileall rule_tagger2/orchestration/pipeline.py
```

### 文件大小检查
```bash
bash scripts/check_max_lines.sh --path rule_tagger2/core
bash scripts/check_max_lines.sh --path rule_tagger2/orchestration
```

---

## 4. 设置 Pre-commit Hooks

### 创建配置文件

创建 `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        args: ['--line-length=120']

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ['--profile=black', '--line-length=120']

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [
          '--max-line-length=120',
          '--extend-ignore=E203,W503',
        ]

  - repo: local
    hooks:
      - id: check-max-lines
        name: Check file line count
        entry: bash scripts/check_max_lines.sh
        language: system
        pass_filenames: false
        always_run: true
```

### 安装和配置

```bash
# 安装 pre-commit
pip install pre-commit

# 安装 git hooks
pre-commit install

# 手动运行所有 hooks (测试)
pre-commit run --all-files

# 只运行 black
pre-commit run black --all-files

# 只运行 line count check
pre-commit run check-max-lines --all-files
```

---

## 5. 调试不匹配的 Case (如果需要)

### 查看详细诊断

```python
# 添加到 test_pipeline_quick.py 或单独脚本

from rule_tagger2.core.facade import tag_position

fen = "your_fen_here"
move_uci = "e2e4"

# Legacy
result_legacy = tag_position(
    engine_path="/usr/local/bin/stockfish",
    fen=fen,
    played_move_uci=move_uci,
    use_new=False,
)

# New
result_new = tag_position(
    engine_path="/usr/local/bin/stockfish",
    fen=fen,
    played_move_uci=move_uci,
    use_new=True,
)

# 比较
print("Legacy:")
print(f"  tension_creation: {result_legacy.tension_creation}")
print(f"  neutral_tension: {result_legacy.neutral_tension_creation}")
print(f"  analysis_context keys: {result_legacy.analysis_context.keys()}")

print("\nNew:")
print(f"  tension_creation: {result_new.tension_creation}")
print(f"  neutral_tension: {result_new.neutral_tension_creation}")

# 查看中间值
if hasattr(result_new, 'analysis_context'):
    tension_support = result_new.analysis_context.get('analysis_meta', {}).get('tension_support', {})
    print(f"\nTension support data:")
    for key, val in tension_support.items():
        print(f"  {key}: {val}")
```

---

## 6. 开始 P2 Day 3: ProphylaxisDetector

### 参考文档
```bash
cat P2_MIGRATION_CHECKLIST.md | grep -A 50 "Prophylaxis"
```

### 创建文件框架
```bash
# 创建 detector 文件
touch rule_tagger2/detectors/prophylaxis.py

# 创建测试文件
touch tests/test_prophylaxis_detector.py
```

### 提取逻辑位置
```bash
# 查看 prophylaxis 在 legacy 中的位置
grep -n "prophylaxis" rule_tagger2/legacy/core.py | head -20

# 查看行号 561-1392 的代码
sed -n '561,1392p' rule_tagger2/legacy/core.py > /tmp/prophylaxis_extract.py
```

---

## 7. 生成报告

### Golden Regression 统计
```bash
# 运行并保存输出
python3 scripts/run_golden_regression.py -v > golden_regression_report.txt 2>&1

# 只看总结
python3 scripts/run_golden_regression.py | tail -15
```

### 文件行数统计
```bash
# 查看所有 Python 文件行数
find rule_tagger2 -name "*.py" -exec wc -l {} \; | sort -rn | head -20

# 查看新文件行数
wc -l rule_tagger2/core/facade.py \
      rule_tagger2/orchestration/pipeline.py \
      rule_tagger2/detectors/tension.py \
      scripts/run_golden_regression.py
```

### Git Diff 统计
```bash
# 查看改动统计
git diff --stat main...feature/cod-v2-claude

# 查看具体改动
git diff main...feature/cod-v2-claude rule_tagger2/core/facade.py
```

---

## 8. 文档更新检查

### 确认所有文档已更新
```bash
ls -lh P2_DAY*.md REFACTORING_STATUS.md
```

### 查看关键文档
```bash
# 查看 P2 Day 2 总结
cat P2_DAY2_SUMMARY.md

# 查看进度状态
cat REFACTORING_STATUS.md | grep "✅\|⬜"

# 查看详细技术报告
cat P2_DAY2_INTEGRATION_REPORT.md
```

---

## 9. 验收清单

运行以下命令确认所有验收标准：

```bash
#!/bin/bash

echo "=== P2 Day 2 验收检查 ==="
echo ""

echo "1. Facade 编译检查..."
python3 -m compileall rule_tagger2/core/facade.py && echo "✓" || echo "✗"

echo "2. Pipeline 编译检查..."
python3 -m compileall rule_tagger2/orchestration/pipeline.py && echo "✓" || echo "✗"

echo "3. Facade 导入测试..."
python3 -c "from rule_tagger2.core.facade import tag_position; print('✓')" || echo "✗"

echo "4. Pipeline 导入测试..."
python3 -c "from rule_tagger2.orchestration.pipeline import run_pipeline; print('✓')" || echo "✗"

echo "5. TensionDetector 导入测试..."
python3 -c "from rule_tagger2.detectors import TensionDetector; print('✓')" || echo "✗"

echo "6. 文件行数检查..."
bash scripts/check_max_lines.sh && echo "✓" || echo "✗"

echo "7. 快速功能测试..."
python3 scripts/test_pipeline_quick.py > /dev/null 2>&1 && echo "✓" || echo "✗"

echo ""
echo "=== 检查完成 ==="
```

保存为 `scripts/verify_p2_day2.sh`，然后运行：

```bash
chmod +x scripts/verify_p2_day2.sh
bash scripts/verify_p2_day2.sh
```

---

## 10. 环境变量使用示例

### 在脚本中使用
```bash
# 使用 legacy pipeline (默认)
python3 your_script.py

# 使用新 pipeline
NEW_PIPELINE=1 python3 your_script.py

# 临时设置环境变量
export NEW_PIPELINE=1
python3 your_script.py
unset NEW_PIPELINE
```

### 在 Python 代码中使用
```python
import os

# 方式 1: 环境变量
os.environ["NEW_PIPELINE"] = "1"
from rule_tagger2.core.facade import tag_position
result = tag_position(...)

# 方式 2: 参数
result = tag_position(..., use_new=True)

# 方式 3: 直接调用 pipeline
from rule_tagger2.orchestration.pipeline import run_pipeline
result = run_pipeline(..., use_legacy=False)
```

---

## 快速参考

| 任务 | 命令 |
|------|------|
| Golden 回归测试 | `python3 scripts/run_golden_regression.py -v` |
| 快速功能测试 | `python3 scripts/test_pipeline_quick.py` |
| 编译检查 | `python3 -m compileall rule_tagger2/` |
| 文件大小检查 | `bash scripts/check_max_lines.sh` |
| 单元测试 | `python3 -m unittest tests.test_tension_detector` |
| 使用新 pipeline | `NEW_PIPELINE=1 python3 your_script.py` |

---

*Generated: 2025-11-05*
*For: P2 Day 2 → P2 Day 3 transition*
