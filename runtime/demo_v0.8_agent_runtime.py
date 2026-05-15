#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phoenix-Evo V0.8 Agent Runtime Demo

测试场景：
  Demo1: 完整生命周期 — 创建→路由→注入→执行→完成
  Demo2: Hook 系统 — on_before_route / on_success / on_failure 全部触发
  Demo3: 取消机制 — cancel() 在执行前取消任务
  Demo4: 任务持久化 — TaskStore 保存+恢复
  Demo5: Feedback 集成 — 成功/失败自动汇报到 FeedbackDispatcher
  Demo6: 失败路径 — execute_fn 异常触发 on_failure hook
"""

import sys
import tempfile
import shutil
import json
from pathlib import Path

PHOENIX_BASE = Path(__file__).parent.parent
sys.path.insert(0, str(PHOENIX_BASE))

from runtime.agent_runtime import (
    AgentRuntime, TaskState, TaskContext,
    HookManager, CancellationToken, TaskStore,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Skill 环境
# ─────────────────────────────────────────────────────────────────────────────

def create_mock_skill_env(base_dir: Path):
    skills_dir = base_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_md = """# Skill: WSL路径修复

## Metadata
- **skill_id**: fix_wsl_chinese_path
- **task_type**: debugging
- **source_trajectory**: task_debug_wsl
- **status**: active
- **quality_score**: 0.85
- **evidence_score**: 0.80
- **replay_pass_rate**: 0.85
- **risk_level**: low
- **usage_count**: 10
- **success_count**: 8

## When to Use
WSL (Windows Subsystem for Linux) related issues, Chinese path problems, Null byte file corruption

## Procedure
1. Identify WSL Chinese path issue
2. Use Python script to fix null bytes
3. Verify fix with test read
"""
    (skills_dir / "fix_wsl_chinese_path.md").write_text(skill_md, encoding="utf-8")

    index = {
        "fix_wsl_chinese_path": {
            "skill_id": "fix_wsl_chinese_path",
            "skill_name": "WSL路径修复",
            "task_type": "debugging",
            "status": "active",
            "quality_score": 0.85,
            "evidence_score": 0.80,
            "replay_pass_rate": 0.85,
            "risk_level": "low",
            "usage_count": 10,
            "success_count": 8,
        }
    }
    (skills_dir / "skill_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demo1: 完整生命周期
# ─────────────────────────────────────────────────────────────────────────────

def demo1_full_lifecycle(tmp_path):
    print()
    print("=" * 60)
    print("  Demo1: AgentRuntime.run() 完整生命周期")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    executed = []

    def my_execute(ctx: TaskContext):
        executed.append(ctx.task_id)
        return "done"

    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_type="debugging",
        risk_level="low",
        task_id="t001",
        session_id="s001",
        execute_fn=my_execute,
    )

    print(f"  task_id          : {ctx.task_id}")
    print(f"  state            : {ctx.state.value}")
    print(f"  skill_found      : {ctx.skill_found}")
    print(f"  selected_skill   : {ctx.selected_skill_name}")
    print(f"  guard_decision   : {ctx.guard_decision}")
    print(f"  execution_result : {ctx.execution_result}")
    print(f"  execute_fn called: {len(executed) == 1}")

    assert ctx.state == TaskState.SUCCESS,      f"expected SUCCESS, got {ctx.state}"
    assert ctx.skill_found is True,             f"expected skill_found=True"
    assert ctx.selected_skill_id is not None,   "selected_skill_id is None"
    assert ctx.execution_result == "success",    f"expected success"
    assert len(executed) == 1,                  "execute_fn not called"
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Demo2: Hook 系统
# ─────────────────────────────────────────────────────────────────────────────

def demo2_hooks(tmp_path):
    print()
    print("=" * 60)
    print("  Demo2: Hook 系统 — 全生命周期钩子触发")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    hook_log = []

    runtime.hooks.on_task_created(lambda ctx: hook_log.append(f"created:{ctx.task_id}"))
    runtime.hooks.on_before_route(lambda ctx: hook_log.append(f"before_route:{ctx.task_id}"))
    runtime.hooks.on_after_route(lambda ctx: hook_log.append(f"after_route:{ctx.task_id}"))
    runtime.hooks.on_before_inject(lambda ctx: hook_log.append(f"before_inject:{ctx.task_id}"))
    runtime.hooks.on_after_inject(lambda ctx: hook_log.append(f"after_inject:{ctx.task_id}"))
    runtime.hooks.on_before_execute(lambda ctx: hook_log.append(f"before_exec:{ctx.task_id}"))
    runtime.hooks.on_success(lambda ctx: hook_log.append(f"success:{ctx.task_id}"))
    runtime.hooks.on_before_cleanup(lambda ctx: hook_log.append(f"before_cleanup:{ctx.task_id}"))
    runtime.hooks.on_after_cleanup(lambda ctx: hook_log.append(f"after_cleanup:{ctx.task_id}"))
    runtime.hooks.on_task_done(lambda ctx: hook_log.append(f"done:{ctx.task_id}"))

    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_id="t002",
        session_id="s002",
        execute_fn=lambda c: None,
    )

    print(f"  hooks fired ({len(hook_log)}): {hook_log}")

    expected = [
        "created:t002", "before_route:t002", "after_route:t002",
        "before_inject:t002", "after_inject:t002", "before_exec:t002",
        "success:t002", "before_cleanup:t002", "after_cleanup:t002", "done:t002",
    ]
    assert hook_log == expected, f"hook mismatch:\n  got: {hook_log}\n  expected: {expected}"
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Demo3: 取消机制
# ─────────────────────────────────────────────────────────────────────────────

def demo3_cancellation(tmp_path):
    print()
    print("=" * 60)
    print("  Demo3: CancellationToken 取消任务")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    # 先跑完一个任务
    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_id="t003",
        session_id="s003",
        execute_fn=lambda c: None,
    )
    print(f"  original state: {ctx.state.value}")

    # 完成后 cancel 应无效
    result = runtime.cancel("t003")
    print(f"  cancel after completion: {result} (expected False)")

    # Hook 阻止执行模拟取消
    runtime2 = AgentRuntime(phoenix_base_dir=tmp_path)
    runtime2.hooks.on_before_execute(lambda ctx: False)

    ctx2 = runtime2.run(
        task_description="WSL中文路径修复",
        task_id="t003b",
        session_id="s003b",
        execute_fn=lambda c: "never called",
    )

    print(f"  state after hook cancel: {ctx2.state.value}")
    assert ctx2.state == TaskState.CANCELLED, f"expected CANCELLED, got {ctx2.state}"
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Demo4: 任务持久化
# ─────────────────────────────────────────────────────────────────────────────

def demo4_task_store(tmp_path):
    print()
    print("=" * 60)
    print("  Demo4: TaskStore 持久化 + 恢复")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_id="t004",
        session_id="s004",
        execute_fn=lambda c: None,
    )

    # 重启 runtime（模拟进程重启）
    runtime2 = AgentRuntime(phoenix_base_dir=tmp_path)
    recovered = runtime2.get_task("t004")

    print(f"  original state  : {ctx.state.value}")
    print(f"  recovered state : {recovered.state.value}")
    print(f"  recovered skill : {recovered.selected_skill_name}")

    assert recovered is not None, "get_task returned None"
    assert recovered.task_id == "t004"
    assert recovered.state == TaskState.SUCCESS
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Demo5: Feedback 集成
# ─────────────────────────────────────────────────────────────────────────────

def demo5_feedback_integration(tmp_path):
    print()
    print("=" * 60)
    print("  Demo5: FeedbackDispatcher 集成")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_id="t005",
        session_id="s005",
        execute_fn=lambda c: None,
    )

    log_dir = tmp_path / "logs"
    from datetime import date
    reporter_log = log_dir / f"runtime_{date.today().strftime('%Y%m%d')}.jsonl"

    print(f"  reporter log exists: {reporter_log.exists()}")
    if reporter_log.exists():
        lines = reporter_log.read_text(encoding="utf-8").strip().splitlines()
        print(f"  reporter log lines: {len(lines)}")
        if lines:
            record = json.loads(lines[-1])
            print(f"  record skill_id : {record.get('selected_skill_id')}")
            print(f"  record result   : {record.get('execution_result')}")

    assert ctx.state == TaskState.SUCCESS
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Demo6: 失败路径
# ─────────────────────────────────────────────────────────────────────────────

def demo6_failure_path(tmp_path):
    print()
    print("=" * 60)
    print("  Demo6: 失败路径 + on_failure hook")
    print("=" * 60)

    create_mock_skill_env(tmp_path)
    runtime = AgentRuntime(phoenix_base_dir=tmp_path)

    failure_hook_called = []
    runtime.hooks.on_failure(lambda ctx: failure_hook_called.append(ctx.task_id))

    def always_fail(ctx: TaskContext):
        raise RuntimeError("intentional failure")

    ctx = runtime.run(
        task_description="WSL中文路径修复",
        task_id="t006",
        session_id="s006",
        execute_fn=always_fail,
    )

    print(f"  state            : {ctx.state.value}")
    print(f"  failure_reason   : {ctx.failure_reason}")
    print(f"  failure hook call: {len(failure_hook_called) == 1}")

    assert ctx.state == TaskState.FAILED, f"expected FAILED, got {ctx.state}"
    assert "intentional failure" in (ctx.failure_reason or "")
    assert len(failure_hook_called) == 1
    print("  PASS")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  Phoenix-Evo V0.8 Agent Runtime — Demo Suite")
    print("=" * 60)

    tmp_path = Path(tempfile.mkdtemp(prefix="phoenix_v08_"))

    try:
        results = []
        results.append(("Demo1 (full lifecycle)",  demo1_full_lifecycle(tmp_path)))
        results.append(("Demo2 (hook system)",      demo2_hooks(tmp_path)))
        results.append(("Demo3 (cancellation)",     demo3_cancellation(tmp_path)))
        results.append(("Demo4 (task store)",       demo4_task_store(tmp_path)))
        results.append(("Demo5 (feedback)",         demo5_feedback_integration(tmp_path)))
        results.append(("Demo6 (failure path)",     demo6_failure_path(tmp_path)))

        print()
        print("=" * 60)
        print("  RESULTS")
        print("=" * 60)
        all_pass = True
        for name, ok in results:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {name}")
            if not ok:
                all_pass = False

        print()
        print(f"  Total: {sum(1 for _, ok in results if ok)}/{len(results)} passed")
        print("=" * 60)

        if all_pass:
            print("  All demos PASSED — V0.8 Agent Runtime READY")
        else:
            print("  Some demos FAILED — check output above")

    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
