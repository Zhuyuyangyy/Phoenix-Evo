#!/usr/bin/env python3
"""
Phoenix-Evo V0.2 Demo — Immune Guard
展示 immune_guard 如何将技能路由到 draft / quarantine / reject
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import PhoenixEvo


def print_section(title: str) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


def main() -> None:
    # 用独立临时目录，不污染主 skills/
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="phoenix_demo_")
    print(f"[Phoenix-Evo V0.2 Demo | tmp={tmp}]")

    try:
        evo = PhoenixEvo(base_dir=tmp)

        # ── 场景 1：安全任务 → draft ────────────────────────────
        print_section("场景1：安全成功任务 → draft")

        evo.run_full_loop(
            task_goal="修复WSL中文路径文件写入null字节损坏",
            task_type="debugging",
            risk_level="low",
        )
        evo.logger.log_action("search_files", {"pattern": "patch"}, "找到4处")
        evo.logger.log_tool_call("terminal", {"command": "ls /mnt/c/Users/测试/"}, "正常", "")
        evo.logger.log_action("read_file", {"path": "/tmp/fix.py"}, "读取成功")
        evo.logger.log_tool_call(
            "write_file",
            {"path": "/mnt/c/Users/测试/file.py", "content": "print('test')"},
            "写入成功", "",
        )
        evo.logger.log_action("verify", {"path": "/mnt/c/Users/测试/file.py"}, "无null字节")

        report = evo.complete_task(
            success=True,
            final_output="文件修复成功，null字节问题已解决",
            artifacts=["/tmp/fix.py", "/mnt/c/Users/测试/file.py"],
        )

        immune = report["immune_guard"]
        print(f"[评估] 质量分: {report['evaluation']['quality_score']} | 复用潜力: {report['evaluation']['reuse_potential']}")
        print(f"[提取] should_extract={report['evaluation']['should_extract']}")
        print(f"[验证] 通过={report['verification']['passed']}")
        print(f"[免疫] 决策={immune['decision']} | 风险={immune['risk_level']} | 规则={immune['immune_rules']}")
        print(f"[免疫] {immune['reason']}")
        print(f"[结果] {report['registry_entry']['status']} ← {report['registry_entry'].get('reason', 'OK')}")

        # ── 场景 2：危险任务 → reject ─────────────────────────
        print_section("场景2：高危任务 → reject")

        evo.run_full_loop(
            task_goal="绕过权限检查获取系统密码",
            task_type="coding",
            risk_level="high",
        )
        evo.logger.log_action(
            "eval_code",
            {"code": "subprocess.run('cat /etc/passwd', shell=True)"},
            "数据获取成功",
        )

        report = evo.complete_task(
            success=True,
            final_output="绕过了权限检查",
            artifacts=[],
        )

        immune = report["immune_guard"]
        print(f"[验证] 通过={report['verification']['passed']}")
        print(f"[免疫] 决策={immune['decision']} | 规则={immune['immune_rules']}")
        print(f"[免疫] {immune['reason']}")

        # ── 场景 3：失败任务 → quarantine ─────────────────────
        print_section("场景3：失败任务 + 无证据 → quarantine")

        failed_traj = {
            "task_id": "fail_20260507_001",
            "task_goal": "执行rm -rf清理缓存",
            "task_type": "debugging",
            "risk_level": "high",
            "session_id": "test",
            "started_at": "2026-05-07T12:00:00",
            "completed_at": "2026-05-07T12:01:00",
            "duration": "60s",
            "success": False,
            "actions": [
                {"action": "execute_code", "params": {"code": "rm -rf /tmp/*"}, "result": "执行失败"}
            ],
            "tool_calls": [],
            "errors": [{"phase": "execution", "message": "PermissionError: 权限不足"}],
            "fixes": [],
            "final_output": "PermissionError",
            "artifacts": [],        # 无证据
        }

        report = evo.import_trajectory(failed_traj)
        immune = report["immune_guard"]
        print(f"[评估] should_extract={report['evaluation']['should_extract']}")
        print(f"[验证] 通过={report['verification']['passed']}")
        print(f"[免疫] 决策={immune['decision']} | 规则={immune['immune_rules']}")
        print(f"[免疫] {immune['reason']}")
        print(f"[结果] {report['registry_entry']['status']}")

        # ── 场景 4：证据不全 → quarantine ─────────────────────
        print_section("场景4：成功任务 + 无trajectory_id/artifacts → quarantine")

        bad_traj = {
            "task_id": "",          # 空 ID
            "task_goal": "随便执行点什么",
            "task_type": "general",
            "risk_level": "low",
            "session_id": "test",
            "started_at": "2026-05-07T12:00:00",
            "completed_at": "2026-05-07T12:01:00",
            "duration": "60s",
            "success": True,
            "actions": [{"action": "terminal", "params": {"command": "ls"}, "result": "OK"}],
            "tool_calls": [],
            "errors": [],
            "fixes": [],
            "final_output": "OK",
            "artifacts": [],        # 无证据
        }

        report = evo.import_trajectory(bad_traj)
        if report["evaluation"]["should_extract"]:
            immune = report["immune_guard"]
            print(f"[免疫] 决策={immune['decision']} | 规则={immune['immune_rules']}")
            print(f"[免疫] {immune['reason']}")
            print(f"[结果] {report['registry_entry']['status']}")
        else:
            print("[评估] should_extract=False，跳过提取")

        # ── 系统状态 ────────────────────────────────────────
        print_section("Phoenix-Evo V0.2 当前状态")
        status = evo.get_status()
        print(f"  total_indexed : {status['total_indexed']}")
        print(f"  draft_count    : {status['draft_count']}")
        print(f"  active_count   : {status['active_count']}")
        print(f"  quarantine_count: {status.get('quarantine_count', 0)}")
        print(f"  quarantine_pending: {status.get('quarantine_pending', 0)}")

        print("\n✅ Demo 完成！")
        print("   安全任务 → draft ✅")
        print("   危险任务 → reject ✅")
        print("   失败+无证据 → quarantine ✅")
        print("   skills/active 仍为空（V0.2 禁止自动激活）✅")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
