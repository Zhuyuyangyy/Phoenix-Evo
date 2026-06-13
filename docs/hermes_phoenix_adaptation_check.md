# Hermes Phoenix Adaptation Check

**Date**: 2026-05-10 17:54
**Version**: V0.9.3-adaptation

## 1. task_start 前自动调用 Phoenix advisory

**Status**: PARTIAL

**Current**: run_agent.py:8539-8546 每次任务前调用 on_task_start



**Gap**: task_type 硬编码为 "general"，SkillRetriever 里的 task_type routing 不生效

**File**: run_agent.py:8544

## 2. task_complete 后自动写回 OutcomeTracker

**Status**: YES

**Current**: run_agent.py:11282-11294
调用 on_task_complete，传入 task/result/success/error_trace，但忽略返回值 injected_skill_ids

**Gap**: Hermes 拿到 injected_skill_ids 但不消费、不展示

## 3. 识别 injected_skill_ids 并保留归因

**Status**: YES (Phoenix层)，NO (Hermes层)

Phoenix 层已写入 injected_skill_ids（见 jsonl 证据），但 Hermes 不展示、不记录、不用于后续决策

## 4. 根据任务自动选 skill，而非固定 Phoenix skill

**Status**: NO — task_type 硬编码导致 SkillRetriever 按类型筛选失效

SkillRetriever 里有 task_type routing：
- debug: signature_first_debugging, error_message_as_contract_signal
- file_repair: safe_file_reconstruction, syntax_validation_before_overwrite
- coding: demo_repair_workflow
- 但 Hermes 永远传 "general" → 全部 skill 等概率混合

## 5. PHOENIX_EVO_ENABLED=false 时原行为不变

**Status**: YES

run_agent.py:8538:  → bridge 为 None 时跳过后静默
phoenix_runtime_bridge.py: __init__ 中 self._enabled=False 时返回原始消息

## 6. Phoenix bridge 出错不崩溃

**Status**: YES

两处 try/except pass：
- run_agent.py:8547-8548 (on_task_start)
- run_agent.py:11295-11296 (on_task_complete)

## 7. 推广到其他项目（TCM-Mind-RAG/AgentShield/ReflexMarket-AI/MarketingCouncil）

**Status**: NO

PhoenixRuntimeBridge 的 SkillRetriever 只认 Phoenix-Evo 的 skills/active/ 目录
没有 project namespace 隔离，没有多项目 skill 注册机制

## Gap 汇总

| # | Gap | Severity | File |
|---|-----|----------|------|
| 1 | task_type 硬编码 general | HIGH | run_agent.py:8544 |
| 2 | Hermes 不消费 injected_skill_ids | MED | run_agent.py:11287 |
| 3 | 无 project namespace 隔离 | HIGH | phoenix_runtime_bridge.py |
| 4 | 无 task_type_classifier | HIGH | run_agent.py:8544 |
| 5 | SkillRetriever 只读 Phoenix skills | MED | skill_retriever.py |

## 需要新增的组件

### 1. task_type_classifier (V1.0 must)

职责：从 user_message 推断 task_type (debug/file_repair/coding/general)
方案：关键词匹配（TypeError→debug，修复→file_repair，demo/test→coding）
文件：runtime/task_type_classifier.py

### 2. project_skill_router (V1.0 must)

职责：根据 project_context 路由到不同 skill namespace
- phoenix: /mnt/d/ZYY Project/Phoenix-Evo/skills/
- tcm: /mnt/d/ZYY Project/TCM-Mind-RAG/skills/
- agentshield: /mnt/d/GITHUB/openclaw-2026.4.10/workplace/projects/AgentShield/skills/

### 3. skill_namespace (V1.0 nice-to-have)

每个项目有独立 skills/ 目录，运行时按 project_context 切换

## V1.0 前必须补齐的最小改动清单

P0（阻塞，不补无法自适应选 skill）：
1. run_agent.py:8544 — 从 user_message 推断 task_type，动态传入 on_task_start
2. runtime/task_type_classifier.py — 新增，基于关键词推断任务类型
3. phoenix_runtime_bridge.py — 新增 project_context 参数，按项目路由 skill_retriever

P1（不阻塞但影响数据质量）：
4. run_agent.py:11287 — 把 injected_skill_ids 写入 session metadata 或返回
5. skill_retriever.py — 支持 project_namespace 参数，多项目 skills 共存

P2（V1.0 nice-to-have）：
6. docs/v1_0_roadmap.md — 规划 Skill attribution ranking / Review dashboard / Auto-curation stability

## 当前 skill counts

- phoenix_advisory_call: success=9
- safe_file_reconstruction: success=3
- syntax_validation_before_overwrite: success=2
- signature_first_debugging: success=2
- demo_repair_workflow: success=0

## jsonl 证据（injected_skill_ids 已写入）

- skill=syntax_validation_before_overwrite task=v093check_171321 injected=['syntax_validation_before_overwrite', 'safe_file_reconstruction']
- skill=safe_file_reconstruction task=v093check_171321 injected=['syntax_validation_before_overwrite', 'safe_file_reconstruction']
- skill=signature_first_debugging task=v093check_171321 injected=['syntax_validation_before_overwrite', 'safe_file_reconstruction']
- skill=phoenix_advisory_call task=v093check_171321 injected=['syntax_validation_before_overwrite', 'safe_file_reconstruction']

## 结论

V0.9.3 Fix 1+2 在 Phoenix 层已完成，但 Hermes 层有三个关键 Gap：
1. task_type 硬编码导致 skill 选不准
2. 无 project namespace 导致无法扩展到其他项目
3. injected_skill_ids 写入了但 Hermes 不消费

V1.0 最小改动：task_type_classifier + project_skill_router，两个文件，修复 P0。