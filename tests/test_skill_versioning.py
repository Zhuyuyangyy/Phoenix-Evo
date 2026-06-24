"""Tests for skill versioning."""

import pytest

from core.skill_versioning import (
    SkillSigner,
    SkillState,
    SkillVersion,
    SkillStateMachine,
    VersionedSkillRegistry,
)


class TestSkillVersion:
    def test_create(self):
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="Test Skill",
            description="A test skill", code_hash="abc123",
        )
        assert sv.state == SkillState.DRAFT
        assert sv.version == "1.0.0"

    def test_to_dict(self):
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="Test",
            description="test", code_hash="abc",
        )
        d = sv.to_dict()
        assert d["state"] == "draft"
        assert d["skill_id"] == "s1"

    def test_from_dict(self):
        d = {
            "skill_id": "s1", "version": "1.0.0", "name": "Test",
            "description": "test", "code_hash": "abc", "state": "published",
        }
        sv = SkillVersion.from_dict(d)
        assert sv.state == SkillState.PUBLISHED


class TestVersionedSkillRegistry:
    def test_register_and_get(self):
        reg = VersionedSkillRegistry()
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="Test",
            description="test", code_hash="abc",
        )
        reg.register(sv)
        result = reg.get("s1")
        assert result is not None
        assert result.version == "1.0.0"

    def test_get_nonexistent(self):
        reg = VersionedSkillRegistry()
        assert reg.get("nonexistent") is None

    def test_get_specific_version(self):
        reg = VersionedSkillRegistry()
        reg.register(SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a"))
        reg.register(SkillVersion(skill_id="s1", version="2.0.0", name="T", description="d", code_hash="b"))
        result = reg.get("s1", version="1.0.0")
        assert result is not None
        assert result.version == "1.0.0"

    def test_get_latest_published(self):
        reg = VersionedSkillRegistry()
        sv1 = SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a")
        sv2 = SkillVersion(skill_id="s1", version="2.0.0", name="T", description="d", code_hash="b", state=SkillState.PUBLISHED)
        reg.register(sv1)
        reg.register(sv2)
        result = reg.get("s1")
        assert result.version == "2.0.0"

    def test_lineage(self):
        reg = VersionedSkillRegistry()
        sv1 = SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a")
        sv2 = SkillVersion(skill_id="s1", version="2.0.0", name="T", description="d", code_hash="b", parent_version="1.0.0")
        reg.register(sv1)
        reg.register(sv2)
        lineage = reg.get_lineage("s1")
        assert len(lineage) == 2
        assert lineage[0].version == "1.0.0"

    def test_list_versions(self):
        reg = VersionedSkillRegistry()
        reg.register(SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a"))
        reg.register(SkillVersion(skill_id="s1", version="2.0.0", name="T", description="d", code_hash="b"))
        versions = reg.list_versions("s1")
        assert len(versions) == 2

    def test_deprecate(self):
        reg = VersionedSkillRegistry()
        sv = SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a")
        reg.register(sv)
        assert reg.deprecate("s1", "1.0.0") is True
        assert reg.get("s1", "1.0.0").state == SkillState.DEPRECATED

    def test_revoke(self):
        reg = VersionedSkillRegistry()
        sv = SkillVersion(skill_id="s1", version="1.0.0", name="T", description="d", code_hash="a")
        reg.register(sv)
        assert reg.revoke("s1", "1.0.0") is True
        assert reg.get("s1", "1.0.0").state == SkillState.REVOKED

    def test_search(self):
        reg = VersionedSkillRegistry()
        reg.register(SkillVersion(skill_id="s1", version="1.0.0", name="Shell Executor", description="Executes shell", code_hash="a"))
        reg.register(SkillVersion(skill_id="s2", version="1.0.0", name="Python Runner", description="Runs Python", code_hash="b"))
        results = reg.search("shell")
        assert len(results) == 1
        assert results[0].skill_id == "s1"


class TestSkillSigner:
    def test_sign_and_verify(self):
        signer = SkillSigner(secret_key="test_key")
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="T",
            description="d", code_hash="abc",
        )
        sv.signature = signer.sign(sv)
        assert signer.verify(sv) is True

    def test_verify_tampered(self):
        signer = SkillSigner(secret_key="test_key")
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="T",
            description="d", code_hash="abc",
        )
        sv.signature = signer.sign(sv)
        sv.code_hash = "tampered"
        assert signer.verify(sv) is False

    def test_verify_no_signature(self):
        signer = SkillSigner()
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="T",
            description="d", code_hash="abc",
        )
        assert signer.verify(sv) is False

    def test_compute_code_hash(self):
        h = SkillSigner.compute_code_hash("print('hello')")
        assert len(h) == 16
        h2 = SkillSigner.compute_code_hash("print('hello')")
        assert h == h2


class TestSkillStateMachine:
    def test_valid_transitions(self):
        sm = SkillStateMachine()
        assert sm.can_transition(SkillState.DRAFT, SkillState.REVIEW)
        assert sm.can_transition(SkillState.REVIEW, SkillState.PUBLISHED)
        assert sm.can_transition(SkillState.PUBLISHED, SkillState.DEPRECATED)
        assert sm.can_transition(SkillState.DEPRECATED, SkillState.REVOKED)

    def test_invalid_transitions(self):
        sm = SkillStateMachine()
        assert not sm.can_transition(SkillState.REVOKED, SkillState.DRAFT)
        assert not sm.can_transition(SkillState.DRAFT, SkillState.PUBLISHED)

    def test_transition(self):
        sm = SkillStateMachine()
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="T",
            description="d", code_hash="abc",
        )
        assert sm.transition(sv, SkillState.REVIEW) is True
        assert sv.state == SkillState.REVIEW

    def test_invalid_transition(self):
        sm = SkillStateMachine()
        sv = SkillVersion(
            skill_id="s1", version="1.0.0", name="T",
            description="d", code_hash="abc",
        )
        assert sm.transition(sv, SkillState.PUBLISHED) is False

    def test_get_valid_transitions(self):
        sm = SkillStateMachine()
        transitions = sm.get_valid_transitions(SkillState.DRAFT)
        assert SkillState.REVIEW in transitions
        assert SkillState.REVOKED in transitions

    def test_revoked_is_terminal(self):
        sm = SkillStateMachine()
        transitions = sm.get_valid_transitions(SkillState.REVOKED)
        assert len(transitions) == 0
