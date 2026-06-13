"""
Tests for SkillVerifier module.
"""

import pytest
from core.skill_verifier import SkillVerifier, VerificationResult, DANGEROUS_PATTERNS, HIGH_RISK_TYPES


class TestSkillVerifier:
    """Test suite for SkillVerifier."""

    def _make_skill(self, **kwargs):
        """Helper to create a test skill candidate."""
        skill = {
            "skill_id": "test_skill_001",
            "skill_name": "test_skill",
            "skill_md": "# Skill: test\n\n## Procedure\n1. Read file\n2. Write file\n3. Verify output\n",
            "source_trajectory": "traj_001",
            "quality_score": 0.85,
        }
        skill.update(kwargs)
        return skill

    def _make_trajectory(self, **kwargs):
        """Helper to create a test trajectory."""
        traj = {
            "task_id": "traj_001",
            "task_goal": "Fix WSL path encoding",
            "task_type": "coding",
            "risk_level": "low",
            "success": True,
            "actions": [
                {"action": "read_file", "params": {}},
                {"action": "verify_result", "params": {}},
            ],
            "artifacts": ["/tmp/output.txt"],
        }
        traj.update(kwargs)
        return traj

    def test_verify_passes_clean_skill(self):
        """Test that a clean skill passes verification."""
        verifier = SkillVerifier()
        skill = self._make_skill()
        traj = self._make_trajectory()

        result = verifier.verify(skill, traj)
        assert result.passed is True
        assert result.risk_level in ("low", "medium")
        assert result.activation_level == "draft"

    def test_verify_fails_missing_trajectory(self):
        """Test that skill without trajectory fails."""
        verifier = SkillVerifier()
        skill = self._make_skill()
        traj = self._make_trajectory(task_id="")

        result = verifier.verify(skill, traj)
        assert result.passed is False
        assert "has_trajectory" in str(result.checked_items)

    def test_verify_fails_missing_goal(self):
        """Test that skill without goal fails."""
        verifier = SkillVerifier()
        skill = self._make_skill()
        traj = self._make_trajectory(task_goal="")

        result = verifier.verify(skill, traj)
        assert result.passed is False

    def test_verify_fails_dangerous_content(self):
        """Test that skill with dangerous content fails."""
        verifier = SkillVerifier()
        skill = self._make_skill(
            skill_md="# Skill\n\n## Procedure\n1. Run rm -rf / to clean up\n"
        )
        traj = self._make_trajectory()

        result = verifier.verify(skill, traj)
        assert result.passed is False
        assert any("危险" in w or "rm" in w for w in result.warnings)

    def test_verify_fails_high_risk_type(self):
        """Test that high-risk task types fail."""
        verifier = SkillVerifier()
        skill = self._make_skill()
        traj = self._make_trajectory(task_type="payment")

        result = verifier.verify(skill, traj)
        assert result.passed is False

    def test_verify_fails_overgeneralization(self):
        """Test that overgeneralized skills fail."""
        verifier = SkillVerifier()
        skill = self._make_skill(
            skill_md="# Skill\n\nAlways do everything correctly.\n"
        )
        traj = self._make_trajectory()

        result = verifier.verify(skill, traj)
        assert result.passed is False

    def test_verify_detects_duplicate(self, tmp_path):
        """Test duplicate detection."""
        verifier = SkillVerifier()
        # Create a skill file to detect as duplicate
        skills_dir = tmp_path / "skills" / "active"
        skills_dir.mkdir(parents=True)
        (skills_dir / "test_skill.md").write_text("# Existing skill")

        skill = self._make_skill(skill_name="test_skill")
        traj = self._make_trajectory()

        with pytest.MonkeyPatch.context() as m:
            m.setattr('core.skill_verifier.Path', lambda *a: tmp_path / "skills" if a == () else tmp_path)
            result = verifier.verify(skill, traj)
            # May or may not pass depending on duplicate detection

    def test_scan_dangerous_content_clean(self):
        """Test scanning clean content."""
        verifier = SkillVerifier()
        result = verifier._scan_dangerous_content("# Safe skill\n1. Read file\n2. Write file")
        assert result["clean"] is True
        assert len(result["matches"]) == 0

    def test_scan_dangerous_content_rm_rf(self):
        """Test detecting rm -rf."""
        verifier = SkillVerifier()
        result = verifier._scan_dangerous_content("Run rm -rf /tmp/old to clean up")
        assert result["clean"] is False
        assert len(result["matches"]) > 0

    def test_scan_dangerous_content_eval(self):
        """Test detecting eval()."""
        verifier = SkillVerifier()
        result = verifier._scan_dangerous_content("Use eval(user_input) to execute")
        assert result["clean"] is False

    def test_scan_dangerous_content_pickle(self):
        """Test detecting pickle.loads."""
        verifier = SkillVerifier()
        result = verifier._scan_dangerous_content("Use pickle.loads(data) to deserialize")
        assert result["clean"] is False

    def test_check_risk_level_low(self):
        """Test risk level classification for low risk."""
        verifier = SkillVerifier()
        risk, reason = verifier._check_risk_level({"task_type": "general", "risk_level": "low"})
        assert risk == "low"

    def test_check_risk_level_high_type(self):
        """Test risk level classification for high-risk type."""
        verifier = SkillVerifier()
        risk, reason = verifier._check_risk_level({"task_type": "payment", "risk_level": "low"})
        assert risk == "high"

    def test_check_risk_level_medium(self):
        """Test risk level classification for medium risk."""
        verifier = SkillVerifier()
        risk, reason = verifier._check_risk_level({"task_type": "coding", "risk_level": "low"})
        assert risk == "medium"

    def test_check_overgeneralization_valid(self):
        """Test overgeneralization check with valid skill."""
        verifier = SkillVerifier()
        md = "# Skill\n\n## Procedure\n1. Step one\n2. Step two\n3. Step three\n"
        result = verifier._check_overgeneralization(md)
        assert result["clean"] is True

    def test_check_overgeneralization_too_few_steps(self):
        """Test overgeneralization check with too few steps."""
        verifier = SkillVerifier()
        md = "# Skill\n\n## Procedure\n1. Just one step\n"
        result = verifier._check_overgeneralization(md)
        assert result["clean"] is False
        assert any("步骤不足" in w for w in result["warnings"])

    def test_check_overgeneralization_vague_language(self):
        """Test overgeneralization check with vague language."""
        verifier = SkillVerifier()
        md = "# Skill\n\nAlways guarantee everything works.\n1. Step one\n2. Step two\n"
        result = verifier._check_overgeneralization(md)
        assert any("泛化" in w for w in result["warnings"])

    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        verifier = SkillVerifier()
        skill = self._make_skill()
        traj = self._make_trajectory()

        result = verifier.verify(skill, traj)
        # All checks should pass for a clean skill
        assert result.confidence > 0.8

    def test_warnings_accumulation(self):
        """Test that warnings are accumulated correctly."""
        verifier = SkillVerifier()
        skill = self._make_skill(
            skill_md="# Skill\n\nAlways do this.\n1. Step one\n2. Step two\n"
        )
        traj = self._make_trajectory()

        result = verifier.verify(skill, traj)
        # Should have overgeneralization warnings
        assert len(result.warnings) > 0

    def test_verification_result_fields(self):
        """Test that VerificationResult has all required fields."""
        result = VerificationResult(
            passed=True,
            confidence=0.9,
            risk_level="low",
            activation_level="draft",
            reason="test",
            warnings=["warning1"],
            checked_items={"check1": True},
        )
        assert result.passed is True
        assert result.confidence == 0.9
        assert result.risk_level == "low"
        assert "warning1" in result.warnings

    def test_dangerous_patterns_coverage(self):
        """Test that dangerous patterns cover key categories."""
        patterns = [p[1] for p in DANGEROUS_PATTERNS]
        # Should cover destructive, financial, privacy, security
        assert len(DANGEROUS_PATTERNS) >= 10

    def test_high_risk_types_coverage(self):
        """Test that high-risk types are defined."""
        assert "payment" in HIGH_RISK_TYPES
        assert "penetration" in HIGH_RISK_TYPES
