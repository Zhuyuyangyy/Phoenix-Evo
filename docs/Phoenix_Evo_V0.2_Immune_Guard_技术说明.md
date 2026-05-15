# Phoenix-Evo V0.2 Immune Guard 技术说明

## 概述

V0.2 在 V0.1 的基础上新增 **Immune Guard（免疫防御层）**，位于 skill_verifier 和 skill_registry 之间，对候选技能进行系统级风险审查，防止危险技能、证据不足技能、反复失败技能进入技能库。

## 架构

```
trajectory
    ↓
post_task_evaluator     — 判断是否值得提取
    ↓
skill_miner             — 从轨迹提取技能候选
    ↓
skill_verifier          — 检查技能格式质量（结构、危险内容、泛化度、重复）
    ↓
immune_guard            ← V0.2 新增：系统级风险治理
    ↓
draft / quarantine / reject
```

## V0.2 新增模块

### 1. ImmuneGuard（免疫审查主引擎）

位置：`core/immune_guard.py`

职责：对通过 skill_verifier 的技能候选进行二次审查，基于系统级风险策略做出放行/隔离/拒绝决策。

核心方法：
- `examine(skill_candidate, trajectory, verification_result) → ImmuneDecision`

返回决策类型：
- `draft` — 安全技能，进入 draft 队列等待人工激活
- `quarantine` — 可疑技能，进入隔离区待复核
- `reject` — 危险技能，直接拒绝并记录

### 2. ImmuneMemory（免疫记忆）

位置：`core/immune_memory.py`

职责：跨会话追踪技能失败历史，识别反复失败的技能模式，防止同类危险技能重复入库。

核心方法：
- `record_failure(skill_name, reason, tags) → count` — 记录一次失败
- `is_quarantined(skill_name, tags)` — 判断是否因反复失败被隔离
- `is_skill_blocklisted(skill_md)` — 检查 blocklist（immune_memory.json）
- `auto_immune()` — 自动将 blocklist 中的危险技能标记为隔离

持久化：`immune_memory.json`（skills/ 目录下）

### 3. QuarantineManager（隔离区管理）

位置：`core/quarantine_manager.py`

职责：管理 quarantine 队列，包括技能隔离、释放到 draft、拒绝等操作。

核心方法：
- `quarantine(skill_md_path, reason, risk_profile)` — 将技能移入隔离区
- `release_to_draft(skill_id)` — 复核通过，释放到 draft
- `release_to_active(skill_id)` — 复核通过，直接激活（V0.2 仍禁止）
- `reject(skill_id, reason)` — 复核拒绝，移入 rejections

持久化：`quarantine/index.json`（技能隔离索引）

### 4. RiskPolicy（风险策略定义）

位置：`core/risk_policy.py`

职责：定义免疫规则的元数据——危险行为关键词、高风险标签、quarantine 阈值等。所有规则为静态配置。

**危险行为分类（DANGEROUS_PATTERNS）：**
- privilege_escalation（权限提升/绕过）
- data_theft（数据窃取）
- destruction（破坏性操作）
- network_attack（网络攻击）
- privacy_violation（隐私侵犯）
- payment_fraud（支付欺诈）
- persistence（持久化后门）
- ai_harm（AI 危害行为）

**风险标签分级：**
- HIGH_RISK_TAGS → reject
- MEDIUM_RISK_TAGS → quarantine

## 决策规则优先级

V0.2 按以下顺序判断（优先级从高到低）：

| 优先级 | 条件 | 决策 |
|--------|------|------|
| 1 | high_risk_tag 命中 | reject |
| 2 | dangerous_pattern 命中 | reject |
| 3 | overgeneralized（< 2 步） | quarantine |
| 4 | source_failed + 无 artifacts | quarantine |
| 5 | source_failed + 无验证步骤 | quarantine |
| 6 | evidence_complete = False（轨迹ID + 步骤数 < 3） | quarantine |
| 7 | similar_skill_failures ≥ 3（历史反复失败） | quarantine |
| 8 | medium_risk_tag 命中 | quarantine |
| 9 | 无 artifacts | 加警告，仍 draft |
| 10 | 其他 | draft |

## evidence_complete 定义

```
evidence_complete = has_trajectory_id AND procedure_step_count >= 3
```

注意：V0.2 不要求 artifacts 作为 evidence_complete 的必要条件（避免与 skill_verifier 的 has_artifacts 检查冲突），但 artifacts 缺失会触发独立的 MISSING_ARTIFACTS 警告。

## V0.2 约束

- **禁止自动激活**：所有技能进入 draft 或 quarantine，必须经人工复核才能激活为 active
- **禁止自动删除**：被 quarantine 的技能不会被自动删除，保留完整记录供人工复核
- **blocklist 机制**：ImmuneMemory 中的 blocklist 会在新技能评估时被查询，防止已知危险技能绕过

## 测试覆盖

V0.2 共 9 个测试（全部通过）：

**ImmuneMemory 单元测试（2个）：**
- test_immune_memory_record_failure
- test_immune_memory_repeat_threshold_triggers_quarantine

**ImmuneGuard 单元测试（4个）：**
- test_immune_guard_unit_failed_source_quarantined — 失败轨迹来源 → quarantine
- test_immune_guard_unit_missing_evidence_quarantined — 证据不足 → quarantine
- test_immune_guard_unit_overgeneralized_quarantined — 步骤不足（< 3步）→ quarantine
- test_immune_guard_unit_draft_safe — 安全技能 → draft
- test_immune_guard_unit_reject_high_risk — 危险内容 → reject

**PhoenixEvo 集成测试（2个）：**
- test_safe_skill_passes_to_draft — 端到端安全路径
- test_dangerous_trajectory_rejected_by_verifier — 危险技能在 verifier 层被拦截

## V0.1 vs V0.2 对比

| 维度 | V0.1 | V0.2 |
|------|------|------|
| 技能生成 | ✅ | ✅ |
| 技能验证 | ✅ | ✅ |
| 危险内容过滤 | ✅（verifier层） | ✅（verifier + immune_guard双层） |
| 过度泛化检测 | ✅ | ✅（延伸至 immune_guard 层） |
| 免疫记忆 | ❌ | ✅（跨会话追踪） |
| 隔离区管理 | ❌ | ✅ |
| 系统级风险策略 | ❌ | ✅ |
| 人工复核要求 | 部分 | 全部（draft/quarantine） |
| auto-activation | 禁止 | 禁止（仍生效） |

## 文件清单

```
core/
├── immune_guard.py        # ImmuneGuard 主类
├── immune_memory.py       # ImmuneMemory 类
├── quarantine_manager.py  # QuarantineManager 类
├── risk_policy.py         # RiskPolicy + RiskProfile
├── phoenix_evo.py         # V0.2 主调度器（集成 immune_guard）
├── trajectory_logger.py   # V0.1
├── post_task_evaluator.py # V0.1
├── skill_miner.py         # V0.1
├── skill_verifier.py      # V0.1
├── skill_registry.py      # V0.1
└── __init__.py            # 导出所有模块

tests/
└── test_immune_guard.py   # 9个测试

skills/
├── draft/                 # V0.2：安全技能待复核
├── quarantine/            # V0.2：可疑技能隔离区
├── active/                # V0.2：经人工复核后激活
├── rejections/            # V0.2：被拒绝技能记录
└── immune_memory.json     # V0.2：免疫记忆持久化
```

## 下一步：V0.3 Curator

计划中的 V0.3 将添加自动技能维护功能：
- **重复技能合并**：相似度 > 0.6 的技能自动合并
- **漂移检测**：技能被修改后检测与原始版本的偏离
- **归档清理**：usage_count=0 + staleness > 30天的技能自动归档
- **draft → active 自动晋升**：仅在 curator 复核后由人工触发激活
