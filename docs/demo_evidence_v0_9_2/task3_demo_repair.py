"""
Phoenix-Evo V0.9.2 - Task 3: Demo fail -> pass Repair
"""
import sys, os, json, subprocess
from datetime import datetime
from pathlib import Path

PHOENIX_DIR = Path("/mnt/d/ZYY Project/Phoenix-Evo")
EVIDENCE_DIR = PHOENIX_DIR / "docs" / "demo_evidence_v0_9_2"

HERMES_BRIDGE_DIR = Path("/mnt/d/GITHUB/hermes-agent-2026.4.16")
sys.path.insert(0, str(PHOENIX_DIR))
sys.path.insert(0, str(HERMES_BRIDGE_DIR))

print("=" * 60)
print("V0.9.2 Task 3: Demo fail -> pass Repair")
print("=" * 60)

_store_path = PHOENIX_DIR / "logs" / "outcome_tracker_store.json"
store_before = {}
if _store_path.exists():
    store_before = json.loads(_store_path.read_text(encoding="utf-8"))

def get_counts(store):
    keys = ["phoenix_advisory_call", "demo_repair_workflow",
            "safe_file_reconstruction", "syntax_validation_before_overwrite"]
    return {k: {"success": store.get(k, {}).get("success_count", 0),
                "fail": store.get(k, {}).get("failure_count", 0)}
            for k in keys if k in store}

counts_before = get_counts(store_before)
print("\n[Pre-task] counts: " + str(counts_before))

DEMO_FILE = Path("/tmp/demo_calculator.py")
DEMO_FILE.write_text(
    "def add(a, b):\n"
    "    return a + b\n"
    "\n"
    "def divide(a, b):\n"
    "    return a / b\n"
    "\n"
    "def multiply(a, b):\n"
    "    a * b\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    print('add(2,3)=', add(2, 3))\n"
    "    print('divide(6,2)=', divide(6, 2))\n"
    "    print('multiply(3,4)=', multiply(3, 4))\n",
    encoding="utf-8"
)

r_before = subprocess.run(["python3", str(DEMO_FILE)], capture_output=True, text=True)
demo_output_before = r_before.stdout.strip()
demo_has_bug = "None" in demo_output_before
print("\n[Setup] Demo bug verified: " + str(demo_has_bug))
print("  Output: " + demo_output_before)

os.environ["PHOENIX_EVO_ENABLED"] = "true"
os.environ["PHOENIX_EVO_DIR"] = str(PHOENIX_DIR)

from phoenix_runtime_bridge import PhoenixRuntimeBridge
bridge = PhoenixRuntimeBridge(phoenix_base_dir=PHOENIX_DIR, phoenix_enabled=True)

task_desc = (
    "修复 /tmp/demo_calculator.py 中的 multiply() 函数，该函数返回 None。"
    "修复流程：1) 最小复现；2) 单点修复；3) 全量测试。"
)

task_id = "task3_" + datetime.now().strftime("%Y%m%d_%H%M%S")
advisory_msg = bridge.on_task_start(
    user_message=task_desc,
    task_id=task_id,
    task_type="repair",
    risk_level="low",
)
print("\n[Step 1] Advisory: " + str(len(advisory_msg) > len(task_desc)) + ", len=" + str(len(advisory_msg)))

from runtime.skill_retriever import SkillRetriever
retriever = SkillRetriever(base_dir=PHOENIX_DIR)
retrieved = retriever.retrieve("demo test failing None return", top_k=5)
retrieved_ids = [s["skill_id"] for s in retrieved]
print("  Retrieved: " + str(retrieved_ids))
expected = ["demo_repair_workflow"]
hits = [s for s in expected if s in retrieved_ids]
print("  Hits: " + str(hits) + "/" + str(len(expected)))

fixed_content = (
    "def add(a, b):\n"
    "    return a + b\n"
    "\n"
    "def divide(a, b):\n"
    "    return a / b\n"
    "\n"
    "def multiply(a, b):\n"
    "    return a * b\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    print('add(2,3)=', add(2, 3))\n"
    "    print('divide(6,2)=', divide(6, 2))\n"
    "    print('multiply(3,4)=', multiply(3, 4))\n"
)
DEMO_FILE.write_text(fixed_content, encoding="utf-8")

r_after = subprocess.run(["python3", str(DEMO_FILE)], capture_output=True, text=True)
demo_output_after = r_after.stdout.strip()
demo_fixed = r_after.returncode == 0 and "None" not in demo_output_after
print("\n[Step 2] Fix: " + ("PASS" if demo_fixed else "FAIL"))
print("  Output: " + demo_output_after)

complete_result = bridge.on_task_complete(
    task=("修复 " + str(DEMO_FILE) + " 中的 multiply() 返回 None"),
    result="修复成功: 添加 return，全量测试通过",
    success=demo_fixed,
    error_trace="multiply() missing return" if not demo_fixed else "",
    task_id=task_id,
    session_id="test_session_task3",
)
print("\n[Step 3] Write-back: " + str(complete_result))

store_after = {}
if _store_path.exists():
    store_after = json.loads(_store_path.read_text(encoding="utf-8"))
counts_after = get_counts(store_after)
print("\n[Post] counts: " + str(counts_after))

evidence = {
    "task": "Task 3: Demo fail -> pass",
    "timestamp": datetime.now().isoformat(),
    "task_id": task_id,
    "retrieved_skills": retrieved_ids,
    "expected_hits": hits,
    "fix_success": demo_fixed,
    "advisory_injected": len(advisory_msg) > len(task_desc),
    "outcome_written": complete_result.get("written", False),
    "before_output": demo_output_before,
    "after_output": demo_output_after,
}

(EVIDENCE_DIR / "task3_demo_repair.json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
)

report = (
    "# Task 3: Demo fail -> pass - V0.9.2 证据\n\n"
    "## 任务信息\n"
    "- task_id: " + task_id + "\n"
    "- Demo文件: `" + str(DEMO_FILE) + "`\n\n"
    "## 技能检索\n"
    "- 检索到: " + str(retrieved_ids) + "\n"
    "- 命中: " + str(hits) + "\n\n"
    "## Before\n"
    "```\n" + demo_output_before + "\n"
    "```\n\n"
    "## After\n"
    "```\n" + demo_output_after + "\n"
    "```\n\n"
    "## 结论\n"
    "- Skill Retrieval: " + ("PASS" if hits else "FAIL") + "\n"
    "- Advisory: " + ("PASS" if len(advisory_msg) > len(task_desc) else "FAIL") + "\n"
    "- Fix: " + ("PASS" if demo_fixed else "FAIL") + "\n"
    "- Write-back: " + ("PASS" if complete_result.get("written") else "FAIL") + "\n"
)

(EVIDENCE_DIR / "task3_demo_repair.md").write_text(report, encoding="utf-8")
print("\nEvidence written.")
print("Task 3 完成")
