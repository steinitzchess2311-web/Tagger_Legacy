# ai_coordinating_protocol.md
> Version 1.2  |  Last updated: 2025-11-07  
> Purpose: Define how Planner (owners), Codex (PM/Reviewer), and Claude (Executor) coordinate in the style_tag project.

## Roles & Ownership

| Role            | Primary Duties                                                                                           | Key Outputs                                           |
|-----------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| **Planner (owners)** | 提出方向/目标与边界；设定阶段目标与优先级；在关键里程碑处做最终拍板。                                  | 方向说明、阶段目标、里程碑通过/否决记录               |
| **Codex (PM + Reviewer)** | **完整代码审阅** → 评估影响 → **细化可执行计划**；把计划**写入 `project_process.md`**；过程监督与复盘；代码评审与改进建议。 | `project_process.md` 中的 plan、表格与变更记录；评审备注 |
| **Claude (Executor)** | 是牛马开发组。按plan栏目中的计划实现；在代码内与文档中记录实现细节与决策；对疑点及时向 Codex 反馈。                       | 代码提交、实现摘要、`claude comment`                  |

> 决策权：  
> - 方向与范围：Planner  
> - 计划拆解与实现路径：Codex（必要时征求 Planner 确认）  
> - 具体实现细节：Claude（遵循计划；若偏离需 Codex 确认）

---

## Artifacts & Conventions

- **唯一工作台**：`project_process.md`  
  - 每一阶段由 **Codex** 写入：目标、范围、受影响文件、实施步骤、回退顺序、兼容性要求。  
  - 采用下表作为统一记录格式（保持与既有格式一致）：
  
  -----------------|-------------------|---------------------|-----------------|
  plan             | claude process    | claude comment      | codex comment   |
  -----------------|-------------------|---------------------|-----------------|
  （Codex 填写计划项） | （Claude 状态：✅/⏳/❓） | （Claude 的实现摘要） | （Codex 的审核与改进意见） |

- **状态符号**：`✅` 完成 / `⏳` 进行中 / `❓` 有疑点 / `🚫` 关闭或撤销  
- **代码内统一标记**（便于全局检索）：  
  - `# TODO[v2-rename]: ...`  
  - `# TODO[v2-prepare]: ...`  
  - `# TODO[v2-failed]: ...`  
  - `# TODO[v2-kbe]: ...`

---

## Workflow Loop

1. **Planner** 提出方向（例如：标签命名重构、新增标签、修复某体系未触发等）。  
2. **Codex（PM）完整审阅代码库**，评估影响面，**把方向细化为可执行计划**：  
   - 明确落地范围与不做的内容；  
   - 指定受影响文件与新增文件；  
   - 规定管线调用顺序与回退关系；  
   - 约定兼容性/别名映射与对外导出；  
   - 写入 `project_process.md`：计划表（如上表）+ 精炼步骤。  
3. **Claude** 严格按 Codex 计划实现：  
   - 提交代码并在 `claude comment` 写清“改了什么、在哪些文件、关键阈值/常量/顺序”；  
   - 对 `❓` 项主动反馈，必要时与 Codex 同步更新计划。  
4. **Codex** 审核实现：  
   - 在 `codex comment` 中给出通过/修改建议；  
   - 如涉及重大偏离，**Codex 有权要求回滚或追加步骤**；  
   - 更新 `project_process.md` 中相应行的最终状态。  
5. **Planner** 在里程碑节点检查：  
   - 若该阶段所有条目均为 `✅`，Planner 批准进入下一阶段；  
   - 如方向需调整，Planner 只变更目标，Codex 负责重写计划。

---

## Handoff 清单（最少交付物）

- **Codex → Claude**  
  - 受影响文件列表（含新增/改名/别名映射）；  
  - 管线步骤与调用顺序（含回退链）；  
  - 关键阈值/标志名称；  
  - 兼容性要求（例如对外常量、ORDERED_TAGS、别名表）。

- **Claude → Codex**  
  - 变更摘要（按文件列点）；  
  - 新/改标签与导出的清单；  
  - 关键注释与 `TODO[v2-*]` 定位点。

---

## Escalation（异议上报）

- Claude 对计划可在 `project_process.md` 对应行标 `❓` 并简述原因；  
- Codex 在 1 次循环内给出决断或替代路径；  
- 如涉及方向性变更，由 Planner 拍板，Codex 负责修订计划。

---

## Ground Rules

- **单一事实来源**：`project_process.md` 的计划表为唯一执行依据；  
- **先计划、后编码**：除紧急修复外，Claude 以 Codex 的计划为起点；  
- **保持向后兼容**：改名与导出必须提供别名/映射；  
- **记录即文档**：表格与代码注释合力形成最短可读文档。


## Row Priority
When executing project_process.md, process rows top-down with this order:
1) ❓ rows (fix Codex concerns first)
2) ⏳ rows (continue in-progress)
3) empty rows (start new)

Process at most 3 rows per round. Do not modify multiple times in the same round.

## Code Review Requirement
Codex must compare “CLAUDE_COMMENT” with actual code:
- Files exist and paths correct
- Functions/classes/configs added or changed as described
- Thresholds/switches injected from YAML/ENV (no hardcode)
- Gating/conflict/cooldown implemented per plan
- Telemetry/snapshots generated as claimed
If acceptable → mark ✅ with brief evidence; else → mark ❓ and list precise fixes (file:line, reason, suggestion).


## Models
EXECUTOR_MODEL: claude-3-5-sonnet-20241022
REVIEWER_MODEL: gpt-4-turbo-2024-04-09





That is all for the protocol, please start your work on project_process.md 

