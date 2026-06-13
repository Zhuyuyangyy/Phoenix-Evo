# Phoenix-Evo V0.5 Hermes Bridge 技术说明

## 概述

V0.5 在 V0.2 的基础上新增 Hermes Bridge，把 Hermes Agent 的任务执行轨迹接入 Phoenix 的自进化闭环。

核心目标：



## 架构



## V0.5 新增模块

### 1. HermesAdapter（事件适配层）

位置：integrations/hermes_adapter.py

职责：把 Hermes 的回调事件转成 Phoenix 能理解的轨迹格式。

核心方法：

| 方法 | 对应 Hermes 事件 | 说明 |
|------|-----------------|------|
| on_session_start() | plugin hook | 新会话初始化 Phoenix 轨迹 |
| on_step() | step_callback | 每轮迭代前，记录上轮工具结果 |
| on_tool_progress() | tool_progress_callback | 工具开始/完成事件 |
| on_tool_complete() | tool_complete_callback | 工具完成，记录最终结果 |
| on_task_end() | run_conversation 返回后 | 触发 Phoenix 自进化闭环 |
| run_full_loop() | 手动 | 初始化 Phoenix 轨迹记录 |
| complete_task() | 手动 | 完成任务并触发自进化 |

Hermes 事件 -> Phoenix 格式映射：



### 2. AsyncBridge（异步桥接器）

位置：integrations/async_bridge.py

职责：解决 Hermes（async）与 Phoenix（sync）的调用模式差异，用队列解耦。

核心设计：



关键特性：
- 有界队列（maxsize=100），满则丢弃最旧事件，不阻塞 Hermes
- Phoenix worker 是 daemon thread，进程退出时自动终止
- bridge.stop(timeout=5.0) 优雅关闭
- Phoenix worker 异常被捕获，不泄露到 Hermes 主线程

### 3. HermesSkillExporter（格式转换器）

位置：integrations/hermes_skill_exporter.py

职责：把 Phoenix 内部 skill 格式转换成 Hermes /skills 可读的 SKILL.md。

Phoenix 内部格式 -> Hermes 格式：



核心方法：

| 方法 | 说明 |
|------|------|
| export_skill(skill_id) | 导出单个 draft skill |
| export_all_drafts() | 导出所有 draft skills |
| export_quarantined() | 导出 quarantine skills（需人工确认） |
| get_hermes_export_status() | 返回导出状态 |

### 4. IntegrationPolicy（集成策略）

位置：integrations/integration_policy.py

职责：定义所有集成约束，供 Bridge 和 Exporter 调用检查。

V0.5 核心约束：

| 约束 | 规则 |
|------|------|
| 自动激活 | 禁止 |
| 自动调用 skill | 禁止 |
| 覆盖 Hermes skill | 禁止 |
| 删除 skill | 禁止 |
| 修改 Hermes 系统文件 | 禁止 |
| 导出 draft | 需人工复核 |
| 导出 quarantine | 禁止（需人工确认） |
| 高风险 trajectory | 不生成 skill |

## Hermes 集成点

### 回调接口

V0.5 使用 Hermes 已有回调接口，无需修改 Hermes 核心代码：



### Hermes 事件流



## V0.5 约束总结

### 允许的操作

- 捕获 Hermes 执行轨迹
- Phoenix 自进化闭环运行（生成 draft skill）
- 导出 draft skill 到 Hermes 兼容格式
- 人工复核后激活 draft skill

### 禁止的操作

- 自动激活任何 skill
- 自动调用已有 skill
- 自动修改/覆盖 Hermes 系统 skill
- 自动删除 skill
- 修改 Hermes 系统文件
- 导出 quarantine/reject 状态 skill（除非人工确认）

## V0.5 vs V0.4 对比

| 维度 | V0.4 | V0.5 |
|------|------|------|
| Hermes 事件适配 | 无 | HermesAdapter |
| 异步队列解耦 | 无 | AsyncBridge |
| Hermes skill 格式导出 | 无 | HermesSkillExporter |
| 集成策略层 | 无 | IntegrationPolicy |
| Hermes 技能库读取 | 无 | 预留（V0.6） |
| 运行时 Skill Router | 无 | 预留（V0.6） |

## V0.6 计划

- Runtime Skill Router：Hermes 任务开始时查询 Phoenix 可用 skill
- 增量轨迹累积：工具调用在 worker 线程中增量写入轨迹文件
- Hermes skill 回源：Phoenix 追踪导出后 skill 的使用情况

## V0.7 计划

- Phoenix 正式接管 Hermes skill 生命周期
- Curator 自动技能维护
- 跨 Agent skill 共享
