# Phoenix-Evo 核心设计文档

<p align="center">
  <strong>Agent 经验治理层 -- 从任务执行到能力沉淀的闭环系统</strong>
</p>

---

## 1. 设计哲学

### 1.1 核心命题

传统 Agent 框架关注"如何完成任务"，Phoenix-Evo 关注"如何管理从任务中获得的经验"。

```
传统方式：  任务 -> 执行 -> 结束（经验丢失）
Phoenix：  任务 -> 执行 -> 轨迹 -> 自评 -> 提取 -> 验证 -> 免疫 -> 入库 -> 复用
```

Phoenix-Evo 的目标是让 Agent 在每次任务结束后自动沉淀经验、修复缺陷、生成技能，并通过免疫系统防止错误经验污染长期能力。

### 1.2 三大原则

| 原则 | 含义 | 实现 |
|------|------|------|
| **自动怀疑** | 不信任任何未经验证的经验 | ImmuneGuard + SkillVerifier |
| **自动验证** | 每个技能必须通过回放和证据检验 | SkillReplay + SkillEvidence |
| **自动沉淀** | 验证通过的技能自动入库供复用 | SkillRegistry + SkillCurator |

---

## 2. 核心设计

### 2.1 经验治理闭环

将任务执行轨迹转化为经过验证的技能资产，形成闭环反馈。

```
任务执行
   |
TrajectoryLogger（记录完整轨迹）
   |
PostTaskEvaluator（规则引擎自评，无 LLM 依赖）
   |
SkillMiner（从轨迹中提取可复用技能）
   |
SkillVerifier（安全性和可信度验证）
   |
ImmuneGuard（免疫审查：approve / quarantine / reject）
   |
SkillRegistry（入库为 draft 状态）
   |
下次任务复用 -> 新轨迹 -> 循环
```

**设计要点：**
- 现有 Agent 框架（LangChain、AutoGPT）主要关注执行，不提供经验沉淀机制
- Phoenix-Evo 实现了"执行-学习-复用"的完整闭环
- 所有经验沉淀都经过安全审查，防止"经验中毒"

### 2.2 免疫防御系统

借鉴生物免疫系统的多层防御机制，构建 Agent 经验安全层。

```
第一层：SkillVerifier（模式匹配 + 规则检查）
   | 通过
第二层：ImmuneGuard（风险画像 + 危险模式检测）
   | 通过
第三层：ImmuneMemory（记忆累积，重复失败触发隔离）
   | 通过
入库（draft 状态，等待人工激活）
```

**免疫记忆机制：**
- 同一技能在相同标签下累计失败 >= 3 次 -> 自动隔离
- 隔离的技能需要人工复核才能恢复
- 所有免疫决策可追溯到原始轨迹

**危险模式检测：**
- 破坏性操作：`rm -rf`、`sudo rm`、`drop table`、`truncate`
- 金融操作：`payment`、`transfer money`、`sql inject`
- 安全风险：`eval()`、`exec()`、`pickle.loads`、`shell=True`
- 欺骗行为：`fake`、`impersonate`、`bypass`、`backdoor`
- 过度泛化：`always`、`never fail`、`guarantee`

### 2.3 技能治理引擎

自动管理技能生命周期，防止技能膨胀和质量退化。

```
Curator.scan()
   |
+-------------------------------------------+
| 相似技能 -> SkillVectorizer -> 合并建议    |
| 漂移技能 -> DriftDetector -> 降级/归档     |
| 隔离技能 -> QuarantineManager -> 人工复核  |
| 低质量   -> CuratorPolicy -> 归档/删除    |
+-------------------------------------------+
```

**治理策略：**
- **MergeAction：** 相似度 > 0.85 的技能合并为一个
- **DowngradeAction：** 成功率 < 0.3 的技能降级
- **ArchiveAction：** 长期未使用的技能归档
- **QuarantineAction：** 漂移检测异常的技能隔离
- **ReviewAction：** 边界情况提交人工复核

### 2.4 回放验证系统

每个技能都绑定原始轨迹，支持回放验证。

```
SkillCard
  +-- skill_md（技能内容）
  +-- source_trajectory（原始轨迹）
  +-- evidence_score（证据分）
  +-- replay_pass_rate（回放通过率）
  +-- runtime_success_rate（运行时成功率）
```

**Evidence Score 计算：**
```
evidence_score =
    0.30 * source_success     (原始任务是否成功)
  + 0.25 * replay_pass_rate  (回放通过率)
  + 0.20 * runtime_success   (运行时成功率)
  + 0.15 * usage_count_norm  (使用次数归一化)
  + 0.10 * recency_factor    (时间衰减因子)
```

### 2.5 运行时安全闸门

8 条硬性规则，在技能注入前进行最终安全检查。

| # | 规则 | 决策 |
|---|------|------|
| 1 | draft skill | DENY |
| 2 | quarantine skill | DENY |
| 3 | archived skill | DENY |
| 4 | evidence_score < 0.60 | DENY |
| 5 | risk_score > 0.50 | DENY |
| 6 | replay_regression = true | DENY |
| 7 | task_risk = critical + skill_risk != low | DENY |
| 8 | high/critical task + no replay | REVIEW_REQUIRED |

**设计原则：** 宁可拒绝一个好技能，也不允许一个危险技能通过。

### 2.6 任务生命周期管理

完整的任务状态机 + Hook 钩子系统。

```
TaskState 有限状态机：
  CREATED -> ROUTING -> INJECTING -> RUNNING -> SUCCESS/FAILED
                |                      |
            NO_SKILL -> FALLBACK    CANCELLED
```

**Hook 生命周期（12 个钩子点）：**
```
on_task_created -> on_before_route -> on_after_route
-> on_before_inject -> on_after_inject -> on_before_execute
-> on_execute（用户回调）
-> on_success / on_failure
-> on_before_cleanup -> on_after_cleanup -> on_task_done
```

### 2.7 反馈闭环

运行时结果自动回流，驱动技能质量演进。

```
RuntimeReporter（每条调用写一行 JSONL）
  -> OutcomeTracker（定时扫描日志文件）
      累计失败 >= 3 -> 触发 quarantine
  -> FeedbackDispatcher（同步分发）
      SkillRegistry.record_outcome()
        SkillCard metadata 更新
          Curator.scan() 审查 quarantine_skills
            quarantine_skill -> 降级/删除/恢复
```

---

## 3. 架构设计

### 3.1 分层架构

```
+---------------------------------------------+
|              CLI / API Layer                 |
+---------------------------------------------+
|           AgentRuntime (V0.8)               |
|    任务生命周期 + Hook 系统 + TaskStore      |
+---------------------------------------------+
|         PhoenixRuntime (V0.6)               |
|  SkillRouter -> RuntimeGuard -> ContextInject |
+---------------------------------------------+
|         Feedback Loop (V0.7)                |
|  OutcomeTracker -> FeedbackDispatcher        |
+---------------------------------------------+
|           Core Evolution (V0.1-V0.4)        |
|  Trajectory -> Evaluate -> Mine -> Verify    |
|  -> ImmuneGuard -> Registry -> Curator         |
+---------------------------------------------+
|           Integration Layer (V0.5)          |
|  HermesAdapter -> PhoenixBridge              |
+---------------------------------------------+
```

### 3.2 模块化设计

每个模块都是独立的、可测试的、可替换的：

- **core/** -- 核心进化逻辑，无外部依赖
- **runtime/** -- 运行时编排，依赖 core
- **integrations/** -- 外部系统集成，依赖 core + runtime
- **cli/** -- 命令行接口，依赖所有层

### 3.3 安全约束

- 候选技能只进 `skills/draft/`，不自动激活
- 涉及删除/支付/绕过/攻击的技能被免疫系统拒绝
- 所有技能可追溯到原始轨迹
- 禁止自动修改 active skills
- 禁止自动删除技能

---

## 4. 当前局限

为保持透明，以下局限被明确承认：

1. **检索是统计方法，不是语义检索。** TF-IDF + 余弦相似度是词袋方法，不捕获真正的语义含义。基于 embedding 的检索（sentence-transformers、向量数据库）将是真正的升级方向。
2. **漂移检测是自适应阈值，不是变点检测。** 当前实现基于群体统计设置动态阈值，不检测技能行为的时间序列变化（需要 CUSUM、EWMA 或贝叶斯方法）。
3. **中文分词使用 jieba，回退方案为字符级 + bigram。** 质量取决于 jieba 是否安装。
4. **尚无真实 LLM Agent 集成。** 所有演示使用合成/模拟 Agent。核心价值主张（治理技能记忆能提升 Agent 任务表现）有待真实 LLM Agent 验证。
5. **实验验证有限。** 现有对比测试使用 8 个技能的合成语料库。真实评估需要更大的语料库和端到端任务成功率测量。

---

## 5. 未来方向

### 5.1 短期（V1.1-V1.3）
- 技能版本管理（同一技能的演进历史）
- 跨项目技能共享（技能市场）
- 自动化回放测试框架

### 5.2 中期（V2.0）
- 基于 embedding 的检索（sentence-transformers + FAISS/ChromaDB）实现真正的语义搜索
- 多 Agent 协作进化（共享免疫记忆）
- 技能组合（复合技能自动生成）
- CUSUM 或 EWMA 漂移检测替代当前的自适应阈值

### 5.3 长期
- 分布式技能库（去中心化经验治理）
- 联邦学习式技能共享（隐私保护）
- 自我修复架构（系统级自进化）

---

## 6. 总结

Phoenix-Evo 的核心贡献是提供了一种有原则的 Agent 经验治理方法：自动验证、监控和管理累积的经验，而不是盲目信任。

这个方法包含三个根本性的设计决策：

1. **经验不再丢失** -- 每次任务执行都产生可复用的技能资产
2. **安全不再妥协** -- 多层免疫系统确保经验质量
3. **能力可以演进** -- Agent 在使用中通过验证和反馈持续改进技能

经验治理不是自动相信自己，而是自动怀疑自己、验证自己、管理自己。
