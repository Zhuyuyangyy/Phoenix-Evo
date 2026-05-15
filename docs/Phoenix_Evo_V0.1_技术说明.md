# Phoenix-Evo V0.1 技术说明

## 一、系统定位

Phoenix-Evo 是对 Hermes Agent 自进化能力的工程化实现。

Hermes 的 built-in learning loop 依赖 LLM 做自我评估。Phoenix-Evo V0.1 采用**纯规则引擎**，无需 LLM 调用，在本地即可完成完整闭环。

## 二、模块关系

```
TrajectoryLogger
    ↓ (trajectory dict)
PostTaskEvaluator
    ↓ (EvaluationResult: should_extract + quality_score + failure_type)
[当 should_extract=True]
    ↓
SkillMiner
    ↓ (skill_candidate dict: skill_md + inputs + procedure)
SkillVerifier
    ↓ (VerificationResult: passed + risk_level + warnings)
[当 passed=True]
    ↓
SkillRegistry
    → skills/draft/{skill_id}.md
    → skill_index.json 更新
```

## 三、轨迹记录格式

```json
{
  "task_id": "task_20260507_143022_a1b2c3",
  "task_goal": "用户目标描述",
  "task_type": "coding|writing|research|planning|debugging|general",
  "risk_level": "low|medium|high",
  "session_id": "20260507",
  "started_at": "2026-05-07T14:30:22",
  "completed_at": "2026-05-07T14:35:10",
  "duration": "288.0s",
  "plan": [
    {"step": "读取文件", "expected": "文件内容", "logged_at": "..."}
  ],
  "actions": [
    {
      "action": "read_file",
      "params": {"path": "/tmp/test.py"},
      "result": "文件内容",
      "logged_at": "2026-05-07T14:30:25"
    }
  ],
  "tool_calls": [
    {
      "tool": "terminal",
      "args": {"command": "python fix.py"},
      "raw_result": "...",
      "error": "",
      "logged_at": "..."
    }
  ],
  "errors": [
    {
      "phase": "execution",
      "message": "FileNotFoundError: ...",
      "recoverable": true,
      "logged_at": "..."
    }
  ],
  "fixes": [
    {
      "phase": "execution",
      "strategy": "使用绝对路径重试",
      "succeeded": true,
      "logged_at": "..."
    }
  ],
  "final_output": "修复完成",
  "artifacts": ["/tmp/out.py"],
  "success": true
}
```

## 四、自评引擎规则

### 评分维度（加权求和）

| 维度 | 权重 | 说明 |
|------|------|------|
| success | 0.30 | 任务是否成功完成 |
| no_error | 0.20 | 是否有错误记录 |
| no_fix | 0.15 | 是否无需修复 |
| verification | 0.15 | 是否有验证动作 |
| tool_efficiency | 0.10 | 工具调用次数是否合理（<20为佳）|
| no_repeat | 0.10 | 是否有重复 action |

### 提取判定规则

```
should_extract = True 当且仅当：
  (quality > 0.7)                                    → 高质量，提取
  或 (quality > 0.5 且 有 fixes)                    → 从修复中学习
  或 (reuse > 0.5 且 quality > 0.5)                 → 复用潜力高

should_extract = False 当：
  failure_type in {SAFETY, PLANNING}                → 安全/规划失败不提取
  quality <= 0.5 且 reuse <= 0.5                    → 质量过低
```

### 失败归因类型

| 类型 | 触发条件 | 描述 |
|------|----------|------|
| planning_failure | 规划阶段关键词 | 任务拆解错误 |
| tool_call_failure | 超时关键词 | 工具调用失败 |
| context_incomplete | not found / enoent | 上下文不足 |
| execution_failure | exec/run/code 阶段 | 代码/命令写错 |
| verification_failure | 验证相关 | 未检查结果 |
| memory_failure | 忘记历史规则 | 记忆失效 |
| safety_failure | permission/denied | 越权/误操作 |

## 五、技能验证规则

### 危险内容检测（正则）

```
rm -rf, sudo rm, drop table, delete all, truncate, shred
payment, transfer money, sql inject
sudo chmod 0, eval(), exec(), pickle.loads, shell=True
fake, impersonat, bypass, backdoor
always, never fail, guarantee
```

### 高风险任务类型

```
HIGH_RISK_TYPES = {payment, auth_bypass, penetration, data_destruction, privacy_steal}
```

### 过度泛化检测

```
- 检测绝对表述：一切/所有/always/never/guarantee
- 检查步骤数量：procedure < 2 步 → 警告
```

## 六、技能生命周期

```
candidate → draft → active → stale → archived
              ↑
         V0.1 只到这里
         必须人工激活
```

V0.1 激活规则：
- `quality_score >= 0.8` + `confidence >= 0.8` + `risk_level == low` → 可申请激活
- `risk_level == medium` → 需要人工确认
- `risk_level == high` → 禁止激活

## 七、与 Hermes Agent 的集成方式

Phoenix-Evo 可以作为 Hermes Agent 的外置自进化模块：

```python
# Hermes Agent 的 run_agent.py 中：
from phoenix_evo import PhoenixEvo

evo = PhoenixEvo()

# 任务开始时
evo.run_full_loop(task_goal=user_goal, task_type=task_type)

# 每次工具调用后
evo.logger.log_tool_call(tool_name, args, result, error)

# 任务结束时
report = evo.complete_task(success=task_success, final_output=response)
```

轨迹文件保存在 `data/trajectories/`，可供 Hermes 的 `/skills` 系统读取为上下文记忆。

## 八、V0.1 限制

1. **纯规则 vs LLM**：自评和验证依赖人工规则，无法处理复杂语义判断
2. **无主动技能激活**：V0.1 所有技能只到 draft，需要人工激活
3. **无 Curator 治理**：V0.2 才有周期性技能库维护
4. **单轨迹验证**：V0.1 只检查当前轨迹，V0.3 才做跨轨迹验证
5. **无轨迹压缩**：长对话轨迹全量保存，V0.3 才加压缩

## 九、升级路线

| 版本 | 内容 | 目标 |
|------|------|------|
| V0.1 | 5模块闭环 + demo + 测试 | 本地可跑 |
| V0.2 | Immune Guard + 风险分类 | 免疫层完整 |
| V0.3 | Curator 周期性治理 | 技能库自维护 |
| V0.4 | 接入 ASF-BGT | 失败归因连分支树 |
