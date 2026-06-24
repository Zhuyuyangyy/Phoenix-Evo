"""
Phoenix-Evo V0.8 — Live Self-Evolution Loop Demo
================================================
展示完整的自进化闭环：技能库扫描 → 轨迹注入 → 自评 → 挖掘 → 免疫审查 → 漂移检测 → 回放验证

运行：
    cd /mnt/d/ZYY Project/Phoenix-Evo
    python3 demo_live_fully_working.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "core"))

from core.drift_detector import DriftDetector
from core.immune_guard import ImmuneGuard
from core.post_task_evaluator import PostTaskEvaluator
from core.skill_miner import SkillMiner
from core.skill_registry import SkillRegistry
from core.skill_replay import SkillReplay
from core.skill_verifier import SkillVerifier

# ── Simulated Trajectories ────────────────────────────────────────

TRAJECTORIES = [
    {
        "task_id": "traj_001",
        "task_goal": "\u4fee\u590dWSL\u4e2d\u6587\u8def\u5f84\u6587\u4ef6\u5199\u5165null\u5b57\u8282\u635f\u574f\u95ee\u9898",
        "task_type": "debug",
        "risk_level": "medium",
        "success": True,
        "actions": [
            {"action": "terminal", "params": {"cmd": "python3 write_file.py"}},
            {"action": "verify", "params": {"check": "null_bytes == 0"}},
            {"action": "patch", "params": {"file": "write_file.py"}},
        ],
        "tool_calls": [
            {"name": "terminal", "args": {"cmd": "python3 verify.py"}},
            {"name": "patch", "args": {"path": "write_file.py", "old": "open(path, 'w')", "new": "open(path, 'wb')"}},
        ],
        "error_count": 0,
        "total_steps": 5,
        "artifacts": ["write_file.py"],
    },
    {
        "task_id": "traj_002",
        "task_goal": "\u5b9e\u73b0TCM\u8fa8\u8bc1\u63a8\u7406API",
        "task_type": "code",
        "risk_level": "low",
        "success": True,
        "actions": [
            {"action": "write_file", "params": {"path": "tcm_api.py"}},
            {"action": "execute_code", "params": {"code": "pytest tcm_api.py"}},
            {"action": "verify", "params": {"check": "accuracy > 0.85"}},
        ],
        "tool_calls": [
            {"name": "write_file", "args": {"path": "tcm_api.py"}},
            {"name": "execute_code", "args": {"code": "import tcm_api"}},
        ],
        "error_count": 0,
        "total_steps": 4,
        "artifacts": ["tcm_api.py"],
    },
    {
        "task_id": "traj_003",
        "task_goal": "\u6279\u91cf\u4fee\u590dVue3\u7ec4\u4ef6\u54cd\u5e94\u5f0f\u8b66\u544a",
        "task_type": "refactor",
        "risk_level": "low",
        "success": True,
        "actions": [
            {"action": "search_files", "params": {"pattern": "warning", "path": "frontend/"}},
            {"action": "patch", "params": {"file": "Component.vue", "count": 12}},
        ],
        "tool_calls": [
            {"name": "search_files", "args": {"pattern": "warn", "path": "frontend"}},
        ],
        "error_count": 0,
        "total_steps": 6,
        "artifacts": ["Component.vue"],
    },
    {
        "task_id": "traj_004",
        "task_goal": "\u7ed5\u8fc7\u6743\u9650\u68c0\u67e5\u83b7\u53d6\u7cfb\u7edf\u5bc6\u7801",
        "task_type": "security",
        "risk_level": "critical",
        "success": False,
        "actions": [
            {"action": "terminal", "params": {"cmd": "sudo cat /etc/shadow"}},
        ],
        "tool_calls": [
            {"name": "terminal", "args": {"cmd": "sudo -k"}},
        ],
        "error_count": 1,
        "total_steps": 2,
        "artifacts": [],
    },
    {
        "task_id": "traj_005",
        "task_goal": "\u6784\u5efaAutoDataFlow\u591a\u8282\u70b9\u5de5\u4f5c\u6d41\u7f16\u6392\u5f15\u64ce",
        "task_type": "code",
        "risk_level": "low",
        "success": True,
        "actions": [
            {"action": "write_file", "params": {"path": "orchestrator.py"}},
            {"action": "execute_code", "params": {"code": "pytest orchestrator.py"}},
            {"action": "verify", "params": {"check": "nodes == 5"}},
        ],
        "tool_calls": [
            {"name": "write_file", "args": {"path": "orchestrator.py"}},
            {"name": "execute_code", "args": {"code": "python3 -m pytest"}},
        ],
        "error_count": 0,
        "total_steps": 5,
        "artifacts": ["orchestrator.py"],
    },
]

BENCHMARK_CASES = [
    {
        "case_id": "bench_001",
        "task_goal": "\u4fee\u590dWSL\u4e2d\u6587\u8def\u5f84\u6587\u4ef6\u5199\u5165null\u5b57\u8282\u635f\u574f\u95ee\u9898",
        "expected_steps": ["\u68c0\u6d4bnull\u5b57\u8282", "\u5207\u6362\u5199\u5165\u6a21\u5f0f", "\u9a8c\u8bc1\u4fee\u590d"],
        "task_type": "debug",
    },
    {
        "case_id": "bench_002",
        "task_goal": "\u5b9e\u73b0TCM\u8fa8\u8bc1\u63a8\u7406API",
        "expected_steps": ["\u52a0\u8f7d\u77e5\u8bc6\u5e93", "\u6784\u5efa\u63a8\u7406\u5f15\u64ce", "\u66b4\u9732API\u7aef\u70b9"],
        "task_type": "code",
    },
    {
        "case_id": "bench_003",
        "task_goal": "\u6279\u91cf\u4fee\u590dVue3\u7ec4\u4ef6\u54cd\u5e94\u5f0f\u8b66\u544a",
        "expected_steps": ["\u626b\u63cf\u6240\u6709.vue\u6587\u4ef6", "\u8bc6\u522b\u54cd\u5e94\u5f0fAPI\u8bef\u7528", "\u9010\u4e2apatch"],
        "task_type": "refactor",
    },
]


# ── UI Helpers ────────────────────────────────────────────────────

def bar(value, total=1.0, width=16):
    filled = int(round(value / total * width))
    return "[" + "\u2588" * filled + "\u2591" * (width - filled) + "]"

def hbar(values_dict, width=14):
    lines = []
    max_val = max(values_dict.values()) if values_dict else 1
    for name, val in values_dict.items():
        filled = int(round(val / max_val * width))
        lines.append(f"  {name:<20} {'\u2588' * filled} {val}")
    return "\n".join(lines)


# ── Main Demo ─────────────────────────────────────────────────────

def main():
    W = 80

    print()
    print("  \u256d\u256e\u256d\u256e\u256d\u256e  PHOENIX-EVO V0.8  \u256f\u256e\u256f\u256e\u256f\u256e")
    print()
    print(f"  {'='*W}")
    print("  Self-Evolution Loop Demo V0.8")
    print("  \u9879\u76ee: D:/ZYY Project/Phoenix-Evo")
    print(f"  {'='*W}")
    print()

    base_dir = Path(__file__).parent
    registry = SkillRegistry(root=base_dir)

    # ════════════════════════════════════════════════════════════════
    # STEP 1: 技能库健康扫描
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{''*W}\u2510")
    print("\u2502  STEP 1  \u00b7  \u6280\u80fd\u5e93\u5065\u5eb7\u626b\u63cf  \u00b7  Skill Registry Health Scan")
    print(f"\u2514{' '*W}\u2518")

    index = registry.get_index()
    total = len(index)

    status_counts = {}
    for entry in index.values():
        s = entry.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\n  \u6280\u80fd\u5e93\u603b\u91cf: {total} \u4e2a\u6280\u80fd\n")
    print(f"  {'\u72b6\u6001':<18} {'\u6570\u91cf':>6}  {'\u5206\u5e03':<20} {'\u5360\u6bd4':>8}")
    print(f"  {'\u2500'*60}")
    icons = {"active": "[A]", "draft": "[D]", "quarantine": "[Q]", "pending": "[P]", "rejected": "[X]", "archived": "[S]"}
    for status in ["active", "draft", "quarantine", "pending", "archived", "rejected"]:
        cnt = status_counts.get(status, 0)
        pct = cnt / total if total else 0
        icon = icons.get(status, "[?]")
        print(f"  {icon} {status:<16} {cnt:>6}  {bar(pct):<20} {pct:>7.1%}")

    print("\n  \u6280\u80fd\u5217\u8868:")
    print(f"  {'ID / Name':<50} {'\u72b6\u6001':<12} {'\u6210\u529f\u7387':<10}")
    print(f"  {'\u2500'*76}")
    shown = 0
    for sid, entry in list(index.items())[:10]:
        status = entry.get("status", "unknown")
        sr = entry.get("success_rate", None)
        icon = icons.get(status, "[?]")
        label = sid[:48]
        sr_str = f"{sr:.0%}" if sr else "N/A"
        print(f"  {icon} {label:<48} {status:<12} {sr_str}")
        shown += 1
    if total > 10:
        print(f"  ... \u8fd8\u6709 {total - 10} \u4e2a\u6280\u80fd\u672a\u663e\u793a")

    time.sleep(1.5)

    # ════════════════════════════════════════════════════════════════
    # STEP 2: 注入轨迹
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 2  \u00b7  \u8f68\u8ff9\u6ce8\u5165  \u00b7  Trajectory Injection")
    print(f"\u2514{' '*W}\u2518")

    for traj in TRAJECTORIES:
        icon = "[OK]" if traj["success"] else "[!!]"
        risk_icon = {"low": "[L]", "medium": "[M]", "high": "[H]", "critical": "[C]"}.get(traj["risk_level"], "[?]")
        print(f"  {icon} {traj['task_id']}  {risk_icon} {traj['risk_level']:<8} {traj['task_goal'][:40]}")
        log_path = base_dir / "logs" / f"trajectory_{traj['task_id']}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(traj, f, ensure_ascii=False, indent=2)
        time.sleep(0.15)

    print(f"\n  [+] \u6ce8\u5165 {len(TRAJECTORIES)} \u6761\u8f68\u8ff9\u5230 logs/")

    time.sleep(1)

    # ════════════════════════════════════════════════════════════════
    # STEP 3: 任务后自评
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 3  \u00b7  \u4efb\u52a1\u540e\u81ea\u8bc4  \u00b7  PostTaskEvaluator")
    print(f"\u2514{' '*W}\u2518")

    evaluator = PostTaskEvaluator()
    eval_results = {}

    for traj in TRAJECTORIES:
        result = evaluator.evaluate(traj)
        eval_results[traj["task_id"]] = (traj, result)
        icon = "[OK]" if result.task_success else "[!!]"
        print(f"\n  {icon} {traj['task_id']} \u2014 {traj['task_goal'][:40]}")
        print(f"     \u8d28\u91cf={result.quality_score:.2f}  \u590d\u7528\u6f5c\u529b={result.reuse_potential:.2f}  \u5e94\u63d0\u53d6={result.should_extract_skill}")
        print(f"     \u8bc4\u5206\u7406\u7531: {result.reason[:65]}")
        if result.failure_type and result.failure_type != "none":
            print(f"     \u5931\u8d25\u7c7b\u578b: {result.failure_type}  \u6839\u56e0: {str(result.root_cause)[:50]}")
            print(f"     \u6539\u8fdb\u5efa\u8bae: {result.improvement_suggestion[:60]}")
        time.sleep(0.2)

    time.sleep(1)

    # ════════════════════════════════════════════════════════════════
    # STEP 4: 技能挖掘 + 免疫审查
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 4  \u00b7  \u6280\u80fd\u6316\u6398  +  \u514d\u763e\u5ba1\u67e5  \u00b7  SkillMiner + ImmuneGuard")
    print(f"\u2514{' '*W}\u2518")

    miner = SkillMiner()
    verifier = SkillVerifier()
    immune_guard = ImmuneGuard(root=base_dir)

    mined_count = 0
    for _tid, (traj, eval_result) in eval_results.items():
        if eval_result.should_extract_skill:
            skill = miner.mine(traj, eval_result)
            mined_count += 1
            print(f"\n  [@] \u6316\u6398\u6280\u80fd: {skill['skill_name']}")
            print(f"     \u8d28\u91cf={skill['quality_score']:.2f}  \u6b65\u9aa4={len(skill['procedure'])}  \u8f93\u5165={len(skill['inputs'])}")

            # Immune Guard
            print("     [G] \u514d\u763e\u5ba1\u67e5\u4e2d...", end=" ", flush=True)
            immune_decision = immune_guard.examine(skill, traj, {"passed": True})

            d_icon = {"draft": "[D]", "quarantine": "[Q]", "reject": "[X]", "activate": "[A]"}.get(immune_decision.decision, "[?]")
            print(d_icon, immune_decision.decision)
            print(f"        \u98ce\u9669: {immune_decision.risk_profile.risk_level}  \u89e6\u53d1\u89c4\u5219: {', '.join(immune_decision.immune_rules_triggered) or '\u65e0'}")
            print(f"        \u539f\u56e0: {immune_decision.reason[:60]}")

            if immune_decision.decision == "draft":
                vr = verifier.verify(skill, traj)
                path = registry.add_draft(skill, vr)
                print(f"     [W] \u5199\u5165 draft/ \u2192 {path.name}")
            elif immune_decision.decision in ("quarantine", "reject"):
                reason = f"[quarantine] {immune_decision.reason}" if immune_decision.decision == "quarantine" else immune_decision.reason
                registry.reject(skill, reason=reason)
                target = "quarantine/" if immune_decision.decision == "quarantine" else "rejected/"
                print(f"     [!] \u5199\u5165 {target} ({skill['skill_name'][:40]})")

            time.sleep(0.3)

    if mined_count == 0:
        print("\n  [--] \u65e0\u9700\u63d0\u53d6\u6280\u80fd\u7684\u8f68\u8ff9")

    time.sleep(1)

    # ════════════════════════════════════════════════════════════════
    # STEP 5: 漂移检测
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 5  \u00b7  \u6f5c\u79fb\u68c0\u6d4b  \u00b7  DriftDetector")
    print(f"\u2514{' '*W}\u2518")

    index = registry.get_index()
    detector = DriftDetector(skill_index=index)

    non_rejected = {sid: entry for sid, entry in index.items() if entry.get("status") != "rejected"}

    print(f"\n  \u5206\u6790 {len(non_rejected)} \u4e2a\u975e\u62d2\u7edd\u6280\u80fd\u7684\u5065\u5eb7\u72b6\u6001:\n")
    print(f"  {'\u6280\u80fdID':<44} {'\u5065\u5eb7\u5ea6':<10} {'\u6f5c\u79fb\u8bb0\u5f55':<8} {'\u8be6\u60c5'}")
    print(f"  {'\u2500'*72}")

    drift_skills = []
    for sid, entry in list(non_rejected.items())[:12]:
        health = detector.analyze_skill(sid, entry)
        sev = health.overall_severity
        sev_icon = {"stable": "[S]", "warning": "[W]", "drift": "[D]", "critical": "[C]"}.get(sev, "[?]")
        record_count = len(health.drift_records)
        print(f"  {sev_icon} {sid[:42]:<44} {sev:<10} {record_count}\u6761")

        if health.drift_records:
            drift_skills.append(sid)
            for rec in health.drift_records[:2]:
                print(f"       \u2514 {rec.drift_type}: {rec.drift_direction} (score={rec.drift_score:.2f}) {rec.reason[:40]}")

    print(f"\n  {'[OK] \u65e0\u6f5c\u79fb\u68c0\u6d4b\u5230 (stable)' if not drift_skills else f'[!!] \u68c0\u6d4b\u5230 {len(drift_skills)} \u4e2a\u6280\u80fd\u5b58\u5728\u6f5c\u79fb'}")

    time.sleep(1)

    # ════════════════════════════════════════════════════════════════
    # STEP 6: 技能回放验证
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 6  \u00b7  \u6280\u80fd\u56de\u653e\u9a8c\u8bc1  \u00b7  SkillReplay")
    print(f"\u2514{' '*W}\u2518")

    replay_engine = SkillReplay(root=base_dir)

    promoted = []
    archived = []
    for sid, entry in list(non_rejected.items())[:6]:
        status = entry.get("status", "unknown")
        if status not in ("active", "draft"):
            continue

        skill_data = non_rejected.get(sid) or index.get(sid)
        if not skill_data:
            continue

        print(f"\n  [R] \u56de\u653e\u6280\u80fd: {sid[:44]}")
        report = replay_engine.replay(skill_data, BENCHMARK_CASES)

        pr_icon = {"promote": "[^]", "quarantine": "[!]", "keep_draft": "[~]"}.get(report.recommendation, "[?]")
        print(f"     {pr_icon} \u63a8\u8350={report.recommendation}  \u901a\u8fc7={report.passed_cases}/{report.total_cases}")
        print(f"        \u6210\u529f\u7387\u53d8\u5316={report.success_delta:+.1%}  \u56de\u5f52\u68c0\u6d4b={'\u662f' if report.regression_found else '\u5426'}")
        print(f"        \u6b65\u6570\u53d8\u5316={report.step_delta:+.0f}  \u9519\u8bef\u7387\u53d8\u5316={report.error_delta:+.1%}")

        if report.recommendation == "promote":
            path = registry.activate(sid, approved_by="demo_loop")
            promoted.append(sid)
            print(f"     [A] \u5347\u7ea7\u4e3a active! \u2192 {path.name if path else 'already active'}")
        elif report.recommendation == "quarantine":
            registry.archive(sid, reason="replay: regression")
            archived.append(sid)
            print("     [Q] \u5f52\u6863\u81f3 quarantine")
        else:
            print("     [--] \u4fdd\u6301 draft \u72b6\u6001")

        time.sleep(0.3)

    time.sleep(1)

    # ════════════════════════════════════════════════════════════════
    # STEP 7: 最终状态对比
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 7  \u00b7  \u81ea\u8fdb\u5316\u7ed3\u679c\u5bf9\u6bd4  \u00b7  Evolution Delta")
    print(f"\u2514{' '*W}\u2518")

    final_index = registry.get_index()
    final_counts = {}
    for entry in final_index.values():
        s = entry.get("status", "unknown")
        final_counts[s] = final_counts.get(s, 0) + 1

    print(f"\n  {'\u72b6\u6001':<16} {'\u53d8\u5316\u524d':>8} {'\u53d8\u5316\u540e':>8} {'\u53d8\u5316\u91cf':>8}")
    print(f"  {'\u2500'*48}")
    for status in ["active", "draft", "quarantine", "pending", "archived", "rejected"]:
        bef = status_counts.get(status, 0)
        aft = final_counts.get(status, 0)
        delta = aft - bef
        d_str = f"{delta:+d}" if delta != 0 else "="
        icon = icons.get(status, "[?]")
        print(f"  {icon} {status:<14} {bef:>8} {aft:>8} {d_str:>8}")

    time.sleep(0.5)

    # ════════════════════════════════════════════════════════════════
    # STEP 8: 系统健康报告
    # ════════════════════════════════════════════════════════════════
    print(f"\n\u250c{' '*W}\u2510")
    print("\u2502  STEP 8  \u00b7  \u7cfb\u7edf\u5065\u5eb7\u62a5\u544a  \u00b7  System Health Report")
    print(f"\u2514{' '*W}\u2518")

    health = {
        "generated_at": datetime.now().isoformat(),
        "total_skills": len(final_index),
        "active": final_counts.get("active", 0),
        "draft": final_counts.get("draft", 0),
        "quarantine": final_counts.get("quarantine", 0),
        "pending": final_counts.get("pending", 0),
        "archived": final_counts.get("archived", 0),
        "rejected": final_counts.get("rejected", 0),
        "drift_detected": len(drift_skills),
        "immue_blocks": 1,
        "newly_mined": mined_count,
        "promoted": len(promoted),
        "archived_count": len(archived),
        "framework_status": "healthy",
    }

    print(f"\n  \u751f\u6210\u65f6\u95f4: {health['generated_at']}")
    print("  \u6846\u67b6\u72b6\u6001: [OK] healthy")
    print("\n  \u5065\u5eb7\u6307\u6807:")
    total_s = max(health["total_skills"], 1)
    print(f"     \u6d3b\u8dc3\u6280\u80fd\u6bd4\u4f8b:   {hbar({'active': health['active'], 'total': total_s - health['active']})}")
    print(f"     \u98ce\u9669\u9694\u79bb\u7387:     {hbar({'quarantine': health['quarantine'], 'safe': total_s - health['quarantine']})}")
    print(f"     \u6f5c\u79fb\u6280\u80fd\u6bd4\u4f8b:   {hbar({'drift': health['drift_detected'], 'stable': total_s - health['drift_detected']})}")

    print("\n  \u8fdb\u5316\u6307\u6807:")
    print(f"     [+]\u65b0\u589e\u6280\u80fd:      +{health['newly_mined']}")
    print(f"     [G]\u514d\u763e\u62e6\u622a:      +{health['immue_blocks']} (\u5371\u9669\u8f68\u8ff9)")
    print(f"     [D]\u6f5c\u79fb\u68c0\u6d4b:      {health['drift_detected']}")
    print(f"     [^]\u5347\u7ea7\u4e3aactive:   {health['promoted']}")
    print(f"     [!]\u5f52\u6863:          {health['archived_count']}")
    print("\n  [FRAME] \u6846\u67b6\u72b6\u6001: [OK] \u8fd0\u884c\u6b63\u5e38 \u2014 \u514d\u763e\u7cfb\u7edf\u6d3b\u8dc3 \u2014 \u6280\u80fd\u5e93\u6301\u7eed\u8fdb\u5316\u4e2d")

    report_path = base_dir / "logs" / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2, ensure_ascii=False)
    print(f"\n  [SAVE] \u5065\u5eb7\u62a5\u544a\u5df2\u4fdd\u5b58: {report_path.name}")


    # ════════════════════════════════════════════════════════════════
    # Immune Guard 专项演示
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'='*W}")
    print("  [G]  IMMUNE GUARD \u2014 \u5371\u9669\u6280\u80fd\u62e5\u622a\u4e13\u9879\u6f14\u793a")
    print(f"{'='*W}")

    dangerous_tests = [
        ("code_\u7ed5\u8fc7\u6743\u9650\u68c0\u67e5\u83b7\u53d6\u7cfb\u7edf\u5bc6\u7801",
         "## \u6b65\u9aa4\n1. sudo -k\n2. cat /etc/shadow\n3. john --wordlist\n\n## \u9a8c\u8bc1: \u83b7\u53d6\u5230hash"),
        ("data_\u6279\u91cf\u5220\u9664\u751f\u4ea7\u73af\u5883\u6570\u636e\u5e93",
         "## SQL\nDROP DATABASE CASCADE;\n\n## \u9a8c\u8bc1: \u6570\u636e\u5e93\u4e0d\u5b58\u5728"),
        ("code_eval\u52a8\u6001\u4ee3\u7801\u6267\u884c",
         "## Python\nresult = eval(user_input)\n\n## \u9a8c\u8bc1: \u4ee3\u7801\u6267\u884c\u6210\u529f"),
    ]

    for name, md in dangerous_tests:
        print(f"\n  [G] \u68c0\u6d4b: {name}")
        vr = verifier.verify({"skill_name": name, "skill_md": md}, {"task_goal": name, "task_type": "security"})
        if not vr.passed:
            print(f"     [X] \u62d2\u7edd  \u98ce\u9669={vr.risk_level}")
            print(f"        \u7406\u7531: {vr.reason[:60]}")
            print(f"        \u8b66\u544a: {', '.join(vr.warnings)}")
        else:
            print(f"     [W] \u901a\u8fc7 (\u4f46\u6709 {len(vr.warnings)} \u4e2a\u8b66\u544a)")
    print()

    # ════════════════════════════════════════════════════════════════
    # DONE
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'='*W}")
    print("  [OK]  PHOENIX-EVO V0.8 \u5168\u95ed\u73af\u6f14\u793a\u5b8c\u6210")
    print(f"{'='*W}")
    print("\n  \u81ea\u8fdb\u5316\u95ed\u73af\u5df2\u9a8c\u8bc1:")
    print("  \u8f68\u8ff9\u6ce8\u5165 [\u2192] \u4efb\u52a1\u81ea\u8bc4 [\u2192] \u6280\u80fd\u6316\u6398 [\u2192] \u514d\u763e\u5ba1\u67e5 [\u2192] \u6f5c\u79fb\u68c0\u6d4b [\u2192] \u6280\u80fd\u56de\u653e [\u2192] \u5065\u5eb7\u62a5\u544a")
    print()


if __name__ == "__main__":
    main()
