# Phoenix-Evo — 不死鸟自进化 Agent 系统

> 不是让 Agent 单次完成任务，而是让 Agent 在每次任务结束后自动沉淀经验、修复缺陷、生成技能，并通过免疫系统防止错误经验污染长期能力。

---

## 版本演进

| 版本 | 主题 | 状态 |
|------|------|------|
| V0.1 | 基础闭环：轨迹→自评→提取→验证→入库 | 完成 |
| V0.5 | PhoenixRuntime：Skill Router + Guard + Context Injector | 完成 |
| V0.6 | 三层对抗测试 + Chinese word segmentation fix | 完成 |
| V0.7 | Runtime Feedback Loop：OutcomeTracker + FeedbackDispatcher | 完成 |
| V0.8 | AgentRuntime：任务生命周期 + Hook 系统 + TaskStore | 完成 |

---

## 核心闭环（V0.1）

任务 -> 轨迹记录 -> 自评 -> 提取 -> 验证 -> 入库(draft) -> 下次复用
              |
          失败归因 -> 免疫防御 -> 拒绝危险经验

## V0.8 运行时架构

AgentRuntime.run(task)
  1. TaskContext 创建 (CREATED)
     on_task_created hook
  2. PhoenixRuntime.route() (ROUTING)
     on_before_route -> SkillRouter -> RuntimeGuard -> on_after_route
  3a. skill_found=False -> NO_SKILL -> FeedbackDispatcher.report_skipped()
  3b. skill_found=True
        4. 上下文注入 (INJECTING)
           on_before_inject -> on_after_inject
        5. execute_fn(ctx) (RUNNING)
           on_before_execute
           success -> SUCCESS -> on_success -> FeedbackDispatcher.report_success()
           failure -> FAILED  -> on_failure -> FeedbackDispatcher.report_failure()

---

## 目录结构

Phoenix-Evo/
core/
  phoenix_evo.py              # V0.1 主调度器
  trajectory_logger.py         # 轨迹记录器
  post_task_evaluator.py      # 任务后自评器
  skill_miner.py              # 技能提取器
  skill_verifier.py           # 技能验证器（免疫层）
  skill_registry.py            # 技能库管理器
runtime/
  phoenix_runtime.py           # V0.6 Skill Router 运行时
  skill_retriever.py          # V0.6 向量检索 + Chinese segmentation fix
  skill_router.py             # V0.6 路由决策（DENY/ALLOW/REVIEW）
  runtime_guard.py            # V0.6 Security Gate（8条规则）
  context_injector.py         # V0.6 Hermite插值上下文注入
  runtime_reporter.py         # V0.6 调用日志记录器
  fallback_manager.py         # V0.6 无匹配时降级策略
  outcome_tracker.py          # V0.7 任务结果追踪
  feedback_dispatcher.py      # V0.7 反馈分发（success/failure/skipped）
  agent_runtime.py            # V0.8 任务生命周期管理器
  demo_v0.6.py                # V0.6 Demo（6个场景）
  demo_v0.8_agent_runtime.py  # V0.8 Demo（6个场景）
skills/
  draft/                      # 候选技能（待激活）
  active/                     # 已激活技能
  archived/                   # 已归档技能
data/
  trajectories/               # 轨迹历史

---

## V0.8 核心新增

### AgentRuntime
任务生命周期管理器。串联 PhoenixRuntime -> Hook -> FeedbackDispatcher。

```python
from runtime.agent_runtime import AgentRuntime

runtime = AgentRuntime(phoenix_base_dir=Path("Phoenix-Evo"))
runtime.hooks.on_success(lambda ctx: print(f"Done: {ctx.task_id}"))

ctx = runtime.run(
    task_description="修复WSL中文路径",
    task_type="debugging",
    risk_level="low",
    execute_fn=lambda c: fix_path(c.injected_context),
)
# ctx.state == TaskState.SUCCESS
```

### HookManager
12个生命周期钩子点，支持 before/after 两种模式，before 返回 False 可拒绝操作。

### TaskStore
任务状态持久化。默认 JSON 文件，重启后 get_task() 可恢复。

### CancellationToken
可检测取消状态的 token，execute_fn 内可检查 token.is_cancelled。

---

## V0.7 Feedback Loop 数据流

RuntimeReporter（每条调用写一行 JSONL）
  OutcomeTracker（定时扫描日志文件）
    累计失败>=3 -> 触发 quarantine
  FeedbackDispatcher（同步分发）
    SkillRegistry.record_outcome()
      SkillCard metadata 更新（usage_count, success_rate...）
        Curator.scan() 审查 quarantine_skills
          quarantine_skill -> 降级/删除/恢复

---

## V0.6 Runtime Guard 规则

1. draft skill -> deny
2. quarantine skill -> deny
3. archived skill -> deny
4. evidence_score < 0.60 -> deny
5. risk_score > 0.50 -> deny
6. replay_regression = true -> deny
7. task_risk = critical + skill_risk != low -> deny
8. high/critical task + no replay -> review_required

---

## 快速开始

```bash
cd Phoenix-Evo
python runtime/demo_v0.6.py
python runtime/demo_v0.8_agent_runtime.py
```

---

## V0.1 安全约束

- 候选技能只进 skills/draft/，不自动激活
- 涉及删除/支付/绕过/攻击的技能被免疫系统拒绝
- 所有技能可追溯到原始轨迹
- 禁止自动修改 active skills
- 禁止自动删除技能

---

## 下一步（V0.9 规划）

- PhoenixRuntime 与 Hermes Agent 真实集成（接 Claude/GPT 执行）
- OutcomeTracker 后台 daemon 模式（自动扫描日志）
- Curator 免疫审查自动化（自动 quarantine/recover）
- Replay 历史轨迹回放验证
- Skill 质量评分动态调整（基于真实使用反馈）

---

自进化不是自动相信自己，而是自动怀疑自己、验证自己、沉淀自己。
