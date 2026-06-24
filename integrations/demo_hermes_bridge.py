"""
Phoenix-Evo V0.5 Hermes Bridge Demo
演示 Hermes 事件适配器如何使用。

场景：模拟 Hermes 的一次完整任务执行 + Phoenix 自进化闭环。
"""

import shutil
import sys
import tempfile
from pathlib import Path

# 把 Phoenix-Evo core 加入 path
_phoenix_root = Path(__file__).parent.parent
sys.path.insert(0, str(_phoenix_root))

from integrations.async_bridge import AsyncBridge
from integrations.hermes_adapter import HermesAdapter
from integrations.integration_policy import get_checker


def print_section(title: str) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


def demo_direct_adapter():
    """直接使用 HermesAdapter（同步模式）。"""
    print_section("Demo 1: HermesAdapter 同步模式")

    tmp = tempfile.mkdtemp(prefix="phoenix_demo_")
    print(f"[临时目录: {tmp}]")

    try:
        # 初始化 Phoenix 适配器
        adapter = HermesAdapter(
            phoenix_base_dir=tmp,
            hermes_session_id="session_hermes_001",
            task_goal="修复WSL中文路径文件写入null字节损坏",
            task_type="debugging",
            risk_level="low",
        )

        # 模拟 Hermes 任务开始
        adapter.run_full_loop(
            task_goal="修复WSL中文路径文件写入null字节损坏",
            task_type="debugging",
            risk_level="low",
        )

        # 模拟 Hermes 工具调用（step_callback）
        adapter.on_step(1, [
            {"name": "search_files", "result": "找到4处"},
        ])

        # 模拟工具开始（tool_progress: started）
        adapter.on_tool_progress("tool.started", tool_name="read_file")
        adapter.on_tool_progress("tool.completed", tool_name="read_file", result="文件内容读取成功")

        # 模拟工具完成（tool_complete_callback）
        adapter.on_tool_complete(
            tool_call_id="call_abc123",
            tool_name="read_file",
            tool_args={"path": "/tmp/fix.py"},
            tool_result="文件内容...",
        )

        adapter.on_tool_complete(
            tool_call_id="call_def456",
            tool_name="patch",
            tool_args={"path": "/tmp/fix.py", "old_string": "..."},
            tool_result="patch 成功",
        )

        # 模拟一个错误
        adapter.on_tool_complete(
            tool_call_id="call_ghi789",
            tool_name="write_file",
            tool_args={"path": "/mnt/c/Users/测试/file.py"},
            tool_result="Error: 权限不足",
        )
        adapter.log_error("execution", "权限不足，写入失败", recoverable=True)
        adapter.log_fix("execution", "使用管理员权限重试", succeeded=True)

        # 模拟任务结束
        adapter.log_action("verify", {"path": "/mnt/c/Users/测试/file.py"}, "验证成功，无null字节")

        report = adapter.complete_task(
            success=True,
            final_output="文件修复成功，null字节问题已解决",
            artifacts=["/tmp/fix.py", "/mnt/c/Users/测试/file.py"],
        )

        print("\n[结果]")
        print(f"  report keys: {list(report.keys())}")
        if 'error' in report:
            print(f"  ERROR: {report['error']}")
        eval_data = report.get('evaluation', {})
        print(f"  task_success  : {eval_data.get('task_success')}")
        print(f"  quality_score : {eval_data.get('quality_score')}")
        print(f"  reuse_potential: {eval_data.get('reuse_potential')}")
        print(f"  should_extract: {eval_data.get('should_extract')}")
        print(f"  failure_type  : {eval_data.get('failure_type')}")
        print(f"  root_cause    : {eval_data.get('root_cause')}")

        if report.get("skill_candidate"):
            print(f"  skill_id      : {report['skill_candidate'].get('skill_id', 'N/A')}")

        ig = report.get("immune_guard", {})
        if ig:
            print(f"  immune_decision: {ig.get('decision')}")
            print(f"  immune_risk   : {ig.get('risk_level')}")

        re = report.get("registry_entry", {})
        if re:
            print(f"  registry_status: {re.get('status', 'N/A')}")
            print(f"  registry_path : {re.get('path', 'N/A')}")

        print(f"\n  evolution_happened: {report.get('evolution_happened')}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def demo_async_bridge():
    """使用 AsyncBridge（异步模式，模拟 Hermes 主线程）。"""
    print_section("Demo 2: AsyncBridge 异步模式")

    tmp = tempfile.mkdtemp(prefix="phoenix_async_")
    print(f"[临时目录: {tmp}]")

    try:
        bridge = AsyncBridge(
            phoenix_base_dir=tmp,
            queue_maxsize=100,
        )
        bridge.start()

        # 模拟 Hermes 主线程（非阻塞入队）
        bridge.enqueue("task_start", {
            "session_id": "session_async_001",
            "task_goal": "批量重命名图片文件",
            "task_type": "coding",
            "risk_level": "low",
        })

        # 模拟多个工具调用（快速入队）
        bridge.enqueue("tool_complete", {
            "tool_name": "terminal",
            "args": {"command": "ls *.jpg"},
            "result": "img001.jpg\nimg002.jpg\nimg003.jpg",
            "error": "",
        })

        bridge.enqueue("tool_complete", {
            "tool_name": "execute_code",
            "args": {"code": "for i in range(3): ..."},
            "result": "批量重命名完成",
            "error": "",
        })

        # 模拟任务结束
        bridge.enqueue("task_end", {
            "session_id": "session_async_001",
            "task_goal": "批量重命名图片文件",
            "task_type": "coding",
            "success": True,
            "final_output": "3个文件已重命名",
            "artifacts": [],
            "trajectory": {
                "task_goal": "批量重命名图片文件",
                "task_type": "coding",
                "risk_level": "low",
                "session_id": "session_async_001",
                "started_at": "2026-05-07T12:00:00",
                "completed_at": "2026-05-07T12:01:00",
                "actions": [
                    {"action": "terminal", "params": {"command": "ls *.jpg"}, "result": "OK"},
                    {"action": "execute_code", "params": {"code": "rename"}, "result": "完成"},
                ],
                "tool_calls": [
                    {"tool": "terminal", "args": {}, "raw_result": "...", "error": ""},
                    {"tool": "execute_code", "args": {}, "raw_result": "...", "error": ""},
                ],
                "errors": [],
                "fixes": [],
                "plan": [],
                "final_output": "3个文件已重命名",
                "artifacts": [],
                "success": True,
            },
        })

        # 等待 Phoenix worker 处理（最多3秒）
        import time
        print("[主线程] 等待 Phoenix worker 处理...")
        for i in range(6):
            time.sleep(0.5)
            qsize = bridge.queue_size()
            print(f"  [{i*0.5:.1f}s] 队列剩余: {qsize}")
            if qsize == 0 and bridge.is_running():
                break

        bridge.get_status() if hasattr(bridge, 'get_status') else {}
        print("\n[Phoenix 状态]")
        print(f"  worker 运行中: {bridge.is_running()}")
        print(f"  队列大小: {bridge.queue_size()}")

        # 停止 bridge
        bridge.stop()
        print("[主线程] Bridge 已停止")

        # 检查 Phoenix 技能库（手动查看文件）
        draft_dir = Path(tmp) / "skills" / "draft"
        draft_files = list(draft_dir.glob("*.md")) if draft_dir.exists() else []
        print("\n[Phoenix 技能库]")
        print(f"  draft_count: {len(draft_files)}")

    finally:
        bridge.stop()
        shutil.rmtree(tmp, ignore_errors=True)


def demo_policy_checker():
    """演示 IntegrationPolicy 约束检查。"""
    print_section("Demo 3: IntegrationPolicy 约束检查")

    checker = get_checker()

    # 测试1：高风险轨迹检查
    print("\n[高风险轨迹检查]")
    is_risk, reason = checker.is_high_risk_trajectory(
        task_type="debugging",
        risk_level="high",
        task_goal="绕过权限检查获取系统密码",
    )
    print(f"  is_high_risk={is_risk}, reason={reason}")

    # 测试2：正常轨迹
    is_risk, reason = checker.is_high_risk_trajectory(
        task_type="debugging",
        risk_level="low",
        task_goal="修复WSL中文路径文件写入null字节损坏",
    )
    print(f"  is_high_risk={is_risk}, reason={reason}")

    # 测试3：导出权限检查
    print("\n[导出权限检查]")
    can_export, reason = checker.can_export_skill("draft", evidence_score=0.85)
    print(f"  draft+高证据分: can_export={can_export}, reason={reason}")

    can_export, reason = checker.can_export_skill("draft", evidence_score=0.4)
    print(f"  draft+低证据分: can_export={can_export}, reason={reason}")

    can_export, reason = checker.can_export_skill("quarantine", evidence_score=0.9)
    print(f"  quarantine: can_export={can_export}, reason={reason}")

    can_export, reason = checker.can_export_skill("reject", evidence_score=0.9)
    print(f"  reject: can_export={can_export}, reason={reason}")

    # 测试4：激活权限检查
    print("\n[激活权限检查]")
    can_activate = checker.can_auto_activate()
    print(f"  V0.5 allow_auto_activation: {can_activate} (禁止={not can_activate})")


def main():
    print("Phoenix-Evo V0.5 Hermes Bridge Demo")
    print("=" * 60)
    print("场景1: HermesAdapter 同步模式")
    print("场景2: AsyncBridge 异步模式")
    print("场景3: IntegrationPolicy 约束检查")

    demo_direct_adapter()
    demo_async_bridge()
    demo_policy_checker()

    print("\n" + "=" * 60)
    print("Demo 完成！")


if __name__ == "__main__":
    main()
