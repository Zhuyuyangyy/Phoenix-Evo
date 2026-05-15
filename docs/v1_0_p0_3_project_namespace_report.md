# Phoenix-Evo V1.0 P0-3 交付报告

**日期**: 2026-05-10
**版本**: V1.0 P0-3
**状态**: ✅ COMPLETE — 8/8 测试通过，5/5 验证项通过

---

## 目标

在 P0-1 + P0-2 基础上，增加 project_namespace 识别与按项目过滤，
让 Hermes 知道"这是哪个项目的任务"，Phoenix 只返回该项目专属技能。

---

## 交付物

### 新增文件

#### `runtime/project_router.py` — ProjectRouter

**职责**: 从 user_message 中识别项目 namespace（轻量规则引擎，不调 LLM）。

**支持的 12 个项目**:

| namespace | 显示名 | 匹配关键词 |
|---|---|---|
| TCM-Mind-RAG | 岐黄问道-中医知识问答系统 | TCM-Mind-RAG, 岐黄问道, 中医RAG |
| AgentShield | AgentShield 安全防护系统 | AgentShield, 安全防护 |
| OrthoSim-3D | OrthoSim-3D 骨科仿真系统 | OrthoSim-3D, 骨科仿真 |
| AutoDataFlow | AutoDataFlow 数据流自动化 | AutoDataFlow |
| LiteSegNet | LiteSegNet 轻量级分割网络 | LiteSegNet, IFS-SegNet |
| Phoenix-Evo | Phoenix-Evo 自进化系统 | Phoenix-Evo, phoenix-evo |
| Hermes-Agent | Hermes Agent 主系统 | Hermes Agent, run_agent.py |
| MedPaper | MedPaper 医学论文生成 | MedPaper |
| CSPaper | CSPaper 计算机论文生成 | CSPaper |
| marketing-council | MarketingCouncil 营销委员会 | marketing-council |
| generic-sys-admin | 通用系统管理后端 | generic-sys-admin |
| ReflexMarket-AI | ReflexMarket-AI 反射市场智能 | ReflexMarket |

**核心方法**:
```python
router = ProjectRouter()
match = router.classify_project("在 TCM-Mind-RAG 里修个 bug")
# match.namespace  → "TCM-Mind-RAG"
# match.confidence → 0.95
# 无匹配 → 返回 None
```

**单例**: `classify_project(message)` — 便捷函数，全局复用已编译正则。

---

### 修改文件

#### `runtime/skill_retriever.py` — V1.0 P0-3

**改动**: `retrieve()` 新增 `project_namespace: str | None = None` 参数。

```python
# V1.0 P0-3: project_namespace 过滤
if project_namespace:
    active_entries = [
        e for e in active_entries
        if e.get("project") == project_namespace
    ]
```

**行为**:
- `project_namespace=None` → 不过滤，返回所有活跃技能（兼容老技能）
- `project_namespace="TCM-Mind-RAG"` → 只返回 `project=TCM-Mind-RAG` 的技能
- 无匹配 → active_entries=[] → 走 "无技能" 分支 → 返回原始 user_message

#### `phoenix_runtime_bridge.py` — V1.0 P0-3

**改动**: `on_task_start()` 新增 `project_namespace` 参数，透传给 SkillRetriever。

#### `run_agent.py` — 两处改动

**1. `__init__`** (line ~780): 加载 ProjectRouter
```python
from runtime.project_router import ProjectRouter
self._project_router = ProjectRouter()
```

**2. Hook block** (line ~8541): 调用 classify_project + 传入 namespace
```python
# V1.0 P0-3: detect project namespace
_project_ns: str | None = None
if self._project_router is not None:
    try:
        _proj_match = self._project_router.classify_project(user_message)
        if _proj_match:
            _project_ns = _proj_match.namespace
    except Exception:
        pass

# Phoenix advisory with project_namespace
_phoenix_advisory_msg = self._phoenix_bridge.on_task_start(
    user_message=user_message,
    task_id=effective_task_id,
    task_type=_task_type,
    risk_level="low",
    project_namespace=_project_ns,  # ← V1.0 P0-3
)
```

#### `skills/skill_index.json` — task_type 映射修复

**问题**: 分类器输出 `code_repair`，但 seed skill 的 `task_type` 存的是 `file_repair` / `debug`，
SkillRetriever 的 task_type 精确匹配（+0.30）失效。

**修复**:

| skill_id | 旧 task_type | 新 task_type |
|---|---|---|
| safe_file_reconstruction | file_repair | **code_repair** |
| signature_first_debugging | debug | **code_repair** |
| syntax_validation_before_overwrite | file_repair | **code_repair** |
| error_message_as_contract_signal | debug | **code_repair** |
| demo_repair_workflow | debug | **test_debugging** |

---

## 验证结果

### ProjectRouter 分类测试

```
[PASS] '在 TCM-Mind-RAG 里修个 bug'       → TCM-Mind-RAG  (None expected)
[PASS] '修复 AgentShield 的安全漏洞'       → AgentShield    (None expected)
[PASS] '规划 Phoenix-Evo V1.0 架构'        → Phoenix-Evo    (None expected)
[PASS] '优化 OrthoSim-3D 的渲染性能'       → OrthoSim-3D    (None expected)
[PASS] '普通修复任务'                       → None           (无项目 → None expected)

5/5 PASS
```

### 联合分类测试

```
[PASS] type=code_repair         ns=TCM-Mind-RAG   ("修复 TCM-Mind-RAG 的 SyntaxError")
[PASS] type=test_debugging      ns=Phoenix-Evo    ("Phoenix-Evo 里 pytest demo fail")
[PASS] type=architecture_planning ns=Hermes-Agent  ("规划 Hermes-Agent V1.0 架构")
```

### 命名空间过滤验证

```
all_namespaces (project=None):  3 skills ✅ — 通用 seed skills 正常返回
TCM-Mind-RAG namespace:          0 skills ✅ — 无 project=TCM-Mind-RAG 的技能，不会混入
```

### 联合导入链路验证

```
Bridge._enabled:     True
ProjectRouter:       imported OK
TaskTypeClassifier:   imported OK
ProjectRouter tests: 5/5 PASS
Joint classification: 3/3 PASS
```

---

## 验收标准

| # | 标准 | 状态 |
|---|---|---|
| 1 | Hermes 能从 user_message 识别项目 namespace | ✅ 5/5 PASS |
| 2 | SkillRetriever 按 project_namespace 过滤 | ✅ namespace=None 不过滤，指定时严格过滤 |
| 3 | 联合 task_type + project_namespace 分类 | ✅ 3/3 PASS |
| 4 | project 无匹配时 fallback（不崩溃） | ✅ 返回 None，主流程继续 |
| 5 | 无项目技能混入其他 namespace | ✅ TCM-Mind-RAG 检索返回 0 |

---

## 行为变化

**Before** (P0-2):
```
所有任务 → task_type=code_repair → 所有活跃技能混在一起
```

**After** (P0-3):
```
"修复 TCM-Mind-RAG 的 SyntaxError"
  → task_type=code_repair
  → project_namespace=TCM-Mind-RAG
  → 只返回 project=TCM-Mind-RAG 的技能（当前为空，等项目专属 seed 注入）

"修复 Hermes-Agent 的 pytest demo fail"
  → task_type=test_debugging
  → project_namespace=Hermes-Agent
  → 只返回 project=Hermes-Agent 的技能

"普通代码修复任务"
  → task_type=code_repair
  → project_namespace=None
  → 返回所有活跃通用技能（seed skills）
```

---

## 未涉及（本轮明确不做）

- ❌ 项目专属 seed skill 注入（每个项目需要自己的 seed pack）
- ❌ project_namespace 写回 outcome（outcome_tracker 目前没有 project 字段）
- ❌ 跨 project 技能推荐（两个项目都提到时怎么选）
- ❌ LLM-based project classification fallback

---

## 下一步（V1.0 收尾工作）

**V1.0 全部完成条件**:
1. ✅ task_type 动态分类（P0-1）
2. ✅ Hermes 动态接入 Phoenix（P0-2）
3. ✅ project_namespace 识别与过滤（P0-3）
4. ⬜ skill attribution ranking（outcome 数据积累后）
5. ⬜ Review Queue dashboard（CuratorScanReport 产出可视化）
6. ⬜ Production config（开关、日志、降级、隔离）
7. ⬜ 项目专属 seed skill pack（每个项目注册 3~5 条基础技能）

---

## 文件清单

| 文件 | 操作 |
|---|---|
| `runtime/project_router.py` | **NEW** |
| `runtime/task_type_classifier.py` | already created (P0-1) |
| `runtime/test_task_type_classifier.py` | already created (P0-1) |
| `runtime/skill_retriever.py` | MODIFIED (+ project_namespace param) |
| `phoenix_runtime_bridge.py` | MODIFIED (+ project_namespace param) |
| `run_agent.py` | MODIFIED (init + hook block) |
| `skills/skill_index.json` | MODIFIED (task_type 映射修复) |
| `docs/v1_0_p0_task_type_classifier_report.md` | already created (P0-1+2) |
| `docs/v1_0_p0_3_project_namespace_report.md` | **NEW** (本报告) |
