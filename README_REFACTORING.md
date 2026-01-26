# Chess Style Tagger v9 - 重构项目

> **状态:** ✅ P0 完成，可以开始 P1
>
> **目标:** 将所有文件控制在 400 行以内，提升可维护性和可测试性

---

## 📋 快速导航

- **[完整代码审查](./CODE_REVIEW.md)** - 10,000+ 行代码的深度分析
- **[重构进度](./REFACTORING_STATUS.md)** - 当前进度和任务追踪
- **[实施指南](./REFACTORING_GUIDE.md)** - 可立即执行的步骤

---

## 🎯 项目概况

### 🆕 CoD v2 快速指引

- 新的九类 Control-over-Dynamics 子类现已在 legacy 管线中启用，详情见 `docs/cod_v2.md`。
- 批量诊断脚本：`python3 scripts/batch_cod_diagnostics.py --input <pgn> --limit 500 --out reports/cod_diag.csv`。
- 所有 CoD 布尔位与子类会在 `TagBundle.debug` 中输出，默认 `control_schema_version=2`。
- 调试可通过 `control_debug_context: true` 或设置环境变量 `CONTROL_DEBUG_CONTEXT=1` 打开 context 快照。

### 当前状态

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| 最大文件 | **2,066 行** | < 400 行 | ❌ |
| 超过400行的文件 | 4 个 | 0 个 | ❌ |
| 测试覆盖率 | ~15% | > 80% | ❌ |
| 模块化程度 | 低 | 高 | ❌ |
| 文档完整度 | 中 | 高 | 🟡 |

### 问题文件

1. **rule_tagger2/legacy/core.py** - 2,066 行 (God Object)
2. **scripts/analyze_player_batch.py** - 702 行
3. **rule_tagger2/legacy/analysis.py** - 469 行
4. **rule_tagger2/tagging/result.py** - 440 行

---

## ✅ 已完成工作（Phase P0）

### 1. 安全网建立

- [x] 备份原始文件为 `core_v8.py`
- [x] 创建 golden test cases ([tests/golden_cases.json](tests/golden_cases.json))
- [x] 10 个测试用例覆盖主要标签类型

### 2. 基础架构骨架

创建的新文件：

```
rule_tagger2/
├── detectors/
│   ├── __init__.py          ✓ 创建
│   └── base.py              ✓ 创建 (87 行)
│
└── orchestration/
    ├── __init__.py          ✓ 创建
    └── context.py           ✓ 创建 (215 行)
```

### 3. 核心抽象

#### TagDetector 接口

```python
class TagDetector(ABC):
    @abstractmethod
    def detect(self, context: AnalysisContext) -> List[str]:
        """返回检测到的标签列表"""
        pass

    @abstractmethod
    def get_metadata(self) -> DetectorMetadata:
        """返回检测元数据"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """检测器名称"""
        pass
```

#### AnalysisContext 数据容器

包含所有检测所需的数据：
- 棋盘状态
- 引擎分析结果
- 位置评估指标
- 计算后的特征
- 元数据

### 4. 验证

```bash
✓ 所有导入成功
✓ 类型定义正确
✓ 无语法错误
✓ 可以开始迁移
```

---

## 🚀 下一步：Phase P1（进行中）

### 目标：创建第一个 Detector

**选择：TensionDetector**

**原因：**
- 独立性强，依赖少
- 逻辑相对清晰
- 易于验证正确性
- 是其他 detector 的良好示例

### 实施步骤

1. **创建 TensionDetector 骨架**
   - 文件：`rule_tagger2/detectors/tension.py`
   - 策略：包装器模式（暂时调用 legacy 逻辑）

2. **创建测试文件**
   - `tests/test_tension_migration.py`
   - `tests/run_tension_test.py`

3. **验证一致性**
   - 运行 golden tests
   - 对比新旧结果
   - 确保 100% 匹配

4. **文档化**
   - 添加 docstrings
   - 记录设计决策
   - 更新 REFACTORING_STATUS.md

---

## 📚 文档结构

### 已创建文档

1. **[CODE_REVIEW.md](./CODE_REVIEW.md)** (完整)
   - 项目结构分析
   - 代码质量评估
   - 问题识别
   - 重构方案
   - 预期成果

2. **[REFACTORING_STATUS.md](./REFACTORING_STATUS.md)** (进行中)
   - 阶段追踪
   - 任务清单
   - 指标监控
   - 开发日志

3. **[REFACTORING_GUIDE.md](./REFACTORING_GUIDE.md)** (完整)
   - 可执行步骤
   - 代码示例
   - 测试方法
   - 调试技巧

4. **[tests/golden_cases.json](./tests/golden_cases.json)** (完整)
   - 10 个测试用例
   - 覆盖各种标签类型

---

## 🏗️ 目标架构

### 当前架构（单体）

```
app.py / pipeline.py
        ↓
rule_tagger2/legacy/core.py (2066 行!)
        ↓
    [所有检测逻辑混在一起]
```

### 目标架构（模块化）

```
app.py / pipeline.py
        ↓
orchestration/pipeline.py
        ↓
    ┌─────────────┴─────────────┐
    ↓                           ↓
detectors/                 orchestration/
├── base.py               ├── context.py
├── tension.py            ├── pipeline.py
├── prophylaxis.py        ├── gating.py
├── control.py            └── result_builder.py
├── initiative.py
├── maneuver.py
├── tactical.py
└── ...
```

### 预期文件大小

| 模块 | 当前 | 目标 | 状态 |
|------|------|------|------|
| TensionDetector | - | ~250 行 | 待创建 |
| ProphylaxisDetector | - | ~300 行 | 待创建 |
| ControlDetector | - | ~200 行 | 待创建 |
| InitiativeDetector | - | ~180 行 | 待创建 |
| ManeuverDetector | - | ~220 行 | 待创建 |
| TacticalDetector | - | ~200 行 | 待创建 |
| Pipeline | - | ~200 行 | 待创建 |
| ResultBuilder | - | ~150 行 | 待创建 |

**所有文件 < 400 行 ✓**

---

## 🎓 重构原则

### 1. 锁口径

- 不修改外部 API
- 保持结果一致性
- 向后兼容

### 2. 小步迁移

- 每次只迁移一个检测器
- 每步都测试
- 频繁提交

### 3. 快速对比

- Golden test cases
- 自动化测试
- 性能基准

### 4. 再扩展

- 先包装，后重构
- 逻辑优化在第二轮
- 持续改进

---

## 🛠️ 工具和命令

### 开发命令

```bash
# 运行 legacy 版本
python pipeline.py --use-legacy

# 运行新版本（迁移后）
python pipeline.py --use-new

# 对比模式
python pipeline.py --compare

# 运行测试
pytest tests/ -v

# 只测试 tension
pytest tests/ -k tension -v

# 代码格式化
black --line-length 100 .
isort --profile black .

# 类型检查
mypy rule_tagger2/
```

### 分析命令

```bash
# 统计代码行数
find rule_tagger2 -name "*.py" -exec wc -l {} \; | sort -rn

# 查找大文件
find . -name "*.py" -exec wc -l {} \; | awk '$1 > 400'

# 测试覆盖率
pytest --cov=rule_tagger2 --cov-report=html

# 复杂度分析
radon cc rule_tagger2/ -a -s
```

---

## 📊 进度追踪

### 阶段概览

| 阶段 | 描述 | 工作量 | 风险 | 状态 |
|------|------|--------|------|------|
| P0 | 安全网建立 | 1天 | 低 | ✅ 完成 |
| P1 | 第一个 Detector | 2-3天 | 低 | 🚧 进行中 |
| P2 | 3个主要 Detector | 1周 | 中 | ⏳ 待开始 |
| P3 | Pipeline + Gating | 1周 | 中 | ⏳ 待开始 |
| P4 | 批处理重构 | 1周 | 中 | ⏳ 待开始 |
| P5 | Legacy 清理 | 3天 | 高 | ⏳ 待开始 |

### 时间估算

- **总工作量：** 4-5 周
- **当前进度：** ~5%
- **预计完成：** 基于实际投入时间

---

## 🎯 成功标准

### 技术指标

- [x] 所有文件 < 400 行
- [ ] 测试覆盖率 > 80%
- [ ] 性能无退化（< 5%）
- [ ] 类型检查通过
- [ ] 代码风格一致

### 质量指标

- [ ] 可读性提升
- [ ] 易于扩展
- [ ] 易于测试
- [ ] 文档完整
- [ ] 向后兼容

### 开发体验

- [ ] 新手可快速上手
- [ ] Bug 定位时间减少 50%
- [ ] 添加新 detector 只需 1 天
- [ ] CI/CD 流畅运行

---

## ⚠️ 重要提醒

### DO ✅

1. ✅ 每次修改后运行测试
2. ✅ 保持 legacy 模式可用
3. ✅ 频繁提交小改动
4. ✅ 文档同步更新
5. ✅ 对比新旧结果

### DON'T ❌

1. ❌ 一次修改多个模块
2. ❌ 跳过测试验证
3. ❌ 修改逻辑在第一轮
4. ❌ 忽略性能影响
5. ❌ 删除 legacy 代码（暂时）

---

## 🐛 问题排查

### 如果测试失败

1. 检查 golden cases 是否正确
2. 对比 legacy 和新版的中间结果
3. 使用调试器逐步执行
4. 检查元数据传递

### 如果性能下降

1. 使用 profiler 找到瓶颈
2. 检查是否有重复计算
3. 考虑缓存策略
4. 优化数据结构

### 如果导入失败

1. 检查 `__init__.py` 文件
2. 验证相对导入路径
3. 检查循环依赖
4. 清理 `__pycache__`

---

## 📞 获取帮助

### 资源

1. **代码审查报告** - 详细的问题分析和解决方案
2. **实施指南** - 具体的可执行步骤
3. **原始文档** - `docs/RuleSystem_v8.2.md`
4. **配置文件** - `metrics_thresholds.yml`

### 示例

- 查看已创建的 `base.py` 和 `context.py`
- 参考 `test_score_engine.py` 的测试模式
- 学习 `chess_evaluator/` 的模块结构

---

## 🎉 里程碑

### ✅ Milestone 1: 基础设施（已完成）

- 安全网建立
- 抽象接口定义
- 测试框架搭建

### 🚧 Milestone 2: 第一个 Detector（进行中）

- TensionDetector 创建
- 测试通过
- 文档完整

### ⏳ Milestone 3: 核心 Detectors

- 5+ detectors 迁移
- Pipeline 实现
- 全面测试

### ⏳ Milestone 4: 生产就绪

- 性能优化
- 完整测试覆盖
- 生产验证

---

## 📄 许可和贡献

本重构项目遵循原项目的许可条款。

贡献指南：
1. 阅读重构文档
2. 遵循 Python PEP 8
3. 添加测试覆盖
4. 更新相关文档
5. 提交 Pull Request

---

## 📅 更新日志

### 2025-11-04

**Phase P0 完成：**
- ✅ 创建基础架构骨架
- ✅ 定义 TagDetector 和 AnalysisContext
- ✅ 准备 golden test cases
- ✅ 验证所有导入正常

**下一步：**
- 🚧 开始 Phase P1 - 创建 TensionDetector

---

**准备好了吗？开始 Phase P1！** 🚀

参见：[REFACTORING_GUIDE.md](./REFACTORING_GUIDE.md) 获取详细步骤
