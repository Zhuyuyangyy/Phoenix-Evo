"""Tests for daemon_entry.py — standalone Docker entrypoint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class TestDaemonEntry:
    """Verify daemon_entry.py can be imported and has correct structure."""

    def test_module_imports(self):
        """daemon_entry.py should import without triggering circular imports."""
        import importlib
        mod = importlib.import_module("daemon_entry")
        assert hasattr(mod, "main")

    def test_argparse_help(self):
        """daemon_entry.py --help should exit 0 and show usage."""
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "daemon_entry.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "PhoenixRuntimeDaemon" in result.stdout
        assert "base_dir" in result.stdout

    def test_missing_base_dir_exits_nonzero(self):
        """Running without base_dir should fail with exit code 2 (argparse error)."""
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "daemon_entry.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
