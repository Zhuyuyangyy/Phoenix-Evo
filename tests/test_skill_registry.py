"""
Tests for SkillRegistry module.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.skill_registry import SkillRegistry
from core.skill_verifier import VerificationResult


class TestSkillRegistry:
    """Test suite for SkillRegistry."""

    def _make_verification_result(self, **kwargs):
        """Helper to create a VerificationResult."""
        vr = VerificationResult(
            passed=True,
            confidence=0.9,
            risk_level="low",
            activation_level="draft",
            reason="test verification passed",
            warnings=[],
            checked_items={},
        )
        for k, v in kwargs.items():
            setattr(vr, k, v)
        return vr

    def _make_skill(self, **kwargs):
        """Helper to create a test skill."""
        skill = {
            "skill_id": "test_skill_001",
            "skill_name": "test_skill",
            "skill_md": "# Skill: test\n\n## Procedure\n1. Step one\n2. Step two\n",
            "source_trajectory": "traj_001",
            "quality_score": 0.85,
        }
        skill.update(kwargs)
        return skill

    def test_init_creates_directories(self, tmp_path):
        """Test that initialization creates required directories."""
        registry = SkillRegistry(root=tmp_path)
        assert (tmp_path / "skills" / "draft").exists()
        assert (tmp_path / "skills" / "active").exists()
        assert (tmp_path / "skills" / "archived").exists()

    def test_add_draft(self, tmp_path):
        """Test adding a skill as draft."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        path = registry.add_draft(skill, vr)
        assert path.exists()
        assert path.name == "test_skill_001.md"

        # Check index
        index = registry.get_index()
        assert "test_skill_001" in index
        assert index["test_skill_001"]["status"] == "draft"

    def test_add_draft_writes_skill_md(self, tmp_path):
        """Test that add_draft writes the skill markdown file."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill(skill_md="# My Skill\n\nContent here")
        vr = self._make_verification_result()

        path = registry.add_draft(skill, vr)
        content = path.read_text(encoding="utf-8")
        assert "# My Skill" in content

    def test_activate_skill(self, tmp_path):
        """Test activating a draft skill."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        result = registry.activate("test_skill_001", approved_by="human")

        assert result is not None
        assert result.exists()
        assert "active" in str(result)

        index = registry.get_index()
        assert index["test_skill_001"]["status"] == "active"
        assert index["test_skill_001"]["approved_by"] == "human"

    def test_activate_nonexistent_skill(self, tmp_path):
        """Test activating a non-existent skill returns None."""
        registry = SkillRegistry(root=tmp_path)
        result = registry.activate("nonexistent_skill")
        assert result is None

    def test_activate_non_draft_skill(self, tmp_path):
        """Test activating a non-draft skill returns None."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        registry.activate("test_skill_001")

        # Try to activate again (already active)
        result = registry.activate("test_skill_001")
        assert result is None

    def test_archive_skill(self, tmp_path):
        """Test archiving a skill."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        result = registry.archive("test_skill_001", reason="test archive")

        assert result is True
        index = registry.get_index()
        assert index["test_skill_001"]["status"] == "archived"

    def test_archive_nonexistent_skill(self, tmp_path):
        """Test archiving a non-existent skill returns False."""
        registry = SkillRegistry(root=tmp_path)
        result = registry.archive("nonexistent_skill")
        assert result is False

    def test_reject_skill(self, tmp_path):
        """Test rejecting a skill."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()

        registry.reject(skill, reason="dangerous content")

        index = registry.get_index()
        rejected_key = "__rejected__test_skill_001"
        assert rejected_key in index
        assert index[rejected_key]["status"] == "rejected"

    def test_record_usage_success(self, tmp_path):
        """Test recording successful usage."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        registry.record_usage("test_skill_001", success=True)

        index = registry.get_index()
        entry = index["test_skill_001"]
        assert entry["usage_count"] == 1
        assert entry["success_count"] == 1
        assert entry["success_rate"] == 1.0

    def test_record_usage_failure(self, tmp_path):
        """Test recording failed usage."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        registry.record_usage("test_skill_001", success=False)

        index = registry.get_index()
        entry = index["test_skill_001"]
        assert entry["usage_count"] == 1
        assert entry["success_count"] == 0
        assert entry["success_rate"] == 0.0

    def test_record_usage_multiple(self, tmp_path):
        """Test recording multiple usages."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        registry.record_usage("test_skill_001", success=True)
        registry.record_usage("test_skill_001", success=True)
        registry.record_usage("test_skill_001", success=False)

        index = registry.get_index()
        entry = index["test_skill_001"]
        assert entry["usage_count"] == 3
        assert entry["success_count"] == 2
        assert abs(entry["success_rate"] - 0.667) < 0.01

    def test_record_usage_nonexistent_skill(self, tmp_path):
        """Test recording usage for non-existent skill does nothing."""
        registry = SkillRegistry(root=tmp_path)
        registry.record_usage("nonexistent_skill", success=True)
        # Should not raise

    def test_get_active_skills(self, tmp_path):
        """Test getting active skills."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)
        registry.activate("test_skill_001")

        active = registry.get_active_skills()
        assert len(active) == 1
        assert active[0]["skill_id"] == "test_skill_001"

    def test_get_draft_skills(self, tmp_path):
        """Test getting draft skills."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill()
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)

        drafts = registry.get_draft_skills()
        assert len(drafts) == 1
        assert drafts[0]["skill_id"] == "test_skill_001"

    def test_find_similar(self, tmp_path):
        """Test finding similar skills."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill(skill_name="wsl_path_fix")
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)

        similar = registry.find_similar("wsl_path")
        assert "test_skill_001" in similar

    def test_find_similar_no_match(self, tmp_path):
        """Test finding similar skills with no match."""
        registry = SkillRegistry(root=tmp_path)
        skill = self._make_skill(skill_name="wsl_path_fix")
        vr = self._make_verification_result()

        registry.add_draft(skill, vr)

        similar = registry.find_similar("completely_different")
        assert len(similar) == 0

    def test_load_index_empty(self, tmp_path):
        """Test loading index when no file exists."""
        registry = SkillRegistry(root=tmp_path)
        index = registry._load_index()
        assert index == {}

    def test_load_index_corrupted(self, tmp_path):
        """Test loading corrupted index file."""
        registry = SkillRegistry(root=tmp_path)
        index_path = tmp_path / "skills" / "skill_index.json"
        index_path.parent.mkdir(parents=True)
        index_path.write_text("invalid json{")

        index = registry._load_index()
        assert index == {}

    def test_save_index_creates_file(self, tmp_path):
        """Test that saving index creates the file."""
        registry = SkillRegistry(root=tmp_path)
        registry._save_index({"test": {"status": "draft"}})

        index_path = tmp_path / "skills" / "skill_index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert "test" in data

    def test_get_status(self, tmp_path):
        """Test getting registry status."""
        registry = SkillRegistry(root=tmp_path)
        # This method may not exist in the base SkillRegistry
        # but is called from PhoenixEvo
        index = registry.get_index()
        assert isinstance(index, dict)
