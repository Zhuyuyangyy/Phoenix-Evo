# Phoenix-Evo V0.6 - V1.0 完整路线图（锁定版）

> 文档版本：V0.6-LOCKED  
> 锁定时间：2026-05-08  
> 当前基线：V0.5 Hermes Bridge  
> 状态：已冻结，禁止在 V0.6 执行期间修改本文档

---

## 一句话定位

```
Phoenix-Evo 不是 Agent 执行框架，而是 Agent 的自进化经验治理层。
它把任务执行轨迹转化为经过验证、免疫、回放、治理和安全复用的技能资产。
```

```
Hermes：负责执行任务
Phoenix-Evo：负责从任务中成长
AgentShield：负责行为和风险审计
```

---

## 当前状态（V0.5 完成后）

```
V0.1 造血：轨迹 → 自评 → 技能提取          ✅ 完成
V0.2 免疫：风险识别 → reject/quarantine/draft ✅ 完成
V0.3 代谢：相似合并 → 漂移检测 → 降级归档    ✅ 完成
V0.4 记忆：SkillCard → Replay → 晋级判断    ✅ 完成
V0.5 桥接：Hermes 轨迹 → Phoenix draft skill ✅ 完成
```

Phoenix 已经能接 Hermes 的执行轨迹，但还没有让 Hermes 在新任务中复用 Phoenix 的技能。

**当前状态：能学，但还不会正式用。**

---

## 终局目标（V1.0）

```
Hermes 执行任务
    ↓
Phoenix 捕获轨迹
    ↓
生成候选技能
    ↓
格式验证
    ↓
Immune Guard 风险审查
    ↓
SkillCard 证据绑定
    ↓
Replay 回放验证
    ↓
Curator 治理去重/漂移/归档
    ↓
人工或规则晋级 active
    ↓
Hermes 新任务检索 active skill
    ↓
安全注入上下文
    ↓
执行结果反哺 Phoenix
```

**一句话：Agent 每执行一次任务，都有机会沉淀为可验证、可治理、可复用的技能资产。**

---

## 总体里程碑

```
V0.5 Hermes Bridge        已完成（基线）
V0.6 Runtime Skill Router 下一步
V0.7 Runtime Feedback Loop
V0.8 Phoenix-Bench
V0.9 Governance & Multi-Agent Extension
V1.0 Framework Release
```

---

## 执行口径（直接交给开发）

```
Phoenix-Evo 当前 V0.5 已完成 Hermes Bridge，已经能从 Hermes 执行轨迹中
稳定生成 draft skills。

后续主线不是继续堆技能生成，而是进入"安全复用 + 运行时反馈 + 量化验证"阶段。

V0.6 先做 Runtime Skill Router，使 Hermes 在新任务开始时能从 Phoenix
active skills 中检索可用技能，并通过 RuntimeGuard、EvidenceScore、
RiskScore、ReplayResult 进行安全路由，只把合格 active skill 注入上下文。

V0.7 做 Runtime Feedback Loop，把 skill 实际使用结果写回 Phoenix，
更新使用次数、成功率、失败次数、风险事件，并在连续失败或风险上升时
触发 replay、curator 或 quarantine。

V0.8 做 Phoenix-Bench，构建 30-50 条任务评测集，完成 baseline /
skill extraction / immune guard / curator / evidence replay / runtime
router 的消融实验，证明 Phoenix-Evo 能提升任务成功率、技能复用率、
风险拦截率，并降低重复技能和回归风险。

V0.9 做 Governance 和 Multi-Agent Extension，加入 skill 版本、审批、
权限、审计和跨 Agent 技能共享机制。

V1.0 封装为完整框架：Hermes 执行，Phoenix 成长，AgentShield 审计，
形成可控、可审计、可回放、可复用、可治理的 Agent 自进化基础设施。
```

---

## V0.6：Runtime Skill Router

### 阶段目标

让 Hermes 在新任务开始时，从 Phoenix 中检索可用的 **active skill**，并作为上下文安全注入。

```
任务结束 → 生成 draft skill      （现状）
任务开始 → 检索 active skill → 安全注入 Hermes   （V0.6 目标）
```

### 阶段流程

```
Hermes task_start
    ↓
PhoenixRuntime.query(task_description)
    ↓
SkillRetriever 检索 active skills
    ↓
SkillRouter 排序
    ↓
RuntimeGuard 检查状态/风险/证据分
    ↓
ContextInjector 生成 Hermes 上下文
    ↓
Hermes 使用 skill 辅助执行
```

### 新增文件清单

```
runtime/
├── skill_retriever.py       # 根据任务描述检索相似 active skill
├── skill_router.py          # 综合相似度、证据分、风险分选择技能（已存在）
├── context_injector.py      # 把 skill 转成 Hermes 可读上下文
├── runtime_guard.py         # 调用前安全闸门
├── fallback_manager.py      # 技能不可用/失败时回退
└── runtime_reporter.py      # 记录技能使用情况（已存在）
```

### 核心路由规则

```
active + evidence_score >= 75 + risk_score <= 0.30 → ALLOW（自动注入）
active + evidence_score 60~75 + risk_score <= 0.30 → SUGGEST（仅建议）
draft skill → DENY（禁止 runtime 使用）
quarantine skill → DENY
archived skill → DENY
high-risk task → require review
```

### SkillRouter 评分公式

```
route_score =
    0.35 × similarity          （task_description 与 skill 相关度）
  + 0.30 × evidence_score      （EvidenceSummary 综合分）
  + 0.20 × replay_pass_rate    （Replay 回放通过率）
  + 0.15 × runtime_success_rate（历史使用成功率）
  - 0.30 × risk_score         （风险惩罚）

ALLOW >= 0.60 | SUGGEST 0.40-0.60 | DENY < 0.40
```

### V0.6 Task 拆解

#### Task 1：建立 active skill 索引（skill_retriever.py）

```
目标：扫描 skills/active/，建立可检索索引
输入：Hermes task_description
输出：候选 skill 列表（含 relevance_score）

需支持：
- keyword match
- tag match
- description similarity
- risk tag filtering
- evidence score sorting
```

#### Task 2：实现 RuntimeGuard（runtime_guard.py）

```
目标：决定 skill 是否允许进入 Hermes 上下文

规则（按优先级）：
1. status != active → DENY
2. evidence_score < 60 → DENY
3. risk_score > 0.50 → DENY
4. quarantine_history > 0 → REVIEW_REQUIRED
5. replay_regression = true → DENY
```

#### Task 3：SkillRouter 完善（已存在，补齐缺失字段）

```
skill_router.py 已有骨架，需确保支持：
- 从 index_entry 读取 evidence_score、replay_rate、runtime_success_rate
- 字段兼容 V0.1-V0.4 多种命名
- fallback 中性分 0.50 当字段缺失时
```

#### Task 4：实现 ContextInjector（context_injector.py）

```
目标：把 skill 转成 Hermes 可读上下文

输出格式：
---
## Relevant Skill: {skill_name}

**When to use:**
{trigger_condition}

**Procedure:**
{steps}

**Constraints:**
{constraints}

**Evidence score:** {evidence_score}/1.0
**Risk notes:** {risk_tags}
---

注意：只注入必要信息，不要把整个 SkillCard 都塞进上下文。
```

#### Task 5：实现 FallbackManager（fallback_manager.py）

```
目标：没有 skill 或 skill 被拒绝时，Hermes 正常执行

策略：
- no_skill_found → Hermes 正常执行
- skill_denied → Hermes 正常执行 + 记录原因
- skill_failed → fallback to baseline execution
```

#### Task 6：实现 PhoenixRuntime 统一调度（phoenix_runtime.py）

```
目标：对 Hermes 暴露单一入口，内部协调各模块完成安全 skill 注入

完整流程：
  1. SkillRetriever 检索 active skills
  2. SkillRouter 综合评分排序
  3. RuntimeGuard 逐条安全检查
  4. ContextInjector 生成 Hermes 上下文
  5. FallbackManager 提供降级方案
  6. RuntimeReporter 记录完整调用
```

### V0.6 安全边界（禁止突破）

```
1. draft skill 禁止 runtime 使用
2. quarantine skill 禁止 runtime 使用
3. archived skill 禁止 runtime 使用
4. active skill 也必须过 RuntimeGuard
5. skill 只能作为上下文建议，不直接执行危险操作
6. skill 使用失败不得自动重试高风险动作
7. skill 使用记录必须可追溯
```

### V0.6 验收标准

```
1. Hermes 新任务开始时能查询 Phoenix active skill
2. draft/quarantine/archived skill 不会被注入
3. 低风险 active skill 可以生成上下文包
4. 无匹配 skill 时正常 fallback
5. runtime 调用记录写入日志
6. 测试至少 15 条，全绿
```

### V0.6 Demo 场景

```
Demo1：相似任务命中 active skill
Demo2：draft skill 被拒绝注入
Demo3：quarantine skill 被拒绝注入
Demo4：无匹配 skill 触发 fallback
Demo5：高 evidence_score skill 排名靠前
```

### V0.6 完成后状态

> **能学，也能用。**

---

## V0.7：Runtime Feedback Loop

### 阶段目标

让 Hermes 使用 skill 后，把结果重新反馈给 Phoenix，形成完整的学习闭环。

```
V0.6：调用技能
V0.7：用完还能继续进化
```

### 阶段流程

```
Hermes 使用 skill
    ↓
任务成功/失败
    ↓
Phoenix 记录 runtime outcome
    ↓
更新 SkillCard（usage_count、success_rate、failure_count）
    ↓
更新 replay/evidence 统计
    ↓
必要时触发 Curator 漂移检测
```

### 新增文件清单

```
runtime/
├── outcome_tracker.py       # 记录 skill 实际调用结果
├── skill_usage_store.py     # 统计每个 skill 的使用次数/成功率
├── runtime_evaluator.py     # 判断本次 skill 是否有效
└── feedback_dispatcher.py  # 反哺 Evidence / Curator / Immune
```

### Skill 运行时字段扩展

```json
{
  "usage_count": 12,
  "runtime_success_rate": 0.83,
  "recent_failure_count": 1,
  "last_used_at": "2026-05-07",
  "runtime_risk_incidents": 0,
  "needs_replay": false,
  "needs_curator_review": false
}
```

### 反馈规则

```
连续失败 >= 2 → 标记 needs_replay
连续失败 >= 3 → 降级 review
运行时风险上升 → quarantine
长期高成功率 → 提升 evidence confidence
长期未使用 → Curator 检查是否归档
```

### V0.7 验收标准

```
1. skill 被调用后能记录 outcome
2. 成功调用能提升 usage_count
3. 失败调用能增加 failure_count
4. 连续失败会触发 replay
5. 风险上升会触发 quarantine
6. Curator 能读取 runtime 数据做漂移判断
```

### V0.7 完成后状态

> **能用，用完还能继续进化。**

---

## V0.8：Phoenix-Bench

### 阶段目标

构建评测集，证明 Phoenix-Evo 真的有效。

**这是论文、专利、路演最重要的一步。**

没有 Benchmark，只能说"我设计了一个框架"。  
有 Benchmark，就能说"我证明了这个框架能提升成功率、降低风险、减少重复技能"。

### 新增目录

```
bench/
├── cases/
│   ├── coding_debug_cases.json
│   ├── document_generation_cases.json
│   ├── tool_error_cases.json
│   ├── unsafe_action_cases.json
│   └── skill_reuse_cases.json
├── runners/
│   ├── run_baseline.py
│   ├── run_with_phoenix.py
│   └── run_ablation.py
├── metrics/
│   ├── success_rate.py
│   ├── risk_blocking.py
│   ├── reuse_rate.py
│   ├── redundancy_rate.py
│   └── regression_rate.py
└── reports/
    └── benchmark_report.md
```

### Benchmark case 数量

```
V0.8 先做：30 条任务 case
V1.0 前扩到：50-100 条任务 case
```

### 消融实验设计

```
Baseline Hermes
Hermes + Phoenix V0.1
Hermes + V0.1 + Immune Guard
Hermes + V0.1-V0.3 Curator
Hermes + V0.1-V0.4 Evidence Replay
Hermes + V0.1-V0.6 Runtime Router
```

### 核心指标

```
Task Success Rate        任务成功率
Skill Reuse Rate         技能复用率
Risk Blocking Accuracy   风险拦截准确率
Regression Rate          技能复用引入退化的比例
Redundancy Rate          重复技能比例
Drift Detection Rate     漂移发现率
Average Steps            平均执行步骤
Human Review Load        人工复核负担
Evidence Coverage        技能证据覆盖率
```

### V0.8 验收标准

```
1. 至少 30 条 benchmark case
2. 至少 5 组 ablation
3. 输出 CSV/JSON/Markdown 报告
4. 证明 Runtime Router 能提升复用率
5. 证明 Immune Guard 能拦截高风险技能
6. 证明 Curator 能降低重复技能比例
7. 证明 Evidence Replay 能降低回归风险
```

### V0.8 完成后状态

> **不只是能用，而且能证明有用。**

---

## V0.9：Governance & Multi-Agent Extension

### 阶段目标

让 Phoenix-Evo 从单 Agent 经验层，升级为多 Agent 可共享、可治理的经验系统。

### 方向一：治理层

```
governance/
├── approval_workflow.py     # 人工审批流程
├── version_manager.py       # skill 版本管理
├── policy_engine.py         # 不同风险等级策略
├── permission_manager.py   # 哪些 Agent 可以用哪些 skill
└── audit_logger.py          # 技能生命周期审计日志
```

治理层解决：
```
谁创建了 skill？
谁批准了 skill？
哪个 Agent 用过？
什么时候失败过？
为什么被 quarantine？
哪个版本被归档？
```

### 方向二：多 Agent 共享

```
multi_agent/
├── agent_profile.py         # Agent 能力画像
├── skill_transfer.py        # 技能迁移
├── skill_scope.py           # 技能适用范围
├── shared_registry.py       # 共享技能库
└── compatibility_checker.py# 判断技能能否跨 Agent 使用
```

多 Agent 共享规则（必须遵守）：
```
同类型 Agent → 可推荐 skill
不同类型 Agent → 只 suggest，不自动使用
高风险 skill → 禁止跨 Agent 迁移
跨 Agent 使用前必须 replay
```

### V0.9 验收标准

```
1. skill 有版本号
2. skill 有审批状态
3. skill 有 owner/source agent
4. 多 Agent 可共享 active skill
5. 跨 Agent 使用前必须经过 compatibility check
6. 所有生命周期操作有 audit log
```

### V0.9 完成后状态

> **从单体自进化层，升级为组织级 Agent 经验治理层。**

---

## V1.0：Framework Release

### 阶段目标

形成完整框架、文档、评测、Demo、论文/专利材料。

V1.0 不追求功能无限多，而是要**边界清楚、证据完整、可演示、可复现**。

### V1.0 应包含

```
1. 完整代码架构
2. Hermes Bridge
3. Runtime Skill Router
4. Runtime Feedback Loop
5. Phoenix-Bench
6. 技术说明文档
7. API 使用文档
8. Demo evidence
9. 专利交底书
10. 论文框架
```

### V1.0 系统能力清单

```
✅ 执行轨迹采集
✅ 技能候选生成
✅ 技能格式验证
✅ 风险免疫审查
✅ 证据卡绑定
✅ 历史任务回放
✅ Curator 技能治理
✅ Runtime skill 检索
✅ 安全上下文注入
✅ 使用结果反馈
✅ Benchmark 评测
✅ 生命周期审计
```

### V1.0 验收标准

```
1. 100+ 单元测试全绿
2. 30-50 条 benchmark case
3. 至少 3 个完整端到端 demo
4. 每个 skill 有 SkillCard
5. 每次 runtime 调用有日志
6. 高风险 skill 不会进入 active
7. 失败 skill 能触发 replay/curator
8. README 有完整架构图和版本矩阵
9. docs 有 V1.0 总技术说明
10. patent/paper draft 可直接启动
```

### V1.0 完成后状态

> **一个可控、可审计、可回放、可复用、可治理的 Agent 自进化基础设施。**

---

## 最终架构图

```
┌──────────────────────────────┐
│          Hermes Agent          │
│      执行任务 / 调用工具        │
└───────────────┬──────────────┘
                │ task/tool events
                ↓
┌──────────────────────────────┐
│       Phoenix Hermes Bridge    │
│   事件适配 / 异步队列 / 导出    │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│       Trajectory System        │
│   轨迹记录 / 失败归因 / 自评    │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│        Skill Genesis           │
│   技能提取 / 格式验证 / 入库    │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│        Immune Guard            │
│   风险拦截 / 隔离 / 免疫记忆    │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│      Evidence & Replay         │
│   证据卡 / 回放验证 / 晋级判断  │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│          Curator               │
│   去重 / 漂移检测 / 归档 / 降级 │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│      Runtime Skill Router      │
│   检索 / 路由 / 注入 / fallback │
└───────────────┬──────────────┘
                ↓
┌──────────────────────────────┐
│      Runtime Feedback Loop     │
│   使用结果反哺 / 重新回放 / 治理 │
└──────────────────────────────┘
```

---

## 版本矩阵

| 版本 | 名称 | 状态 | 核心交付 |
|------|------|------|----------|
| V0.1 | 造血 | ✅ 完成 | 轨迹 → 自评 → 技能提取 |
| V0.2 | 免疫 | ✅ 完成 | reject/quarantine/draft 三层路由 |
| V0.3 | 代谢 | ✅ 完成 | 相似合并/漂移检测/归档降级 |
| V0.4 | 记忆 | ✅ 完成 | SkillCard/Evidence Replay/晋级 |
| V0.5 | 桥接 | ✅ 完成 | Hermes Bridge / 异步队列 / 导出器 |
| V0.6 | 路由 | 🔨 下一版本 | Runtime Skill Router / Guard / Fallback |
| V0.7 | 反馈 | 📋 规划 | Runtime Feedback Loop / outcome_tracker |
| V0.8 | 评测 | 📋 规划 | Phoenix-Bench / 30+ case / ablation |
| V0.9 | 治理 | 📋 规划 | Governance / Multi-Agent |
| V1.0 | 发布 | 📋 规划 | 框架发布 / 文档 / 专利 / 论文 |

---

## 执行顺序

```
第一步：V0.6 Runtime Skill Router
        让 Hermes 能安全检索 active skill

第二步：V0.7 Runtime Feedback Loop
        让 skill 使用结果反哺 Phoenix

第三步：V0.8 Phoenix-Bench
        量化证明 Phoenix 有效

第四步：V0.9 Governance
        补权限、版本、审批、多 Agent 共享

第五步：V1.0 Release
        封装框架、文档、论文、专利
```

最短路线：
```
V0.6 会用
V0.7 会反馈
V0.8 能证明
V1.0 可发布
```

---

## V0.6 开发启动语（可直接交给开发）

```
启动 Phoenix-Evo V0.6 Runtime Skill Router，基于 phoenix-evo-v0.5。

目标：
在 Hermes 新任务开始时，从 Phoenix active skills 中检索可用技能，
并基于 skill 状态、EvidenceSummary 分数、risk_score、replay 结果
进行安全路由。

约束：
V0.6 只允许 active skill 被注入 Hermes 上下文。
draft / quarantine / archived skill 必须被拒绝。

新增文件：
- runtime/skill_retriever.py
- runtime/context_injector.py
- runtime/runtime_guard.py
- runtime/fallback_manager.py
- runtime/outcome_tracker.py（V0.7 预留）

完善文件：
- runtime/skill_router.py（补字段兼容）
- runtime/phoenix_runtime.py（统一调度）

验收标准：
1. Hermes 新任务开始时能查询 Phoenix active skill
2. draft/quarantine/archived skill 不会被注入
3. 低风险 active skill 可以生成上下文包
4. 无匹配 skill 时正常 fallback
5. runtime 调用记录写入日志
6. 测试至少 15 条，全绿

Demo：
1. 相似任务命中 active skill
2. draft skill 被拒绝注入
3. quarantine skill 被拒绝注入
4. 无匹配 skill 触发 fallback
5. 高 evidence_score skill 排名靠前

安全边界（禁止突破）：
- draft skill 禁止 runtime 使用
- quarantine skill 禁止 runtime 使用
- archived skill 禁止 runtime 使用
- active skill 也必须过 RuntimeGuard
- skill 只能作为上下文建议，不直接执行危险操作
- skill 使用失败不得自动重试高风险动作
- skill 使用记录必须可追溯
```

---

## 文档版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| V0.6-LOCKED | 2026-05-08 | 锁定 V0.5→V1.0 完整路线图，冻结文档 |
