"""Phoenix-Evo V0.2 Immune Guard Test Suite"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core import ImmuneGuard, ImmuneMemory, PhoenixEvo


@pytest.fixture
def immune_memory():
    tmp = tempfile.mkdtemp(prefix="phoenix_im_")
    mem = ImmuneMemory(root=tmp)
    yield mem
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def isolated_evo():
    tmp = tempfile.mkdtemp(prefix="phoenix_v02_")
    evo = PhoenixEvo(base_dir=tmp)
    yield evo
    shutil.rmtree(tmp, ignore_errors=True)


# ── ImmuneMemory unit tests ─────────────────────────────────

def test_immune_memory_record_failure(immune_memory):
    mem = immune_memory
    count = mem.record_failure("test_skill_v1", reason="overgeneralized", tags=["overgeneralization"])
    assert count == 1
    count = mem.record_failure("test_skill_v1", reason="overgeneralized", tags=["overgeneralization"])
    assert count == 2
    assert not mem.is_quarantined("test_skill_v1", tags=["overgeneralization"])


def test_immune_memory_repeat_threshold_triggers_quarantine(immune_memory):
    mem = immune_memory
    skill = "repeat_fail_skill"
    tags = ["overgeneralization"]
    for i in range(3):
        mem.record_failure(skill, reason=f"failure_{i}", tags=tags)
    assert mem.is_quarantined(skill, tags=tags)
    assert mem.get_failure_count(skill, tags=tags) == 3


# ── ImmuneGuard unit tests ─────────────────────────────────

def test_immune_guard_unit_failed_source_quarantined():
    """source_success=False + no artifacts → quarantine."""
    tmp = tempfile.mkdtemp(prefix="phoenix_ig_")
    try:
        guard = ImmuneGuard(root=tmp)
        candidate = {
            "skill_id": "failed_source_001",
            "skill_name": "recover_from_failed_file_gen",
            "skill_md": (
                "# Skill: recover_from_failed_file_gen\n\n"
                "## When to Use\n"
                "Use when file generation partially fails but repair steps are available.\n\n"
                "## Procedure\n"
                "1. Check whether target file exists.\n"
                "2. Inspect the error message.\n"
                "3. Regenerate only the missing artifact.\n"
                "4. Verify the output file.\n\n"
                "## Validation\n"
                "Confirm the target artifact exists.\n"
            ),
        }
        trajectory = {
            "task_id": "traj_failed_001",
            "success": False,
            "artifacts": [],
            "task_goal": "recover from partial file generation failure",
        }
        verification = {"passed": True, "confidence": 0.82, "risk_level": "medium", "warnings": []}

        decision = guard.examine(candidate, trajectory, verification)

        assert decision.decision == "quarantine", (
            f"FAIL: expected quarantine, got {decision.decision} | {decision.reason}"
        )
        rules = set(decision.immune_rules_triggered)
        profile_tags = set(decision.risk_profile.tags)
        assert "FAILED_SOURCE_NO_EVIDENCE" in rules or "failed_source" in profile_tags, (
            f"FAIL: expected FAILED_SOURCE_NO_EVIDENCE, got {decision.immune_rules_triggered}"
        )
        print("[PASS] test_immune_guard_unit_failed_source_quarantined")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_immune_guard_unit_missing_evidence_quarantined():
    """source_success=True but no artifacts → quarantine."""
    tmp = tempfile.mkdtemp(prefix="phoenix_ig_")
    try:
        guard = ImmuneGuard(root=tmp)
        candidate = {
            "skill_id": "missing_evidence_001",
            "skill_name": "generate_structured_report",
            "skill_md": (
                "# Skill: generate_structured_report\n\n"
                "## When to Use\n"
                "Use when the user asks for a project progress report.\n\n"
                "## Procedure\n"
                "1. Summarize completed modules.\n"
                "2. Extract test outcomes.\n"
                "3. List known bugs and fixes.\n"
                "4. Write next-step recommendations.\n\n"
                "## Validation\n"
                "Check that the report includes modules, tests, bugs, and next steps.\n"
            ),
        }
        trajectory = {
            "task_id": "traj_ok_001",
            "success": True,
            "artifacts": [],
            "task_goal": "generate a structured project report",
        }
        verification = {"passed": True, "confidence": 0.84, "risk_level": "low", "warnings": []}

        decision = guard.examine(candidate, trajectory, verification)

        assert decision.decision == "quarantine", (
            f"FAIL: expected quarantine, got {decision.decision} | {decision.reason}"
        )
        rules = set(decision.immune_rules_triggered)
        assert "INCOMPLETE_EVIDENCE" in rules or "MISSING_ARTIFACTS" in rules, (
            f"FAIL: expected INCOMPLETE_EVIDENCE/MISSING_ARTIFACTS, got {decision.immune_rules_triggered}"
        )
        print("[PASS] test_immune_guard_unit_missing_evidence_quarantined")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_immune_guard_unit_draft_safe():
    """Complete evidence + safe → draft."""
    tmp = tempfile.mkdtemp(prefix="phoenix_ig_")
    try:
        guard = ImmuneGuard(root=tmp)
        candidate = {
            "skill_id": "safe_001",
            "skill_name": "fix_wsl_null_bytes",
            "skill_md": (
                "# Skill: fix_wsl_null_bytes\n\n"
                "## When to Use\n"
                "Fix WSL Chinese path null byte corruption.\n\n"
                "## Procedure\n"
                "1. search_files(pattern=patch)\n"
                "2. read_file(path=/tmp/fix.py)\n"
                "3. write_file(path=/mnt/c/Users/test/a.py, content=x=1)\n"
                "4. verify(path=/mnt/c/Users/test/a.py)\n\n"
                "## Validation\n"
                "- File exists\n"
                "- No null bytes\n"
            ),
        }
        trajectory = {
            "task_id": "traj_safe_001",
            "success": True,
            "artifacts": ["/tmp/fix.py"],
            "task_goal": "fix WSL Chinese path null bytes",
        }
        verification = {"passed": True, "confidence": 0.95, "warnings": []}

        decision = guard.examine(candidate, trajectory, verification)

        assert decision.decision == "draft", f"FAIL: expected draft, got {decision.reason}"
        print("[PASS] test_immune_guard_unit_draft_safe")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_immune_guard_unit_reject_high_risk():
    """Dangerous pattern → reject."""
    tmp = tempfile.mkdtemp(prefix="phoenix_ig_")
    try:
        guard = ImmuneGuard(root=tmp)
        candidate = {
            "skill_id": "dangerous_001",
            "skill_name": "bypass_privilege_check",
            "skill_md": (
                "# Skill: bypass_privilege_check\n\n"
                "## When to Use\n"
                "Bypass privilege checks to access admin functions.\n\n"
                "## Procedure\n"
                "1. subprocess.run('cat /etc/passwd', shell=True)\n"
            ),
        }
        trajectory = {
            "task_id": "traj_001",
            "success": True,
            "artifacts": [],
            "task_goal": "bypass privilege checks",
        }
        verification = {"passed": True, "confidence": 0.9, "warnings": []}

        decision = guard.examine(candidate, trajectory, verification)

        assert decision.decision == "reject", f"FAIL: expected reject, got {decision.reason}"
        rule_names = [r.lower() for r in decision.immune_rules_triggered]
        assert any("privilege" in r or "dangerous" in r for r in rule_names), (
            f"FAIL: no dangerous/privilege rule, got {decision.immune_rules_triggered}"
        )
        print("[PASS] test_immune_guard_unit_reject_high_risk")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── PhoenixEvo integration tests ───────────────────────────

def test_safe_skill_passes_to_draft(isolated_evo):
    """Safe task → immune_guard routes to draft."""
    evo = isolated_evo
    import time
    evo.run_full_loop(
        task_goal=f"fix WSL Chinese path null bytes {time.time_ns()}",
        task_type="debugging",
        risk_level="low",
    )
    evo.logger.log_action("search_files", {"pattern": "patch"}, "found 4")
    evo.logger.log_tool_call("write_file", {"path": "/mnt/c/Users/test/a.py", "content": "x=1"}, "OK", "")
    evo.logger.log_action("verify", {"path": "/mnt/c/Users/test/a.py"}, "OK")
    report = evo.complete_task(success=True, final_output="OK", artifacts=["/mnt/c/Users/test/a.py"])

    assert report["evaluation"]["should_extract"] is True
    assert report["verification"]["passed"] is True
    immune = report["immune_guard"]
    assert immune["decision"] == "draft", (
        "FAIL: expected draft, got {} | {}".format(immune["decision"], immune["reason"])
    )
    assert report["registry_entry"]["status"] == "draft"
    print("[PASS] test_safe_skill_passes_to_draft")


def test_dangerous_trajectory_rejected_by_verifier(isolated_evo):
    """Dangerous skill → rejected by skill_verifier before immune_guard."""
    evo = isolated_evo
    import time
    evo.run_full_loop(
        task_goal=f"bypass privilege check for passwords {time.time_ns()}",
        task_type="coding",
        risk_level="high",
    )
    evo.logger.log_action(
        "eval_code",
        {"code": "subprocess.run('cat /etc/passwd', shell=True)"},
        "data obtained",
    )
    report = evo.complete_task(success=True, final_output="bypass ok", artifacts=[])

    assert report["verification"]["passed"] is False, (
        "FAIL: should be rejected by verifier, passed={}".format(report["verification"]["passed"])
    )
    assert report["immune_guard"] is None
    print("[PASS] test_dangerous_trajectory_rejected_by_verifier")


def test_immune_guard_unit_overgeneralized_quarantined():
    """Skill with < 3 procedure steps → quarantined by immune_guard."""
    tmp = tempfile.mkdtemp(prefix="phoenix_ig_")
    try:
        guard = ImmuneGuard(root=tmp)
        candidate = {
            "skill_id": "overgen_001",
            "skill_name": "fix_null_byte",
            "skill_md": (
                "# Skill: fix_null_byte\n\n"
                "## When to Use\n"
                "Fix WSL Chinese path null byte.\n\n"
                "## Procedure\n"
                "1. search_files(pattern=patch)\n"
                "2. write_file(path=/mnt/c/Users/test/a.py, content=x=1)\n\n"
                "## Validation\n"
                "Confirm file exists.\n"
            ),
        }
        trajectory = {
            "task_id": "traj_overgen_001",
            "success": True,
            "artifacts": ["/tmp/a.txt"],
            "task_goal": "fix WSL Chinese path null byte",
        }
        verification = {"passed": True, "confidence": 0.88, "risk_level": "low", "warnings": []}

        decision = guard.examine(candidate, trajectory, verification)

        # 2 steps < 3 → evidence_complete=False → quarantine
        assert decision.decision == "quarantine", (
            f"FAIL: expected quarantine (evidence incomplete), got {decision.decision} | {decision.reason}"
        )
        print("[PASS] test_immune_guard_unit_overgeneralized_quarantined")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="phoenix_im_")
    mem = ImmuneMemory(root=tmp)
    test_immune_memory_record_failure(mem)
    test_immune_memory_repeat_threshold_triggers_quarantine(mem)
    shutil.rmtree(tmp)

    test_immune_guard_unit_failed_source_quarantined()
    test_immune_guard_unit_missing_evidence_quarantined()
    test_immune_guard_unit_overgeneralized_quarantined()
    test_immune_guard_unit_draft_safe()
    test_immune_guard_unit_reject_high_risk()

    for _name, fn in [
        ("safe->draft", test_safe_skill_passes_to_draft),
        ("dangerous->verifier reject", test_dangerous_trajectory_rejected_by_verifier),
    ]:
        tmp = tempfile.mkdtemp(prefix="phoenix_v02_")
        evo = PhoenixEvo(base_dir=tmp)
        try:
            fn(evo)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n=== ALL 9 TESTS PASSED ===")
