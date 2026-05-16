# Phoenix-Evo — 不死鸟自进化 Agent 系统

<p align="center">
  <strong>不是让 Agent 单次完成任务，而是让 Agent 在每次任务结束后自动沉淀经验、修复缺陷、生成技能，并通过免疫系统防止错误经验污染长期能力。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Supported-2496ED" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

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

## 版本演进

| 版本 | 主题 | 状态 |
|------|------|------|
| V0.1 | 造血：轨迹 → 自评 → 技能提取 | ✅ 完成 |
| V0.2 | 免疫：风险识别 → reject/quarantine/draft | ✅ 完成 |
| V0.3 | 代谢：相似合并 → 漂移检测 → 降级归档 | ✅ 完成 |
| V0.4 | 记忆：SkillCard → Replay → 晋级判断 | ✅ 完成 |
| V0.5 | 桥接：Hermes 轨迹 → Phoenix draft skill | ✅ 完成 |
| V0.6 | PhoenixRuntime：Skill Router + Guard + Context Injector | ✅ 完成 |
| V0.7 | Runtime Feedback Loop：OutcomeTracker + FeedbackDispatcher | ✅ 完成 |
| V0.8 | AgentRuntime：任务生命周期 + Hook 系统 + TaskStore | ✅ 完成 |
| V0.9 | Daemon + Metrics + CLI + 稳定性补丁 | ✅ 完成 |
| V1.0 | 生产就绪：项目路由 + 任务分类 + 命名空间治理 | ✅ 完成 |

---

## 核心架构

### 自进化闭环

```
任务 → 轨迹记录 → 自评 → 提取 → 验证 → 入库(draft) → 下次复用
              │
          失败归因 → 免疫防御 → 拒绝危险经验
```

### V1.0 运行时架构

```
AgentRuntime.run(task)
  1. TaskContext 创建 (CREATED)
     on_task_created hook
  2. PhoenixRuntime.route() (ROUTING)
     on_before_route → SkillRouter → RuntimeGuard → on_after_route
  3a. skill_found=False → NO_SKILL → FeedbackDispatcher.report_skipped()
  3b. skill_found=True
        4. 上下文注入 (INJECTING)
           on_before_inject → on_after_inject
        5. execute_fn(ctx) (RUNNING)
           on_before_execute
           success → SUCCESS → on_success → FeedbackDispatcher.report_success()
           failure → FAILED  → on_failure → FeedbackDispatcher.report_failure()
```

### Feedback Loop 数据流

```
RuntimeReporter（每条调用写一行 JSONL）
  → OutcomeTracker（定时扫描日志文件）
      累计失败≥3 → 触发 quarantine
  → FeedbackDispatcher（同步分发）
      SkillRegistry.record_outcome()
        SkillCard metadata 更新（usage_count, success_rate...）
          Curator.scan() 审查 quarantine_skills
            quarantine_skill → 降级/删除/恢复
```

---

## 目录结构

```
Phoenix-Evo/
├── core/                          # 核心模块
│   ├── phoenix_evo.py             # V0.1 主调度器
│   ├── trajectory_logger.py       # 轨迹记录器
│   ├── post_task_evaluator.py     # 任务后自评器
│   ├── skill_miner.py             # 技能提取器
│   ├── skill_verifier.py          # 技能验证器（免疫层）
│   ├── skill_registry.py          # 技能库管理器
│   ├── skill_curator.py           # 技能治理器（去重/漂移/归档）
│   ├── skill_evidence.py          # 证据绑定
│   ├── skill_replay.py            # 回放验证
│   ├── skill_similarity.py        # 相似度计算
│   ├── skill_benchmark.py         # 技能基准测试
│   ├── immune_guard.py            # 免疫守卫
│   ├── immune_memory.py           # 免疫记忆
│   ├── quarantine_manager.py      # 隔离管理
│   ├── replay_manager.py          # 回放管理
│   ├── replay_reporter.py         # 回放报告
│   ├── drift_detector.py          # 漂移检测
│   ├── risk_policy.py             # 风险策略
│   ├── execution_guard.py         # 执行守卫
│   ├── curator_policy.py          # 治理策略
│   └── runtime_reporter.py        # 调用日志记录器
├── runtime/                       # 运行时模块
│   ├── phoenix_runtime.py         # Skill Router 运行时
│   ├── phoenix_daemon.py          # 后台守护进程
│   ├── phoenix_metrics.py         # 指标采集
│   ├── agent_runtime.py           # 任务生命周期管理器
│   ├── skill_retriever.py         # 向量检索 + 中文分词
│   ├── skill_router.py            # 路由决策（DENY/ALLOW/REVIEW）
│   ├── runtime_guard.py           # Security Gate（8条规则）
│   ├── context_injector.py        # Hermite 插值上下文注入
│   ├── fallback_manager.py        # 无匹配时降级策略
│   ├── outcome_tracker.py         # 任务结果追踪
│   ├── feedback_dispatcher.py     # 反馈分发
│   ├── project_router.py          # 项目级路由
│   ├── task_type_classifier.py    # 任务类型分类器
│   ├── skill_injection_policy.py  # 技能注入策略
│   ├── runtime_skill_bridge.py    # 运行时技能桥接
│   ├── seed_skills.py             # 种子技能
│   ├── demo_v0.6.py              # V0.6 Demo
│   ├── demo_v0.7_feedback.py     # V0.7 Demo
│   └── demo_v0.8_agent_runtime.py # V0.8 Demo
├── integrations/                  # 集成模块
│   ├── hermes_adapter.py          # Hermes 事件适配层
│   ├── hermes_skill_exporter.py   # Hermes 技能导出
│   ├── phoenix_bridge.py          # Phoenix 桥接
│   ├── async_bridge.py            # 异步桥接
│   └── integration_policy.py      # 集成策略
├── cli/                           # 命令行工具
│   └── phoenix_cli.py             # CLI 入口
├── skills/                        # 技能存储
│   ├── draft/                     # 候选技能（待激活）
│   ├── active/                    # 已激活技能
│   ├── archived/                  # 已归档技能
│   └── rejections/                # 被拒绝的技能
├── data/
│   └── trajectories/              # 轨迹历史
├── logs/                          # 运行日志
├── tests/                         # 测试用例
│   ├── test_self_evolution_loop.py
│   ├── test_immune_guard.py
│   ├── test_runtime_router.py
│   ├── test_curator.py
│   └── test_evidence_replay.py
├── docs/                          # 技术文档
├── Dockerfile                     # 多阶段构建
├── docker-compose.yml             # Docker Compose 编排
├── requirements.txt               # Python 依赖
└── start.sh                       # 启动脚本
```

---

## 快速开始

### 环境要求

- Python 3.12+
- pip

### 本地安装

```bash
git clone https://github.com/your-org/Phoenix-Evo.git
cd Phoenix-Evo
pip install -r requirements.txt
```

### 运行 Demo

```bash
python runtime/demo_v0.6.py
python runtime/demo_v0.7_feedback.py
python runtime/demo_v0.8_agent_runtime.py
```

### Docker 部署

```bash
docker-compose up -d
```

服务端口：
| 端口 | 服务 |
|------|------|
| 8000 | PhoenixRuntime HTTP API |
| 9090 | Prometheus Metrics |

### CLI 使用

```bash
python -m cli.phoenix_cli status --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli skills list --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli skills activate <skill_id> --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli quarantine review --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli curator run --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli daemon start --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli metrics --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli replay <task_id> --base-dir ./Phoenix-Evo
```

---

## 代码示例

### AgentRuntime

```python
from runtime.agent_runtime import AgentRuntime
from pathlib import Path

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

### Hermes 集成

```python
from integrations.hermes_adapter import HermesAdapter

adapter = HermesAdapter(phoenix_base_dir=Path("Phoenix-Evo"))
adapter.on_step_callback(api_call_count=1, prev_tools=[])
adapter.on_tool_complete(tool_name="edit", tool_args={}, tool_result="ok")
```

---

## Runtime Guard 规则

| # | 规则 | 决策 |
|---|------|------|
| 1 | draft skill | DENY |
| 2 | quarantine skill | DENY |
| 3 | archived skill | DENY |
| 4 | evidence_score < 0.60 | DENY |
| 5 | risk_score > 0.50 | DENY |
| 6 | replay_regression = true | DENY |
| 7 | task_risk = critical + skill_risk ≠ low | DENY |
| 8 | high/critical task + no replay | REVIEW_REQUIRED |

---

## 安全约束

- 候选技能只进 `skills/draft/`，不自动激活
- 涉及删除/支付/绕过/攻击的技能被免疫系统拒绝
- 所有技能可追溯到原始轨迹
- 禁止自动修改 active skills
- 禁止自动删除技能

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12 |
| Web 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic v2 |
| 数据库 | SQLAlchemy + aiosqlite |
| 数值计算 | NumPy + SciPy |
| HTTP 客户端 | httpx |
| 监控 | Prometheus |
| 容器化 | Docker + Docker Compose |
| 测试 | pytest + pytest-asyncio |

---

## 项目文档

| 文档 | 说明 |
|------|------|
| [V0.1 技术说明](docs/Phoenix_Evo_V0.1_技术说明.md) | 基础闭环设计 |
| [V0.2 Immune Guard](docs/Phoenix_Evo_V0.2_Immune_Guard_技术说明.md) | 免疫系统设计 |
| [V0.5 Hermes Bridge](docs/Phoenix_Evo_V0.5_Hermes_Bridge_技术说明.md) | Hermes 集成设计 |
| [V0.6-V1.0 Roadmap](docs/Phoenix_Evo_V0.6-V1.0_Roadmap_锁定版.md) | 完整路线图 |

---

自进化不是自动相信自己，而是自动怀疑自己、验证自己、沉淀自己。
