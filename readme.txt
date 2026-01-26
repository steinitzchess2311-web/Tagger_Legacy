This project is for style tag. Calculating a few tags on position, and use these position tags to judge the style tag.

For codex coding agent, you have to know that you don't have to change anything based on this unless I told you to. Because there is chances that I miss understand your code. You have to judge if this is my misunderstanding or the thing that I want you to change by 1. evaluating if my plan is better than yours 2. check if I have told you to change
Extended tag logic (maneuver quality, directional pressure, risk avoidance, premature attack, etc.) is documented in `docs/RuleSystem_v5.md`.
Maneuver failure tags now emit severity suffixes (`.temporary`, `.strategic`, `.true`). Only the `.true` subset contributes to scoring penalties; summaries still report all parent counts for continuity.
The main judging logic: 
Soft gating - 
tactical weight > 0.65, tactical only. Only tactical tags will be triggered. 
tactical weight < 0.35, positional only. Only positional tags will be triggered. 
Else: bent, both might be triggered. 

tactical weight calculation: 
- delta eva 
- engine 1 & 2 choice score gap
- depth jump (hidden tactics)
- contact ratio 
- phase ratio 
- delta structure 
- delta tactics 
etc. 

Positional tags: 
1. control_over_dynamics (c_o_d):
def: I can choose to play dynamically, yet choose to play quiet move. 
- Has_dynamic_in_band = true (engine alter has dynamic)
- played move is quiet 
- delta eva < 0.3

2. defer_initiative:
def: I am not anxious, just play slowly waiting for chances (no need to have dynamic move in engine alters)
- move is quiet 
- delta eva < 0.5

Intent 层（intent hint / flags）
- `analysis_context["intent_hint"]` 会给出轻量级意图标签：`expansion`、`restriction`、`passive`、`neutral` 等，基于 mobility/center/king-safety 的综合信号。
- `analysis_meta["intent_flags"]` 将这些意图以软布尔形式标记，便于统计风格画像。
- 对应的候选标记（如 `restriction_candidate` / `passive_candidate`）也会输出，供 plan-drop 或 gating 阶段判断是否需要进一步验证。

3. risk_avoidance
def: 愿意牺牲机动性来巩固安全感。
- 自身 mobility ≤ −0.05
- opponent tactics ≤ +0.01（最好≤ −0.05）
- king safety ≥ −0.01（最好 ≥ +0.05）
满足“战术下降”或“王安全提升”两者之一即触发。

4. structural integrity 
def: improved pawn structure 
- delta structure >= +0.25
- delta tactics <= 0.10

5. structural_compromise_dynamic
def: 主动破坏结构换取动能或先手。
- 检测到结构破坏事件（孤兵/双兵/兵岛↑、兵链↓、王盾↓ 等）
- 最佳招法未强迫出现同样破坏
- mobility / tactics / center 至少一项 ≥ +0.20

6. structural_compromise_static
def: 结构受损且未获得补偿。
- 同样检测到结构破坏事件，且非强迫
- mobility、tactics、center_gain 均 < +0.20
- notes 会说明“结构削弱但缺乏动态补偿”

（dynamic/static 两标签与 structural_integrity 互斥，可帮助辨别是“主动拆结构换手段”还是“无意义送弱点”。）

5. prophylactic 
def: prophylactic
- self_structure gain >= 0.25
- self mobility change <= 0.20 (not opening up position or changing the corn of position)
- opp_mobility_change <= -0.3
- prophylactic score >= 0.25
- 若 intent_hint 判定为 restriction 且 plan-drop 诊断显示对方主计划的 PSI ≥ 阈值且 plan_loss ≥ 0.15，同时满足 Δeval ≥ plan_drop_eval_cap，则也会标记 prophylactic_move，并在 notes/telemetry 中附加 `plan disruption: psi …, loss …`
- 上述 plan-drop 检测受采样率、方差、runtime 限制；若检测被跳过或不稳定，仅记录诊断，不会改动标签。
- prophylaxis_score 拆分为 `preventive_score`（真正抑制对手活动，用于触发标签）与 `self_safety_bonus`（自我结构/安全收益，仅作诊断展示）。只有 `preventive_score ≥ prophylaxis_preventive_trigger` 时才亮起 prophylactic_move。
- 预防标签分层：在 gating 阶段，会将 `prophylactic_move` 映射为 `prophylactic_strong` / `prophylactic_soft` / `prophylactic_meaningless`（依据 effective Δ、preventive_score、tactical_weight 与软区间权重）。战术或结构灾难（effective Δ ≤ -2.0 / material_delta ≤ -1.0 / blockage ≥ 1.0）时仅保留 `missed_tactic`。
- 胜势/劣势情境：当 eval_before ≥ 3.0 或 ≤ -2.0 时，通过动态 τ 调整 effective Δ（胜势放宽、劣势收紧），并在 metadata 中记录 `context.label`（winning / losing position handling）。
- if this is true, c_o_d will be automatically changed to true. 

6. tactical sensitivity 
def: improved tactical potential in position after this move
- delta tactic >= 0.3

7. initiative exploitation
def: subjectively improve the position 
- delta eva > 0.5
- delta mobility > 0 

8. tension_creation
def: 主动制造张力，主动将稳定局面导向复杂搏杀。
- 评估轻度下滑：-0.9 ≤ Δeval_played_vs_before ≤ +0.1（避免把灾难性失误算作张力）
- Mobility 对冲：双方 mobility 方向相反且幅度接近（|Δself|、|Δopp| ≥ ~0.35，差值 ≤ 0.25）；若落在 0.30–0.35 区间，则需结构事件或 contact ratio 跃升支持
- phase ratio > 0.5（中局张力更具代表性），并通过 follow-up mobility 趋势过滤掉后续仍持续崩溃的走法
- Contact 补偿：若 contact ratio 上升 ≥ 0.04 且 Δeval ≤ -0.20，也视为 tension（典型兵突打开放火线）
- 延迟判定：若即时门槛未过，但双方 mobility ≥ 0.25 且趋势反向（self_trend ≤ -0.30，opp_trend ≥ +0.30），同时 contact 跃升 ≥ 0.03，则视为延迟 tension
- notes 中会说明触发路径（例如 symmetry_core / delayed_trend + contact_jump）便于追踪
- 若兵突造成 contact 增幅却未触发 tension / initiative，notes 会附加 `break_eval_flag` 作为诊断提醒
- Sustained filter：延迟/瞬时张力需通过未来两步 mobility 窗口校验（均值 ≥ 0.15、方差 ≤ 0.2），防止“假Δmobility” 误触

tactical tags: 
1. first_choice
def: I found the only winning move — the sole line that maintains a clear advantage.
- engine 1st–2nd choice score gap ≥ 0.8 pawn (80 cp)
- played move == best move
- best move is dynamic
(optional) eval_best ≥ +0.5 to avoid trivial equal positions

2. missed_tactic
def: A clear tactical solution existed, but I missed it.
- engine 1st–2nd choice score gap ≥ 0.8 pawn (80 cp)
- Δeval_cp = (best − played) ≥ 1.5 pawn (150 cp)
- best move is dynamic
tactical_weight ≥ 0.65

3. conversion_precision
def: I’m already winning, and I keep the advantage cleanly.
meaning:
Player in a winning position converts without losing accuracy — no “sloppiness in conversion”.
quantitative conditions:
eval_before ≥ +3.0 pawn (300 cp)
eval_played ≥ +3.0 pawn (300 cp)
|Δeval_played_vs_before| ≤ 0.3 pawn (30 cp)
delta_tactics ≥ 0 (should not lose tactical potential)

4️. panic_move

def: I panicked — evaluation dropped sharply with lower activity.
meaning:
Player made a sudden mistake reducing both score and coordination.
- Δeval_played_vs_before ≤ −2.5 pawn (−250 cp)
- Δmobility (played − before) ≤ −0.8
optional: delta_king_safety ≤ 0 (no compensating safety)
✅ Indicates psychological collapse or blunder under pressure.

5. tactical_recovery
def: I found a tactical resource to recover from a losing position.
meaning:
Player’s move suddenly improves evaluation from a near-lost state.
quantitative conditions:
eval_before ≤ −3.0 pawn (−300 cp)
eval_played ≥ −1.0 pawn (−100 cp)
delta_tactics ≥ +0.2
optional: mobility gain ≥ +0.2 (activity surge)
✅ Signals creativity or defensive sharpness.

6. tactical_dominance (optional — new high-impact tag)
def: The move causes a sharp tactical breakthrough that dominates the game.
(Used when engine detects a large tactical spike itself.)
quantitative conditions:
delta_tactics_best_vs_before ≥ +0.3
depth_jump_cp ≥ +80 cp
delta_structure ≤ +0.4 (not structure-driven)
contact_ratio ≥ 0.25
best_is_forcing = True
✅ Used internally as gating indicator for “tactical mode” or can appear as a top-level tag.

Configuration notes:
- 可通过 `metrics_thresholds.yml` 覆盖关键阈值（tension mobility/contact、blockage hysteresis、soft block scale 等）；若文件缺失或字段未填，则使用内建默认值。
- `analysis_context["telemetry"]` 聚合 tension / structural / prophylaxis / plan-drop / intent 等诊断数据（含阈值、触发源、稳定性），便于统一调试。
- `analysis_context["structural_details"]["reasons"]`、`analysis_context["tension_support"]` 等字段提供结构化原因码；外部脚本可直接使用 JSON 而非解析 notes。
- `analysis_context["intent_hint"]` 给出轻量级意图提示（例如 consolidation / expansion），供后续模型或 UI 使用。
- 若开启 `prophylaxis_plan_drop_enabled`，并配置 `plan_drop_*` 阈值（psi_min / plan_loss_min / sample_rate / variance_cap / runtime_cap_ms），在 `analysis_context["prophylaxis_plan"]` 中可查看 PSI、稳定性、耗时及是否通过验证；默认只在 intent_hint==restriction 的候选步上运行。
- `analysis_meta["intent_flags"]` 提供 expansion / restriction / passive / neutral 的软布尔位，便于统计风格画像。
- `metrics_thresholds.yml` 中的 `prophylaxis_preventive_trigger`、`prophylaxis_safety_bonus_cap` 控制防御触发阈值与自利加分上限；`prophylaxis_score` 仅取防御部分。
- `analysis_meta["tags_initial"]` / `tags_secondary` / `gating.tags_primary` 展示标签经过质量分层与 gating 后的演变；`gating.reason` 标识是否因战术灾难被强制只保留 `missed_tactic`。
- `metrics_thresholds.yml` 额外提供 `winning_tau_*`、`losing_tau_*` 控制胜势/劣势的 τ 伸缩，`soft_gate_midpoint` / `soft_gate_width` 控制软区间平滑。
- 若开启 `prophylaxis_plan_drop_enabled`，分析结果会在 `analysis_context["prophylaxis_plan"]` 中输出 PSI / 计划降阶等诊断信息，默认仅用于观察，不直接影响标签。

7. tactical_theme (future expansion)
def: Detects specific motif types (pin, fork, skewer, deflection, discovered attack, etc.)
quantitative: identified via evaluator’s _evaluate_tactical_themes()
status: optional extension once motif classifier is added.
