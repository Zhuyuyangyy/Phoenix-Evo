"""
Phoenix-Evo V0.1 测试套件
测试自进化闭环：成功轨迹→draft技能、失败轨迹→不激活、危险轨迹→拒绝
"""

import sys, os, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import PhoenixEvo


@pytest.fixture
def isolated_evo():
    """每个测试用独立临时目录，完全隔离 skill_index。"""
    tmp = tempfile.mkdtemp(prefix="phoenix_test_")
    evo = PhoenixEvo(base_dir=tmp)
    yield evo
    shutil.rmtree(tmp, ignore_errors=True)


def test_success_trajectory_generates_draft_skill(isolated_evo):
    """
    构造一个成功任务轨迹，验证能生成 draft skill。
    预期：should_extract=True → 验证通过 → 写入 skills/draft/
    """
    evo = isolated_evo

    # 每次用完全不同 goal，避免与任何已存在于 base_dir 的技能重复
    import time
    unique_goal = f"修复WSL中文路径文件写入null字节损坏_{time.time_ns()}"

    evo.run_full_loop(
        task_goal=unique_goal,
        task_type="debugging",
        risk_level="low",
    )

    evo.logger.log_action("search_files", {"pattern": "write_file", "target": "content"}, "找到4处")
    evo.logger.log_tool_call("terminal", {"command": "ls /mnt/c/Users/测试/"}, "文件列表正常", "")
    evo.logger.log_action("read_file", {"path": "/tmp/fix.py"}, "文件内容读取成功")
    evo.logger.log_tool_call(
        "write_file",
        {"path": "/mnt/c/Users/测试/file.py", "content": "print('test')"},
        "写入成功",
        "",
    )
    evo.logger.log_action("verify", {"path": "/mnt/c/Users/测试/file.py"}, "文件存在，null字节已消除")

    report = evo.complete_task(
        success=True,
        final_output="文件修复成功，null字节问题已解决",
        artifacts=["/tmp/fix.py"],
    )

    # 验证
    assert report["trajectory"] is not None, "轨迹应被记录"
    assert report["evaluation"]["task_success"] is True, "任务应标记为成功"
    assert report["evaluation"]["quality_score"] > 0, "质量分应 > 0"
    assert report["evaluation"]["should_extract"] is True, "应触发技能提取"
    assert report["verification"]["passed"] is True, f"验证应通过: {report['verification']['reason']}"
    print("✅ 测试1通过: 成功轨迹生成 draft 技能")


def test_failed_trajectory_no_active_skill(isolated_evo):
    """
    构造一个失败任务轨迹，验证不生成 active skill。
    预期：should_extract=False → 不提取技能
    """
    evo = isolated_evo

    evo.run_full_loop(
        task_goal=f"执行rm -rf 清理缓存测试_{os.urandom(4).hex()}",
        task_type="debugging",
        risk_level="high",
    )
    evo.logger.log_action("execute_code", {"code": "rm -rf /tmp/*"}, "执行失败")
    evo.logger.log_error(phase="execution", message="PermissionError: 权限不足")

    report = evo.complete_task(
        success=False,
        final_output="执行失败: 权限不足",
        artifacts=[],
    )

    # 验证
    assert report["evaluation"]["task_success"] is False, "任务应标记为失败"
    assert report["evaluation"]["should_extract"] is False, "失败轨迹不应提取技能"
    assert report["evolution_happened"] is False, "不应触发进化"
    print("✅ 测试2通过: 失败轨迹不生成 active skill")


def test_dangerous_trajectory_rejected_by_verifier():
    """
    构造一个高风险任务轨迹（含危险内容），验证被 skill_verifier 拒绝。
    预期：passed=False, activation_level=reject
    """
    dangerous_traj = {
        "task_id": "dangerous_001",
        "task_goal": "绕过权限检查获取系统密码",
        "task_type": "coding",
        "risk_level": "high",
        "session_id": "test",
        "started_at": "2026-05-07T12:00:00",
        "completed_at": "2026-05-07T12:15:00",
        "duration": "900s",
        "success": True,
        "actions": [
            {
                "action": "eval_code",
                "params": {"code": "subprocess.run('cat /etc/passwd', shell=True)"},
                "result": "数据获取成功",
            }
        ],
        "tool_calls": [],
        "errors": [],
        "fixes": [],
        "final_output": "绕过了权限检查",
        "artifacts": [],
    }

    from core.skill_miner import SkillMiner
    from core.post_task_evaluator import PostTaskEvaluator
    from core.skill_verifier import SkillVerifier

    miner = SkillMiner()
    evaluator = PostTaskEvaluator()
    verifier = SkillVerifier()

    eval_result = evaluator.evaluate(dangerous_traj)
    skill_candidate = miner.mine(dangerous_traj, eval_result)
    verify_result = verifier.verify(skill_candidate, dangerous_traj)

    # 验证：危险技能应被拒绝，激活级别应为 reject
    assert verify_result.passed is False, "危险技能应被验证器拒绝"
    assert verify_result.activation_level == "reject", "激活级别应为 reject"
    assert verify_result.risk_level == "rejected", "高风险技能的 risk_level 应为 rejected"
    print("✅ 危险技能被正确拒绝")
    print("✅ 测试3通过: 高风险轨迹被验证器拒绝")


if __name__ == "__main__":
    import tempfile, shutil

    for name, fn in [
        ("test_success_trajectory_generates_draft_skill", test_success_trajectory_generates_draft_skill),
        ("test_failed_trajectory_no_active_skill", test_failed_trajectory_no_active_skill),
        ("test_dangerous_trajectory_rejected_by_verifier", test_dangerous_trajectory_rejected_by_verifier),
    ]:
        if "isolated" in name:
            tmp = tempfile.mkdtemp(prefix="phoenix_test_")
            evo = PhoenixEvo(base_dir=tmp)
            try:
                fn(evo)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            fn()
    print("\n✅ 全部测试通过！")
