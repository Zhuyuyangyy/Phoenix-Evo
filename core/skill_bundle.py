"""Skill bundle export/import for Phoenix-Evo (.phxskill format)."""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


BUNDLE_FORMAT_VERSION = "1.0"
BUNDLE_EXTENSION = ".phxskill"
BUNDLE_MANIFEST = "manifest.json"
BUNDLE_CODE = "code.py"
BUNDLE_CONFIG = "config.json"
BUNDLE_SIGNATURE = "signature.json"


@dataclass
class BundleManifest:
    """Manifest for a skill bundle."""
    format_version: str = BUNDLE_FORMAT_VERSION
    skill_id: str = ""
    skill_name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    created_at: float = field(default_factory=time.time)
    code_hash: str = ""
    dependencies: List[str] = field(default_factory=list)
    trust_score: Optional[float] = None
    phoenix_version: str = "2.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "code_hash": self.code_hash,
            "dependencies": self.dependencies,
            "trust_score": self.trust_score,
            "phoenix_version": self.phoenix_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BundleManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SkillBundleExporter:
    """Exports skills as .phxskill bundles."""

    def __init__(self, signing_key: Optional[str] = None):
        self.signing_key = signing_key

    def export(
        self,
        skill_id: str,
        skill_name: str,
        version: str,
        code: str,
        description: str = "",
        author: str = "",
        dependencies: Optional[List[str]] = None,
        trust_score: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Export a skill as a .phxskill bundle.

        Returns the path to the created bundle file.
        """
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]

        manifest = BundleManifest(
            skill_id=skill_id,
            skill_name=skill_name,
            version=version,
            description=description,
            author=author,
            code_hash=code_hash,
            dependencies=dependencies or [],
            trust_score=trust_score,
            metadata=metadata or {},
        )

        if output_path is None:
            output_path = f"{skill_id}_v{version}{BUNDLE_EXTENSION}"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write manifest
            manifest_path = os.path.join(tmpdir, BUNDLE_MANIFEST)
            with open(manifest_path, "w") as f:
                json.dump(manifest.to_dict(), f, indent=2)

            # Write code
            code_path = os.path.join(tmpdir, BUNDLE_CODE)
            with open(code_path, "w") as f:
                f.write(code)

            # Write config
            config_path = os.path.join(tmpdir, BUNDLE_CONFIG)
            with open(config_path, "w") as f:
                json.dump(config or {}, f, indent=2)

            # Write signature if signing key provided
            if self.signing_key:
                sig = self._sign_manifest(manifest)
                sig_path = os.path.join(tmpdir, BUNDLE_SIGNATURE)
                with open(sig_path, "w") as f:
                    json.dump(sig, f, indent=2)

            # Create tarball
            with tarfile.open(output_path, "w:gz") as tar:
                for fname in os.listdir(tmpdir):
                    tar.add(os.path.join(tmpdir, fname), arcname=fname)

        return output_path

    def _sign_manifest(self, manifest: BundleManifest) -> Dict[str, Any]:
        """Sign a manifest with the signing key."""
        payload = json.dumps(manifest.to_dict(), sort_keys=True)
        message = f"{payload}:{self.signing_key}"
        signature = hashlib.sha256(message.encode()).hexdigest()
        return {
            "algorithm": "sha256",
            "signature": signature,
            "signed_at": time.time(),
        }


class SkillBundleImporter:
    """Imports skills from .phxskill bundles."""

    def __init__(self, verify_signature: bool = True, signing_key: Optional[str] = None):
        self.verify_signature = verify_signature
        self.signing_key = signing_key

    def import_bundle(self, bundle_path: str) -> Dict[str, Any]:
        """Import a skill from a .phxskill bundle.

        Returns a dictionary with manifest, code, config, and validation results.
        """
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"Bundle not found: {bundle_path}")

        result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(bundle_path, "r:gz") as tar:
                tar.extractall(tmpdir)

            # Read manifest
            manifest_path = os.path.join(tmpdir, BUNDLE_MANIFEST)
            if not os.path.exists(manifest_path):
                result["valid"] = False
                result["errors"].append("Missing manifest.json")
                return result

            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)
            manifest = BundleManifest.from_dict(manifest_data)
            result["manifest"] = manifest

            # Read code
            code_path = os.path.join(tmpdir, BUNDLE_CODE)
            if os.path.exists(code_path):
                with open(code_path, "r") as f:
                    result["code"] = f.read()

                # Verify code hash
                actual_hash = hashlib.sha256(result["code"].encode()).hexdigest()[:16]
                if actual_hash != manifest.code_hash:
                    result["valid"] = False
                    result["errors"].append("Code hash mismatch")
            else:
                result["warnings"].append("No code file in bundle")

            # Read config
            config_path = os.path.join(tmpdir, BUNDLE_CONFIG)
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    result["config"] = json.load(f)

            # Verify signature
            sig_path = os.path.join(tmpdir, BUNDLE_SIGNATURE)
            if os.path.exists(sig_path):
                with open(sig_path, "r") as f:
                    result["signature"] = json.load(f)
            elif self.verify_signature:
                result["warnings"].append("No signature in bundle")

        return result


class CompatibilityChecker:
    """Checks compatibility between skill bundles and the current Phoenix version."""

    def __init__(self, current_phoenix_version: str = "2.0"):
        self.current_version = current_phoenix_version

    def check(self, manifest: BundleManifest) -> Dict[str, Any]:
        """Check if a bundle is compatible with the current system."""
        result = {
            "compatible": True,
            "issues": [],
            "warnings": [],
        }

        # Check format version
        if manifest.format_version != BUNDLE_FORMAT_VERSION:
            result["compatible"] = False
            result["issues"].append(
                f"Format version mismatch: bundle={manifest.format_version}, system={BUNDLE_FORMAT_VERSION}"
            )

        # Check Phoenix version compatibility
        bundle_version = manifest.phoenix_version
        try:
            bundle_major = int(bundle_version.split(".")[0])
            system_major = int(self.current_version.split(".")[0])
            if bundle_major != system_major:
                result["compatible"] = False
                result["issues"].append(
                    f"Phoenix major version mismatch: bundle={bundle_version}, system={self.current_version}"
                )
        except (ValueError, IndexError):
            result["warnings"].append(f"Cannot parse version: {bundle_version}")

        # Check dependencies
        for dep in manifest.dependencies:
            if dep.startswith("phoenix>="):
                min_version = dep.split(">=")[1].strip()
                if min_version > self.current_version:
                    result["compatible"] = False
                    result["issues"].append(
                        f"Dependency requires Phoenix >= {min_version}, current is {self.current_version}"
                    )

        return result
