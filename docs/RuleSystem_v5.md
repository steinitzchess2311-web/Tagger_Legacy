# Codex 系统 Tag 逻辑扩展计划书 v5

## 1. 现状（Current State）

- 引擎侧已输出 `preventive_score` / `self_safety_bonus` 等基础指标，但尚未对外暴露 `prophylactic_*` 质量层级。
- 战术 gating 目前只基于 `delta_eval` 与 `material_delta`，缺乏结构与计划一致性信号。
- 调动类走法（maneuver）没有质量区分，只能通过 mobility 变化粗略判读。
- soft gate（模糊区间）尚未实现；`metrics_thresholds.yml` 仅提供固定阈值。
- telemetry 已记录诸多细节（tension、plan-drop、structural），但未统一输出语义标签或质量说明。

## 2. 目标（Objectives）

1. 引入 `prophylactic_strong / soft / failed` 等质量标签，并在 notes / telemetry 中输出对应分值。
2. 使用动态 τ（winning / losing context）调整有效掉分 `effective_delta`，让胜势/劣势判断合理化。
3. 完善战术/结构 gating：三维信号（eval、material、blockage / plan）综合判定标签收敛。
4. 识别调子质量与早期攻击（piece maneuver、premature attack、risk avoidance）。
5. 保留连续化指标（`maneuver_score`、`aggression_index`、`safety_bias`）在 `analysis_meta` 中，供 LLM 后续使用。

## 3. 新增 / 调整标签与指标

### 3.1 新增标签

| 标签 | 类型 | 定义 | 触发建议 |
| --- | --- | --- | --- |
| `premature_attack` | strategic | 未完成协调即启动攻击 | `effective_delta <= -0.4` 且 `structure_loss < structure_weaken_limit` 且 `mobility_self < mobility_self_limit` |
| `constructive_maneuver` | positional | 调动提升协调 / 中心控制 | `maneuver_quality >= constructive_threshold` |
| `neutral_maneuver` | positional | 调动合理，小亏可接受 | `neutral_threshold <= maneuver_quality < constructive_threshold` |
| `misplaced_maneuver` | positional | 调动方向错误 / 失调 | `maneuver_quality < misplaced_threshold` |
| `risk_avoidance` | psychological | 看似安全但丢动能 | `abs(effective_delta) < 0.6` 且 `king_safety_diff < safety_bias` 且 `mobility_drop > risk_avoidance_mobility_drop` |

### 3.2 标签语义更新
- **非 Knight 调子补偿**：在 `evaluate_maneuver_metrics` 中对 Bishop / Rook 调入半开放线或长对角线的情况增加轻量补偿（例如 `precision += open_file_score * 0.05`），防止直线子 mobility 波动导致误判；Knight 则保留时机修正（`soft_knight_misplaced`）。

- `control_over_dynamics`：强调“保持或重新引导局面节奏”，兼容 Rc1 等防守调动。
- `prophylactic_move`：输出 quality 分层，notes 中附带 `prophylactic_quality: strong (score …)`。
- `tension_creation`：补充 `contact_delta` 阈值过滤，防止假张力。
- `structural_compromise_dynamic`：在发生 `premature_attack` 时，明确结构牺牲与进攻意图。

### 3.3 指标与评分

- `maneuver_quality = 0.5 * mobility_gain + 0.3 * center_gain - 0.2 * max(0, -effective_delta)`。
- `aggression_index = tension_contact_delta - structure_loss`（复用 tension telemetry）。
- `safety_bias = king_safety_diff - mobility_diff`。
- `soft_gate_weight = 1 / (1 + exp(-(effective_delta - midpoint)/width))`（midpoint/width 来自配置）。

## 4. 配置（metrics_thresholds.yml）

```yaml
maneuver_constructive_threshold: 0.25
maneuver_neutral_threshold: 0.0
maneuver_misplaced_threshold: -0.25
aggression_threshold: 0.4
risk_avoidance_mobility_drop: 0.1
structure_weaken_limit: -0.2
mobility_self_limit: 0.25
winning_tau_max: 2.0
winning_tau_scale: 0.2
losing_tau_min: 0.6
losing_tau_scale: 0.2
soft_gate_midpoint: -0.25
soft_gate_width: 0.1
file_pressure_threshold: 0.35
volatility_drop_tolerance: 0.05
premature_attack_threshold: -0.25
premature_attack_hard: -0.4
```

所有检测逻辑必须读取配置，不再硬编码。

## 5. 实现路径

### 5.1 函数接口（rule_tagger.py）

```python
def detect_premature_attack(board, metrics, context) -> Tuple[bool, Dict]:
    ...

def evaluate_maneuver_quality(metrics_before, metrics_after, context) -> Dict:
    ...

def score_behavior_indices(metrics, telemetry) -> Dict:
    ...
```

插入位置：`tag_position()` 中，在 eval delta 及 metrics 计算完成之后。

### 5.2 动态 τ 处理

- `tau = compute_tau(eval_before)`，写入 `analysis_meta["context"]["tau"]`。
- `effective_delta = delta_eval / tau`；所有质量/soft 判断基于 `effective_delta`。
- 若 `tau > 1.05` → `context.label = "winning_position_handling"`；若 `< 0.95` → `losing_position_handling`。

### 5.3 战术 / 结构 Gating

```python
def apply_tactical_gating(tags, effective_delta, material_delta, blockage_penalty, plan_passed):
    if effective_delta <= -2.0 or material_delta <= -1.0:
        return ["missed_tactic"], "tactical_blunder"
    if blockage_penalty >= 1.0 and effective_delta <= -1.0:
        return ["missed_tactic", "structural_blockage"], "structural_failure"
    if plan_passed is False:
        return ["prophylactic_meaningless"], "plan_drop_failed"
    return None, None
```

输出 `tags_initial` → `tags_secondary`（替换质量标签 / context）→ `tags_primary`（gating 后）。

### 5.4 预防质量分层

- 使用 `classify_prophylaxis_quality` 返回 `(label, score)`，写入 `analysis_meta["prophylaxis"]["quality"]` 与 notes。
- `soft_gate_weight`（默认 logistic）用于 0~-0.4 区间的平滑。
- 若 plan-drop candidate 且未通过 → 直接标记 `prophylactic_meaningless`。

### 5.5 输出契约（codex_utils.analyze_position）

```json
"tags": {
  "all": {...},
  "active": [...],
  "secondary": ["control_over_dynamics", "prophylactic_strong", "winning_position_handling"],
  "primary": ["prophylactic_strong"],
  "gating_reason": null,
  "prophylaxis_quality": "prophylactic_strong"
},
"analysis_context": {...},
"engine_meta": {
  "gating": {...},
  "prophylaxis": {...},
  "behavior_scores": {
      "maneuver": 0.18,
      "aggression": 0.42,
      "safety": -0.05
  }
}
```

## 6. 测试集（Regression Table）

| 局面 | FEN | 期待标签 | 说明 |
| --- | --- | --- | --- |
| Kh1 | `rn3rk1/...` | `prophylactic_strong` | 典型防御转移 |
| Rb1 | 同上 | `neutral_maneuver` | 软调度 |
| Re1 | 同上 | `constructive_maneuver` | 中心再部署 |
| c4 | 同上 | `constructive_maneuver + tension_creation` | 中央扩张 |
| h4/g4 | 同上 | `premature_attack + structural_blockage` | 未协调攻击 |
| f5 | 同上 | `premature_attack` (可伴随 `structural_compromise_dynamic`) | 过早突破 |

建议通过 pytest / JSON 回归验证 primary/secondary/gating_reason。

## 7. LLM 预留结构

```json
{
  "move": "Na5",
  "metrics": {
    "maneuver_score": 0.12,
    "aggression_index": 0.22,
    "safety_bias": -0.04
  },
  "tags_initial": ["neutral_maneuver"],
  "llm_context": "The move redirects the knight toward b7 pressure while ceding central activity.",
  "tags_final": ["neutral_maneuver", "strategic_redeployment"]
}
```

## 8. 执行步骤

1. **Stage 1**：实现方案 A（规则层扩展），落地新标签与 gating 分层；更新阈值配置与文档。
2. **Stage 2**：扩展行为评分（方案 B），输出 `behavior_scores` 连续指标；供风格建模。
3. **Stage 3**：预留 LLM 后处理逻辑（方案 C），当有资源时接入 Codex-L 做语义校正。

## 9. 后续扩展

- 统计各标签出现频率，形成棋风画像（冲动型、防御型等）。
- 分析 `premature_attack` 与胜负关系，辅助心理与策略分析。
- 结合 LLM 生成自然语言讲解（教学报告、对局复盘）。

---

> *本计划书旨在指导 Codex rule_tagger 的下一阶段扩展与重构。执行前请同步更新 `metrics_thresholds.yml`，并确保测试集覆盖所有新增标签与 gating 分支。*
- 若 `premature_attack` 触发，将在 `analysis_meta["premature_attack"]` 输出 `{"score": …, "profile": "tactical_overreach|positional_sac"}`，并在 notes 统一记录 `profile=<...> (score …)`，方便 LLM/解释层解析。
