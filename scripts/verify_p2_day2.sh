#!/bin/bash
# P2 Day 2 验收检查脚本
# 运行所有验收标准测试

set +e  # 继续执行即使有错误

echo "================================================================"
echo "P2 Day 2 验收检查"
echo "================================================================"
echo ""

PASSED=0
FAILED=0

# Helper function
check() {
    local name="$1"
    shift
    echo -n "$name... "
    if "$@" > /dev/null 2>&1; then
        echo "✅"
        ((PASSED++))
        return 0
    else
        echo "❌"
        ((FAILED++))
        return 1
    fi
}

# 1. 编译检查
echo "【编译检查】"
check "Facade 编译" python3 -m compileall rule_tagger2/core/facade.py
check "Pipeline 编译" python3 -m compileall rule_tagger2/orchestration/pipeline.py
check "TensionDetector 编译" python3 -m compileall rule_tagger2/detectors/tension.py
echo ""

# 2. 导入测试
echo "【导入测试】"
check "Facade 导入" python3 -c "from rule_tagger2.core.facade import tag_position"
check "Pipeline 导入" python3 -c "from rule_tagger2.orchestration.pipeline import run_pipeline"
check "TensionDetector 导入" python3 -c "from rule_tagger2.detectors import TensionDetector"
echo ""

# 3. 文件大小检查
echo "【文件大小检查 (<400 行)】"
facade_lines=$(wc -l < rule_tagger2/core/facade.py)
pipeline_lines=$(wc -l < rule_tagger2/orchestration/pipeline.py)
tension_lines=$(wc -l < rule_tagger2/detectors/tension.py)

echo -n "Facade ($facade_lines 行)... "
if [ "$facade_lines" -lt 400 ]; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi

echo -n "Pipeline ($pipeline_lines 行)... "
if [ "$pipeline_lines" -lt 400 ]; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi

echo -n "TensionDetector ($tension_lines 行)... "
if [ "$tension_lines" -lt 400 ]; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi
echo ""

# 4. 单元测试
echo "【单元测试】"
check "TensionDetector 单元测试" python3 -m unittest tests.test_tension_detector
echo ""

# 5. 快速功能测试
echo "【功能测试】"
if [ -f scripts/test_pipeline_quick.py ]; then
    check "快速功能测试" python3 scripts/test_pipeline_quick.py
else
    echo "快速功能测试... ⚠️  (脚本不存在)"
fi
echo ""

# 6. 文档检查
echo "【文档检查】"
echo -n "P2_DAY2_SUMMARY.md... "
if [ -f P2_DAY2_SUMMARY.md ]; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi

echo -n "P2_DAY2_INTEGRATION_REPORT.md... "
if [ -f P2_DAY2_INTEGRATION_REPORT.md ]; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi

echo -n "REFACTORING_STATUS.md 已更新... "
if grep -q "P2 Day 2" REFACTORING_STATUS.md; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi
echo ""

# 总结
echo "================================================================"
echo "验收结果"
echo "================================================================"
echo "通过: $PASSED"
echo "失败: $FAILED"
echo "总计: $((PASSED + FAILED))"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo "🎉 所有验收标准通过！P2 Day 2 完成。"
    exit 0
else
    echo "⚠️  有 $FAILED 项验收失败，请检查上述错误。"
    exit 1
fi
