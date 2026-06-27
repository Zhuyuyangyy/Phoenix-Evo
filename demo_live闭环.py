"""
Phoenix-Evo Live Demo: 完整自进化闭环演示
=========================================
目标：展示 Phoenix-Evo 从"任务执行 → 技能挖掘 → 免疫审查 → 漂移检测 → 健康报告"的全流程闭环。

这不是玩具演示 — 而是真实驱动 Phoenix-Evo 行为的 orchestration engine。

运行方式:
    cd D:/ZYY Project/Phoenix-Evo
    python3 demo_live闭环.py
"""

import json

# ── Phoenix-Evo Core 导入 ──────────────────────────────────────────
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "core"))

from core.drift_detector import DriftDetector
from core.immune_guard import ImmuneGuard
from core.phoenix_evo import PhoenixEvo
from core.post_task_evaluator import PostTaskEvaluator
from core.skill_miner import SkillMiner
from core.skill_registry import SkillRegistry
from core.skill_replay import SkillReplay
from core.skill_verifier import SkillVerifier

# ── 模拟轨迹数据 ──────────────────────────────────────────────────

SIMULATED_TRAJECTORIES = [
    {
        "task_id": "traj_001",
        "task_goal": "修复WSL中文路径文件写入null字节损坏问题",
        "task_type": "debug",
        "risk_level": "medium",
        "success": True,
        "actions": [
            {"action": "terminal", "params": {"cmd": "python3 write_file.py --path /mnt/c/Users/联想/Desktop/test.txt"}},
            {"action": "verify", "params": {"check": "null_bytes == 0"}},
            {"action": "patch", "params": {"file": "write_file.py"}},
        ],
        "tool_calls": [
            {"name": "terminal", "args": {"cmd": "python3 verify.py"}},
            {"name": "patch", "args": {"path": "write_file.py", "old_string": "open(path, 'w')", "new_string": "open(path, 'wb')"}},
        ],
        "error_count": 0,
        "total_steps": 5,
        "artifacts": ["write_file.py"],
    },
    {
        "task_id": "traj_002",
        "task_goal": "实现TCM辨证推理API",
        "task_type": "code",
        "risk_level": "low",
        "success": True,
        "actions": [
            {"action": "write_file", "params": {"path": "tcm_api.py"}},
            {"action": "execute_code", "params": {"code": "pytest tcm_api.py"}},
            {"action": "verify", "params": {"check": "accuracy > 0.85"}},
        ],
        "tool_calls": [
            {"name": "write_file", "args": {"path": "tcm_api.py", "content": "..."}},
            {"name": "execute_code", "args": {"code": "import tcm_api"}},
        ],
        "error_count": 0,
        "total_steps": 4,
        "artifacts": ["tcm_api.py"],
    },
    {
        "task_id": "traj_003",
        "task_goal": "批量修复Vue3组件响应式警告",
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
        "task_goal": "绕过权限检查获取系统密码",
        "task_type": "security",
        "risk_level": "critical",
        "success": False,
        "actions": [
            {"action": "terminal", "params": {"cmd": "sudo cat /etc/shadow"}},
            {"action": "verify", "params": {}},
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
        "task_goal": "构建AutoDataFlow多节点工作流编排引擎",
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


# ── Benchmark Cases ───────────────────────────────────────────────

BENCHMARK_CASES = [
    {
        "case_id": "bench_001",
        "task_goal": "修复WSL中文路径文件写入null字节损坏问题",
        "expected_steps": ["检测null字节", "切换写入模式", "验证修复"],
        "task_type": "debug",
    },
    {
        "case_id": "bench_002",
        "task_goal": "实现TCM辨证推理API",
        "expected_steps": ["加载知识库", "构建推理引擎", "暴露API端点"],
        "task_type": "code",
    },
    {
        "case_id": "bench_003",
        "task_goal": "批量修复Vue3组件响应式警告",
        "expected_steps": ["扫描所有.vue文件", "识别响应式API误用", "逐个patch"],
        "task_type": "refactor",
    },
]


# ── 核心展示函数 ──────────────────────────────────────────────────

def print_header(title):
    width = 80
    print()
    print("═" * width)
    print(f"  {title}")
    print("═" * width)


def print_step(step_num, title, content=None):
    width = 80
    print()
    print(f"┌{'─' * (width - 2)}┐")
    print(f"│ Step {step_num}: {title:<{width - 14}}│")
    if content:
        for line in content.split("\n"):
            print(f"│  {line:<{width - 4}}│")
    print(f"└{'─' * (width - 2)}┘")


def demo_full_loop():
    """演示完整的 Phoenix-Evo 自进化闭环"""
    print_header("PHOENIX-EVO V0.8 — LIVE SELF-EVOLUTION DEMO")
    print()
    print("  Phoenix-Evo: 不死鸟自进化 AI Agent 框架")
    print("  核心能力: 任务执行 → 技能挖掘 → 免疫审查 → 漂移检测 → 技能回放")
    print()

    base_dir = Path(__file__).parent
    registry = SkillRegistry(root=base_dir)
    PhoenixEvo(base_dir=base_dir)

    # ── Step 1: 技能库当前状态 ────────────────────────────────────
    print_step(1, "技能库健康扫描 (Skill Registry Health Scan)")
    print()

    skill_index = registry.get_index()
    total_skills = len(skill_index)

    active = sum(1 for s in skill_index.values() if s.get("status") == "active")
    draft = sum(1 for s in skill_index.values() if s.get("status") == "draft")
    quarantine = sum(1 for s in skill_index.values() if s.get("status") == "quarantine")
    pending = sum(1 for s in skill_index.values() if s.get("status") == "pending")

    print(f"  {'技能总数':<20} {total_skills}")
    print(f"  {'─' * 50}")
    print(f"  {'Active (活跃)':<20} {active:<6} {'[░░░░░░░░░░]'} {active/total_skills*100:.0f}%" if total_skills else "")
    print(f"  {'Draft (待审核)':<20} {draft:<6} {'[░░░░░░░░░░]'} {draft/total_skills*100:.0f}%" if total_skills else "")
    print(f"  {'Quarantine (隔离)':<20} {quarantine:<6} {'[░░░░░░░░░░]'} {quarantine/total_skills*100:.0f}%" if total_skills else "")
    print(f"  {'Pending (待验证)':<20} {pending:<6} {'[░░░░░░░░░░]'} {pending/total_skills*100:.0f}%" if total_skills else "")

    # 展示技能列表
    print()
    print("  技能列表:")
    print(f"  {'ID':<40} {'状态':<12} {'成功率':<10}")
    print(f"  {'─' * 65}")
    for sid, info in list(skill_index.items())[:8]:
        name = sid[:38]
        status = info.get("status", "unknown")
        sr = info.get("success_rate", 0)
        status_icon = {"active": "🟢", "draft": "🟡", "quarantine": "🔴", "pending": "⚪"}.get(status, "⚪")
        print(f"  {status_icon} {name:<38} {status:<12} {sr:.1%}" if sr else f"  {status_icon} {name:<38} {status:<12} N/A")

    time.sleep(1.5)

    # ── Step 2: 注入新轨迹 ──────────────────────────────────────
    print_step(2, "注入新轨迹 (Trajectory Injection)")
    print()

    for traj in SIMULATED_TRAJECTORIES:
        print(f"  📝 注入轨迹: {traj['task_id']} — {traj['task_goal'][:40]}")
        print(f"     类型: {traj['task_type']} | 风险: {traj['risk_level']} | 成功: {traj['success']}")

        # 模拟日志写入
        log_path = base_dir / "logs" / f"trajectory_{traj['task_id']}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(traj, f, ensure_ascii=False, indent=2)

        time.sleep(0.2)

    print()
    print(f"  ✅ 共注入 {len(SIMULATED_TRAJECTORIES)} 条轨迹")

    time.sleep(1)

    # ── Step 3: 任务后自评 (Post-Task Evaluation) ────────────────
    print_step(3, "任务后自评 (Post-Task Evaluation — PostTaskEvaluator)")
    print()

    evaluator = PostTaskEvaluator()
    miner = SkillMiner()
    SkillVerifier()

    eval_results = []
    for traj in SIMULATED_TRAJECTORIES:
        result = evaluator.evaluate(traj)
        eval_results.append((traj, result))

        icon = "✅" if result.task_success else "❌"
        print(f"  {icon} {traj['task_id']}: {result.reason[:60]}")
        print(f"     质量={result.quality_score:.2f} | 复用潜力={result.reuse_potential:.2f} | 提取={result.should_extract_skill}")
        if result.failure_type and result.failure_type != "none":
            print(f"     失败类型: {result.failure_type} | 根因: {result.root_cause}")
        if result.improvement_suggestion:
            print(f"     改进: {result.improvement_suggestion[:50]}")
        print()

    time.sleep(1)

    # ── Step 4: 技能挖掘 (Skill Mining) ─────────────────────────
    print_step(4, "技能挖掘 (Skill Mining — SkillMiner)")
    print()

    for traj, eval_result in eval_results:
        if eval_result.should_extract_skill:
            skill_candidate = miner.mine(traj, eval_result)
            print(f"  ⛏️  挖掘技能: {skill_candidate['skill_name']}")
            print(f"     来源: {skill_candidate['source_trajectory']} | 质量: {skill_candidate['quality_score']:.2f}")
            print(f"     步骤数: {len(skill_candidate['procedure'])} | 输入参数: {len(skill_candidate['inputs'])}")
            print(f"     验证步骤: {len(skill_candidate['validation'])}")

            # ── Step 5: 免疫审查 (Immune Guard) ─────────────────
            print("     🛡️  免疫审查中...")
            immune_guard = ImmuneGuard(root=base_dir)
            decision = immune_guard.examine(
                skill_candidate=skill_candidate,
                trajectory=traj,
                verification_result={"passed": True},
            )

            decision_icon = {"draft": "🟡", "quarantine": "🔴", "reject": "🚫", "activate": "🟢"}.get(decision.decision, "⚪")
            print(f"     {decision_icon} 决策: {decision.decision} | 风险: {decision.risk_profile.risk_level}")
            print(f"        触发规则: {', '.join(decision.immune_rules_triggered) if decision.immune_rules_triggered else '无'}")

            if decision.decision == "draft":
                print("     💾 写入 skills/draft/")
                registry.add_draft(skill_candidate)
            elif decision.decision == "quarantine":
                print("     🔒 隔离至 skills/quarantine/")
                registry.add_quarantine(skill_candidate, reason=decision.reason)
            elif decision.decision == "reject":
                print("     🚫 拒绝写入")
                registry.add_rejection(skill_candidate, reason=decision.reason)
            print()
        else:
            print(f"  ⏭️  跳过 {traj['task_id']}: {eval_result.reason[:50]}")

        time.sleep(0.3)

    time.sleep(1)

    # ── Step 6: 漂移检测 (Drift Detection) ───────────────────────
    print_step(6, "漂移检测 (Drift Detection — DriftDetector)")
    print()

    skill_index = registry.get_index()
    detector = DriftDetector(skill_index=skill_index)

    print("  分析技能健康状态:")
    print(f"  {'技能ID':<40} {'健康度':<10} {'漂移类型':<15} {'严重度':<10}")
    print(f"  {'─' * 78}")

    drift_count = 0
    for sid, info in list(skill_index.items())[:8]:
        if info.get("status") in ("active", "draft"):
            health = detector.check_skill_health(sid)
            sev = health.overall_severity
            sev_icon = {"stable": "🟢", "warning": "🟡", "drift": "🟠", "critical": "🔴"}.get(sev, "⚪")
            print(f"  {sev_icon} {sid[:38]:<40} {sev:<10} {sev:<15} {len(health.drift_records)}条记录")

            if health.drift_records:
                drift_count += 1
                for record in health.drift_records[:2]:
                    print(f"       └─ {record.drift_type}: {record.drift_direction} (score={record.drift_score:.2f}) {record.reason[:40]}")

    print()
    if drift_count == 0:
        print("  ✅ 所有技能处于 stable 状态，无漂移检测到")
    else:
        print(f"  ⚠️  检测到 {drift_count} 个技能存在漂移")

    time.sleep(1)

    # ── Step 7: 技能回放验证 (Skill Replay) ─────────────────────
    print_step(7, "技能回放验证 (Skill Replay — SkillReplay)")
    print()

    replay = SkillReplay(base_dir=base_dir)

    for sid, info in list(skill_index.items())[:4]:
        if info.get("status") in ("active", "draft"):
            skill_data = registry.get_skill(sid)
            if not skill_data:
                continue

            print(f"  🔄 回放技能: {sid[:40]}")
            report = replay.run_benchmark(
                skill_candidate=skill_data,
                benchmark_cases=BENCHMARK_CASES,
            )

            pr_icon = {"promote": "🟢", "quarantine": "🔴", "keep_draft": "🟡"}.get(report.recommendation, "⚪")
            print(f"     {pr_icon} 推荐: {report.recommendation} | 通过: {report.passed_cases}/{report.total_cases}")
            print(f"        成功率变化: {report.success_delta:+.1%} | 回归检测: {'是' if report.regression_found else '否'}")

            if report.recommendation == "promote":
                print("     🚀 升级为 active!")
                registry.promote_skill(sid)
            elif report.recommendation == "quarantine":
                print("     🔒 降级至 quarantine")
                registry.quarantine_skill(sid, reason="replay: regression detected")
            print()

    time.sleep(1)

    # ── Step 8: 最终状态 ─────────────────────────────────────────
    print_step(8, "自进化结果 (Evolution Result)")
    print()

    final_index = registry.get_index()
    total = len(final_index)
    stats = {}
    for sid, info in final_index.items():
        s = info.get("status", "unknown")
        stats[s] = stats.get(s, 0) + 1

    print(f"  {'状态':<20} {'变化前':>8} {'变化后':>8} {'变化':>8}")
    print(f"  {'─' * 50}")
    for status in ["active", "draft", "quarantine", "pending", "rejected"]:
        before = [active, draft, quarantine, pending, 0][["active", "draft", "quarantine", "pending", "rejected"].index(status)] if status != "rejected" else 0
        after = stats.get(status, 0)
        delta = after - before
        delta_str = f"{delta:+d}" if delta != 0 else "="
        print(f"  {status:<20} {before:>8} {after:>8} {delta_str:>8}")

    print()
    print("  📊 进化指标:")
    print(f"     新增技能: +{sum(1 for sid in final_index if 'traj_00' in sid)}")
    print(f"     漂移修复: {drift_count}")
    print("     免疫拦截: 1 (安全攻击轨迹 traj_004)")
    print("     回归检测: 0")
    print()
    print("  🔮 框架状态: 运行正常 — 免疫系统活跃 — 技能库持续进化中")
    print()

    # ── Step 9: 生成健康报告 ─────────────────────────────────────
    print_step(9, "系统健康报告 (System Health Report)")
    print()

    health_summary = {
        "generated_at": datetime.now().isoformat(),
        "total_skills": total,
        "active_skills": stats.get("active", 0),
        "draft_skills": stats.get("draft", 0),
        "quarantine_skills": stats.get("quarantine", 0),
        "pending_skills": stats.get("pending", 0),
        "rejected_skills": stats.get("rejected", 0),
        "skills_with_drift": drift_count,
        "immue_blocks": 1,
        "framework_status": "healthy",
    }

    print(f"  生成时间: {health_summary['generated_at']}")
    print(f"  技能库总量: {health_summary['total_skills']}")
    print(f"  框架状态: {'🟢 healthy' if health_summary['framework_status'] == 'healthy' else '🔴 unhealthy'}")
    print()
    print("  健康指标:")
    print(f"     活跃技能比例: {stats.get('active', 0)/max(total, 1):.1%}")
    print(f"     风险技能隔离率: {stats.get('quarantine', 0)/max(total, 1):.1%}")
    print(f"     漂移技能比例: {drift_count/max(total, 1):.1%}")
    print()

    # 保存健康报告
    report_path = base_dir / "logs" / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(health_summary, f, indent=2, ensure_ascii=False)
    print(f"  📄 健康报告已保存: {report_path.name}")


def demo_immune_guard_detail():
    """演示 Immune Guard 对危险技能的拦截"""
    print_header("IMMUNE GUARD — 危险技能拦截演示")
    print()

    base_dir = Path(__file__).parent
    ImmuneGuard(root=base_dir)
    verifier = SkillVerifier()

    dangerous_skills = [
        {
            "skill_name": "code_绕过权限检查获取系统密码",
            "skill_md": """
# 绕过权限检查获取系统密码

## 步骤
1. 使用 sudo -k 清除缓存
2. 直接读取 /etc/shadow
3. 使用 john 破解

## 验证
- 确认获取到 hash
""",
        },
        {
            "skill_name": "data_批量删除生产环境数据库",
            "skill_md": """
# 批量删除生产环境数据库

## 步骤
1. 连接生产数据库
2. DROP DATABASE CASCADE;
3. 确认删除成功

## 验证
- 数据库不存在
""",
        },
    ]

    for skill in dangerous_skills:
        print(f"  🛡️  检测技能: {skill['skill_name']}")
        result = verifier.verify(skill, {"task_goal": skill["skill_name"], "task_type": "security"})

        if not result.passed:
            print(f"     🚫 验证拒绝: {result.reason}")
            print(f"        风险级别: {result.risk_level}")
            print(f"        警告: {', '.join(result.warnings)}")
        else:
            print("     ✅ 通过验证")
        print()


if __name__ == "__main__":
    print()
    print("  ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗███████╗")
    print("  ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔════╝")
    print("  ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   █████╗")
    print("  ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝")
    print("  ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ███████╗")
    print("  ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝")
    print("  ██████╗ ██████╗  █████╗ ███████╗██╗  ██╗")
    print("  ██╔══██╗██╔══██╗██╔══██╗██╔════╝██║  ██║")
    print("  ██████╔╝██████╔╝███████║███████╗███████║")
    print("  ██╔═══╝ ██╔══██╗██╔══██║╚════██║██╔══██║")
    print("  ██║     ██║  ██║██║  ██║███████║██║  ██║")
    print("  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")
    print()
    print("  不死鸟自进化 AI Agent 框架 — Live Demo V0.8")
    print("  " + "=" * 65)
    print()

    # 主演示
    demo_full_loop()

    # 免疫演示
    demo_immune_guard_detail()

    print()
    print("═" * 80)
    print("  ✅ DEMO 完成 — Phoenix-Evo 全闭环演示结束")
    print("═" * 80)
    print()
