"""Tests for skill bundle."""

import os
import tempfile

import pytest

from core.skill_bundle import (
    BundleManifest,
    CompatibilityChecker,
    SkillBundleExporter,
    SkillBundleImporter,
)


class TestBundleManifest:
    def test_create(self):
        m = BundleManifest(skill_id="s1", skill_name="Test", version="1.0.0")
        assert m.format_version == "1.0"

    def test_to_dict(self):
        m = BundleManifest(skill_id="s1", skill_name="Test", version="1.0.0")
        d = m.to_dict()
        assert d["skill_id"] == "s1"
        assert d["version"] == "1.0.0"

    def test_from_dict(self):
        d = {"skill_id": "s1", "skill_name": "Test", "version": "1.0.0",
             "description": "", "author": "", "created_at": 0.0,
             "code_hash": "abc", "dependencies": [], "phoenix_version": "2.0",
             "metadata": {}}
        m = BundleManifest.from_dict(d)
        assert m.skill_id == "s1"


class TestSkillBundleExporter:
    def test_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter()
            path = exporter.export(
                skill_id="s1",
                skill_name="Test Skill",
                version="1.0.0",
                code="print('hello')",
                description="A test skill",
                output_path=os.path.join(tmpdir, "test.phxskill"),
            )
            assert os.path.exists(path)

    def test_export_with_signing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter(signing_key="test_key")
            path = exporter.export(
                skill_id="s1",
                skill_name="Test",
                version="1.0.0",
                code="print('hello')",
                output_path=os.path.join(tmpdir, "signed.phxskill"),
            )
            assert os.path.exists(path)

    def test_export_with_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter()
            path = exporter.export(
                skill_id="s1",
                skill_name="Test",
                version="1.0.0",
                code="print('hello')",
                config={"timeout": 30},
                output_path=os.path.join(tmpdir, "config.phxskill"),
            )
            assert os.path.exists(path)


class TestSkillBundleImporter:
    def test_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter()
            path = exporter.export(
                skill_id="s1",
                skill_name="Test",
                version="1.0.0",
                code="print('hello')",
                output_path=os.path.join(tmpdir, "test.phxskill"),
            )

            importer = SkillBundleImporter(verify_signature=False)
            result = importer.import_bundle(path)
            assert result["valid"] is True
            assert result["manifest"].skill_id == "s1"
            assert result["code"] == "print('hello')"

    def test_import_nonexistent(self):
        importer = SkillBundleImporter()
        with pytest.raises(FileNotFoundError):
            importer.import_bundle("/nonexistent/path.phxskill")

    def test_import_with_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter()
            path = exporter.export(
                skill_id="s1",
                skill_name="Test",
                version="1.0.0",
                code="print('hello')",
                config={"timeout": 30},
                output_path=os.path.join(tmpdir, "test.phxskill"),
            )

            importer = SkillBundleImporter(verify_signature=False)
            result = importer.import_bundle(path)
            assert result["config"]["timeout"] == 30

    def test_code_hash_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SkillBundleExporter()
            path = exporter.export(
                skill_id="s1",
                skill_name="Test",
                version="1.0.0",
                code="print('hello')",
                output_path=os.path.join(tmpdir, "test.phxskill"),
            )

            importer = SkillBundleImporter(verify_signature=False)
            result = importer.import_bundle(path)
            assert result["valid"] is True


class TestCompatibilityChecker:
    def test_compatible(self):
        checker = CompatibilityChecker(current_phoenix_version="2.0")
        manifest = BundleManifest(
            skill_id="s1", skill_name="Test", version="1.0.0",
            code_hash="abc", phoenix_version="2.0",
        )
        result = checker.check(manifest)
        assert result["compatible"] is True

    def test_major_version_mismatch(self):
        checker = CompatibilityChecker(current_phoenix_version="2.0")
        manifest = BundleManifest(
            skill_id="s1", skill_name="Test", version="1.0.0",
            code_hash="abc", phoenix_version="1.0",
        )
        result = checker.check(manifest)
        assert result["compatible"] is False

    def test_format_version_mismatch(self):
        checker = CompatibilityChecker(current_phoenix_version="2.0")
        manifest = BundleManifest(
            skill_id="s1", skill_name="Test", version="1.0.0",
            code_hash="abc", format_version="0.9",
        )
        result = checker.check(manifest)
        assert result["compatible"] is False

    def test_dependency_check(self):
        checker = CompatibilityChecker(current_phoenix_version="2.0")
        manifest = BundleManifest(
            skill_id="s1", skill_name="Test", version="1.0.0",
            code_hash="abc", dependencies=["phoenix>=3.0"],
        )
        result = checker.check(manifest)
        assert result["compatible"] is False
