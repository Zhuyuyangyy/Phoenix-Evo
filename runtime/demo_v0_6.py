"""
V0.6 Runtime Skill Router 完整 Demo
Phoenix-Evo Runtime Skill Router

演示场景：
  Demo 1: 相似任务命中 active skill（注入成功）
  Demo 2: draft skill 被拒绝注入
  Demo 3: 无匹配 skill 触发 fallback
  Demo 4: 高 evidence_score skill 排名靠前
  Demo 5: 低 evidence_score 被 Guard 拒绝
  Demo 6: 全流程 PhoenixRuntime.route() 端到端
"""

import json
import shutil
import tempfile
from pathlib import Path


def create_mock_active_skill(base_dir, skill_id, content):
    active_dir = base_dir / "skills" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    (active_dir / f"{skill_id}.md").write_text(content, encoding="utf-8")


def create_mock_draft_skill(base_dir, skill_id, content):
    draft_dir = base_dir / "skills" / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / f"{skill_id}.md").write_text(content, encoding="utf-8")


def create_skill_index(base_dir, entries):
    index = {}
    for e in entries:
        index[e["skill_id"]] = e
    idx_path = base_dir / "skills" / "skill_index.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def make_active_skill_md(name, skill_id, when_to_use, procedure,
                         quality_score=0.75, risk_level="low",
                         evidence_score=0.80, replay_pass_rate=0.80,
                         usage_count=5, success_count=4):
    return f"""# Skill: {name}

## Metadata
- **skill_id**: {skill_id}
- **task_type**: debugging
- **source_trajectory**: task_debug_{skill_id}
- **status**: active
- **quality_score**: {quality_score}
- **evidence_score**: {evidence_score}
- **replay_pass_rate**: {replay_pass_rate}
- **risk_level**: {risk_level}
- **usage_count**: {usage_count}
- **success_count**: {success_count}
- **success_rate**: {success_count}/{usage_count}

## When to Use
{when_to_use}

## Procedure
{procedure}

## Validation
- 验证: verify -> 文件存在且内容正确

## Safety Note
[low_risk] [file_write] [verified]
"""


# --------------------------------------------------------------------------- #
# Demo 1
# --------------------------------------------------------------------------- #

def demo1():
    print("\n============================================================")
    print("  Demo 1: 相似任务命中 active skill（注入成功）")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    s1 = make_active_skill_md(
        "修复WSL中文路径文件写入null字节", "fix_wsl_chinese_path_null_bytes",
        "当任务目标是修复WSL中文路径下文件写入出现null字节损坏时使用",
        "1. search_files(pattern=patch)\n2. write_file with proper encoding\n3. verify",
        quality_score=0.82, risk_level="medium", evidence_score=0.78,
        replay_pass_rate=0.85, usage_count=8, success_count=7,
    )
    s2 = make_active_skill_md(
        "Git冲突解决", "git_merge_conflict_resolution",
        "当遇到Git merge冲突需要解决合并冲突时使用",
        "1. git status\n2. 手动编辑冲突文件\n3. git add && git commit",
        quality_score=0.90, risk_level="low", evidence_score=0.88,
        replay_pass_rate=0.95, usage_count=20, success_count=19,
    )

    create_mock_active_skill(tmp, "fix_wsl_chinese_path_null_bytes", s1)
    create_mock_active_skill(tmp, "git_merge_conflict_resolution", s2)
    create_skill_index(tmp, [
        {"skill_id": "fix_wsl_chinese_path_null_bytes", "skill_name": "修复WSL中文路径文件写入null字节", "status": "active", "quality_score": 0.82, "risk_level": "medium", "evidence_score": 0.78, "replay_pass_rate": 0.85, "usage_count": 8, "success_count": 7, "success_rate": 0.875, "task_type": "debugging"},
        {"skill_id": "git_merge_conflict_resolution", "skill_name": "Git冲突解决", "status": "active", "quality_score": 0.90, "risk_level": "low", "evidence_score": 0.88, "replay_pass_rate": 0.95, "usage_count": 20, "success_count": 19, "success_rate": 0.95, "task_type": "git"},
    ])

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)

    result = runtime.route(
        task_description="修复WSL中文路径文件写入null字节损坏问题",
        task_type="debugging", risk_level="medium", session_id="demo_001",
    )

    print(f"  skill_found={result.skill_found} injected={result.injected}")
    print(f"  guard_decision={result.guard_decision}")
    if result.selected_skill_id:
        print(f"  selected_skill={result.selected_skill_id}")
        print(f"  route_score={result.route_score}")
    print(f"  fallback_reason={result.fallback_reason}")
    print(f"  duration={result.duration_seconds}s")

    if result.injected:
        for line in result.context.split("\n")[:4]:
            print(f"    {line}")

    assert result.injected, "应该注入成功"
    assert result.selected_skill_id == "fix_wsl_chinese_path_null_bytes"
    print("  PASS")
    shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# Demo 2
# --------------------------------------------------------------------------- #

def demo2():
    print("\n============================================================")
    print("  Demo 2: draft skill 被 RuntimeGuard 拒绝")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    draft_md = "# Skill: test_draft\n## Metadata\n- **skill_id**: test_draft_skill\n- **status**: draft\n- **quality_score**: 0.60\n- **risk_level**: low\n- **evidence_score**: 0.55\n## When to Use\n当测试draft技能时使用\n## Procedure\n1. echo hello\n"
    create_mock_draft_skill(tmp, "test_draft_skill", draft_md)
    create_skill_index(tmp, [
        {"skill_id": "test_draft_skill", "skill_name": "测试draft技能", "status": "draft",
         "quality_score": 0.60, "risk_level": "low", "evidence_score": 0.55},
    ])

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)
    result = runtime.route(task_description="测试draft技能", session_id="demo_002")

    print(f"  injected={result.injected} guard_decision={result.guard_decision}")
    print(f"  fallback_reason={result.fallback_reason}")

    assert not result.injected
    assert result.fallback_reason is not None
    print("  PASS")
    shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# Demo 3
# --------------------------------------------------------------------------- #

def demo3():
    print("\n============================================================")
    print("  Demo 3: 无匹配 skill 触发 fallback")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)
    result = runtime.route(task_description="量子计算芯片设计", session_id="demo_003")

    print(f"  injected={result.injected} fallback_reason={result.fallback_reason}")
    assert not result.injected
    assert result.fallback_reason == "no_skill_found"
    print("  PASS")
    shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# Demo 4
# --------------------------------------------------------------------------- #

def demo4():
    print("\n============================================================")
    print("  Demo 4: 高 evidence_score skill 排名靠前")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    s_low = make_active_skill_md("旧版修复", "old_fix", "WSL路径修复", "1. old method",
                                  quality_score=0.55, risk_level="medium",
                                  evidence_score=0.45, replay_pass_rate=0.40,
                                  usage_count=2, success_count=1)
    s_high = make_active_skill_md("新版修复", "new_fix", "WSL路径修复", "1. new method",
                                   quality_score=0.85, risk_level="low",
                                   evidence_score=0.85, replay_pass_rate=0.90,
                                   usage_count=15, success_count=14)

    create_mock_active_skill(tmp, "old_fix", s_low)
    create_mock_active_skill(tmp, "new_fix", s_high)
    create_skill_index(tmp, [
        {"skill_id": "old_fix", "skill_name": "旧版修复", "status": "active", "quality_score": 0.55, "risk_level": "medium", "evidence_score": 0.45, "replay_pass_rate": 0.40, "usage_count": 2, "success_count": 1, "success_rate": 0.5},
        {"skill_id": "new_fix", "skill_name": "新版修复", "status": "active", "quality_score": 0.85, "risk_level": "low", "evidence_score": 0.85, "replay_pass_rate": 0.90, "usage_count": 15, "success_count": 14, "success_rate": 0.933},
    ])

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)
    result = runtime.route(task_description="WSL路径修复", session_id="demo_004")

    print(f"  top_skill={result.route_results[0].skill_id if result.route_results else 'N/A'}")
    print(f"  top_score={result.route_results[0].route_score if result.route_results else 'N/A'}")
    assert result.route_results[0].skill_id == "new_fix"
    print("  PASS")
    shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# Demo 5
# --------------------------------------------------------------------------- #

def demo5():
    print("\n============================================================")
    print("  Demo 5: 低 evidence_score skill 被 Guard 拒绝")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    s_low = make_active_skill_md("未经充分验证的修复", "unverified_fix",
                                  "WSL修复", "1. unverified method",
                                  quality_score=0.40, risk_level="medium",
                                  evidence_score=0.35, replay_pass_rate=0.30,
                                  usage_count=1, success_count=0)
    create_mock_active_skill(tmp, "unverified_fix", s_low)
    create_skill_index(tmp, [
        {"skill_id": "unverified_fix", "skill_name": "未经充分验证的修复", "status": "active",
         "quality_score": 0.40, "risk_level": "medium", "evidence_score": 0.35,
         "replay_pass_rate": 0.30, "usage_count": 1, "success_count": 0, "success_rate": 0.0},
    ])

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)
    result = runtime.route(task_description="WSL路径修复", session_id="demo_005")

    print(f"  injected={result.injected} guard_decision={result.guard_decision}")
    assert not result.injected
    assert result.guard_decision == "deny"
    print("  PASS")
    shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# Demo 6
# --------------------------------------------------------------------------- #

def demo6():
    print("\n============================================================")
    print("  Demo 6: PhoenixRuntime.query() 端到端全流程")
    print("============================================================")
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_v06_"))

    skills = [
        ("s1_wsl", "WSL中文路径修复", "WSL中文路径文件写入null字节", "medium", 0.82, 0.85),
        ("s2_git", "Git冲突解决", "Git merge冲突解决", "low", 0.90, 0.95),
        ("s3_doc", "文档生成", "自动生成API文档", "low", 0.75, 0.80),
    ]
    for sid, name, when, risk, ev, rr in skills:
        create_mock_active_skill(tmp, sid, make_active_skill_md(
            name, sid, when, f"1. {name} procedure",
            quality_score=ev, risk_level=risk, evidence_score=ev,
            replay_pass_rate=rr, usage_count=10, success_count=int(ev*10),
        ))
    create_skill_index(tmp, [
        {"skill_id": sid, "skill_name": name, "status": "active",
         "quality_score": ev, "risk_level": risk, "evidence_score": ev,
         "replay_pass_rate": rr, "usage_count": 10, "success_count": int(ev*10),
         "success_rate": ev}
        for sid, name, _, risk, ev, rr in skills
    ])

    from runtime import PhoenixRuntime
    runtime = PhoenixRuntime(base_dir=tmp)

    # 6a: Git
    r1 = runtime.query(task_description="解决Git merge冲突", task_type="git",
                       risk_level="low", session_id="s_git")
    print(f"  6a Git: injected={r1.injected} skill={r1.selected_skill_name} score={r1.route_score}")
    assert r1.injected

    # 6b: WSL
    r2 = runtime.query(task_description="修复WSL中文路径文件写入null字节",
                       risk_level="medium", session_id="s_wsl")
    print(f"  6b WSL: injected={r2.injected} skill={r2.selected_skill_name} score={r2.route_score}")
    assert r2.injected

    # 6c: 未知
    r3 = runtime.query(task_description="设计神经网络芯片架构", session_id="s_unknown")
    print(f"  6c Unknown: injected={r3.injected} fallback={r3.fallback_reason}")
    assert not r3.injected
    assert r3.fallback_reason == "no_skill_found"

    stats = runtime.reporter.get_skill_stats("s1_wsl")
    print(f"  reporter stats: {stats}")

    print("  PASS")
    shutil.rmtree(tmp)


def main():
    print("Phoenix-Evo V0.6 Runtime Skill Router Demo")
    print("=" * 60)
    demo1()
    demo2()
    demo3()
    demo4()
    demo5()
    demo6()
    print("\n" + "=" * 60)
    print("所有 Demo 通过！V0.6 Runtime Skill Router 验证完成。")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    main()
