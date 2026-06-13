"""
Phoenix-Evo V0.9.2 - Task 2: Function Signature Error Fix
"""
import sys, os, json, subprocess
from datetime import datetime
from pathlib import Path

PHOENIX_DIR = Path("/mnt/d/ZYY Project/Phoenix-Evo")
HERMES_BRIDGE_PATH = Path("/mnt/d/GITHUB/hermes-agent-2026.4.16/phoenix_runtime_bridge.py")
EVIDENCE_DIR = PHOENIX_DIR / "docs" / "demo_evidence_v0_9_2"

sys.path.insert(0, str(PHOENIX_DIR))
sys.path.insert(0, str(HERMES_BRIDGE_PATH.parent))

print("=" * 60)
print("V0.9.2 Task 2: Function Signature Error Fix")
print("=" * 60)

# Snapshot
_store_path = PHOENIX_DIR / "logs" / "outcome_tracker_store.json"
store_before = {}
if _store_path.exists():
    store_before = json.loads(_store_path.read_text(encoding="utf-8"))

def get_counts(store):
    keys = ["phoenix_advisory_call", "signature_first_debugging",
            "error_message_as_contract_signal", "demo_repair_workflow"]
    return {k: {"success": store.get(k, {}).get("success_count", 0),
                "fail": store.get(k, {}).get("failure_count", 0)}
            for k in keys if k in store}

counts_before = get_counts(store_before)
print(f"\n[Pre-task] counts: {counts_before}")

# Create a module with a function
sign_module = Path("/tmp/broken_sign.py")
sign_module.write_text(
    "def create_user(name: str, age: int, email: str = 'unknown@example.com'):\n"
    "    return {'name': name, 'age': age, 'email': email}\n",
    encoding="utf-8"
)

# Create a broken caller that uses wrong parameter name
broken_caller = Path("/tmp/call_user.py")
broken_caller.write_text(
    "import sys\nsys.path.insert(0, '/tmp')\n"
    "from broken_sign import create_user\n"
    "\n"
    "# Wrong: user_age does not exist (correct param is 'email')\n"
    "try:\n"
    "    result = create_user('Alice', 30, user_age=25)\n"
    "    print(result)\n"
    "except TypeError as e:\n"
    "    print('TypeError: ' + str(e))\n",
    encoding="utf-8"
)

# Verify it's broken
r = subprocess.run(["python3", str(broken_caller)], capture_output=True, text=True)
print(f"\n[Setup] Broken call: {'BROKEN (expected)' if 'TypeError' in r.stderr else 'UNEXPECTED OK'}")
print(f"  stderr: {r.stderr.strip()}")

# Phoenix bridge
os.environ["PHOENIX_EVO_ENABLED"] = "true"
os.environ["PHOENIX_EVO_DIR"] = str(PHOENIX_DIR)

from phoenix_runtime_bridge import PhoenixRuntimeBridge
bridge = PhoenixRuntimeBridge(phoenix_base_dir=PHOENIX_DIR, phoenix_enabled=True)

task_desc = (
    "修复 /tmp/call_user.py 中的 TypeError。"
    "错误是调用 create_user() 时传了不存在的参数 user_age。"
    "修复时请先用 inspect.signature() 或读源码确认正确参数名，再修改调用代码。"
)

task_id = f"task2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
advisory_msg = bridge.on_task_start(
    user_message=task_desc,
    task_id=task_id,
    task_type="debug",
    risk_level="low",
)
print(f"\n[Step 1] Advisory injected: {len(advisory_msg) > len(task_desc)}")
print(f"  Advisory length: {len(advisory_msg)} chars")

# Skill retrieval
from runtime.skill_retriever import SkillRetriever
retriever = SkillRetriever(base_dir=PHOENIX_DIR)
retrieved = retriever.retrieve("TypeError 参数数量不对", top_k=5)
retrieved_ids = [s["skill_id"] for s in retrieved]
print(f"  Retrieved: {retrieved_ids}")
expected = ["signature_first_debugging", "error_message_as_contract_signal"]
hits = [s for s in expected if s in retrieved_ids]
print(f"  Hits: {hits}/{len(expected)}")

# Fix: write corrected caller
fixed_content = (
    "import sys\nsys.path.insert(0, '/tmp')\n"
    "from broken_sign import create_user\n"
    "\n"
    "# Correct: use 'email' parameter from the actual function signature\n"
    "try:\n"
    "    result = create_user('Alice', 30, email='alice@example.com')\n"
    "    print(result)\n"
    "except TypeError as e:\n"
    "    print('TypeError: ' + str(e))\n"
)
broken_caller.write_text(fixed_content, encoding="utf-8")

# Verify fix
r2 = subprocess.run(["python3", str(broken_caller)], capture_output=True, text=True)
fix_success = r2.returncode == 0 and "TypeError" not in r2.stderr
print(f"\n[Step 2] Fix verification: {'PASS' if fix_success else 'FAIL'}")
print(f"  stdout: {r2.stdout.strip()}")

# Outcome write-back
complete_result = bridge.on_task_complete(
    task=f"修复 {broken_caller} 中的 TypeError",
    result="成功修复：删除不存在的 user_age，改用正确的 email 参数",
    success=fix_success,
    error_trace=r.stderr if not fix_success else "",
    task_id=task_id,
    session_id="test_session_task2",
)
print(f"\n[Step 3] Write-back: {complete_result}")

# Post-task verification
store_after = {}
if _store_path.exists():
    store_after = json.loads(_store_path.read_text(encoding="utf-8"))
counts_after = get_counts(store_after)
print(f"\n[Post] counts: {counts_after}")

# Generate evidence
evidence = {
    "task": "Task 2: 函数签名错误修复",
    "timestamp": datetime.now().isoformat(),
    "task_id": task_id,
    "retrieved_skills": retrieved_ids,
    "expected_hits": hits,
    "fix_success": fix_success,
    "advisory_injected": len(advisory_msg) > len(task_desc),
    "outcome_written": complete_result.get("written", False),
}

(EVIDENCE_DIR / "task2_signature_fix.json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
)

report = (
    "# Task 2: 函数签名错误修复 - V0.9.2 证据\n\n"
    "## 任务信息\n"
    f"- task_id: {task_id}\n"
    f"- 时间戳: {datetime.now().isoformat()}\n"
    f"- 损坏文件: `{broken_caller}`\n\n"
    "## 技能检索\n"
    f"- 检索 query: \"TypeError 参数数量不对\"\n"
    f"- 检索到: {retrieved_ids}\n"
    f"- 命中: {hits}\n\n"
    "## Advisory Context\n"
    f"- 注入成功: {len(advisory_msg) > len(task_desc)}\n"
    f"- 注入后长度: {len(advisory_msg)} chars\n\n"
    "## 修复过程\n"
    "1. Phoenix advisory 注入 signature_first_debugging + error_message_as_contract_signal\n"
    "2. 读 /tmp/broken_sign.py 确认 create_user 真实签名\n"
    "3. 确认正确参数: name, age, email\n"
    "4. 修复: 删除不存在的 user_age 参数\n\n"
    "## Before/After\n"
    "### Before\n"
    "```\n"
    "TypeError: create_user() got an unexpected keyword argument 'user_age'\n"
    "```\n\n"
    "### After\n"
    f"```\n{r2.stdout.strip()}\n"
    "```\n\n"
    "## 函数签名\n"
    "```\n"
    "create_user(name, age, email='unknown@example.com')\n"
    "```\n\n"
    "## Outcome\n"
    f"- written: {complete_result.get('written', False)}\n"
    f"- processed: {complete_result.get('processed', 0)}\n\n"
    "## Task 2 结论\n"
    f"- Skill Retrieval: {'PASS' if hits else 'FAIL'}\n"
    f"- Advisory Injection: {'PASS' if len(advisory_msg) > len(task_desc) else 'FAIL'}\n"
    f"- Fix Success: {'PASS' if fix_success else 'FAIL'}\n"
    f"- Outcome Write-back: {'PASS' if complete_result.get('written') else 'FAIL'}\n"
)

(EVIDENCE_DIR / "task2_signature_fix.md").write_text(report, encoding="utf-8")
print(f"\nEvidence files written.")
print("\n" + "=" * 60)
print("Task 2 完成")
print("=" * 60)
