"""Docker-based sandbox for safe agent tool execution."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SandboxConfig:
    """Configuration for a Docker sandbox."""
    image: str = "python:3.11-slim"
    timeout_seconds: int = 60
    max_memory_mb: int = 512
    max_cpu_seconds: int = 30
    network_disabled: bool = True
    read_only_paths: List[str] = field(default_factory=lambda: ["/usr", "/lib", "/bin", "/sbin"])
    writable_paths: List[str] = field(default_factory=lambda: ["/tmp", "/home"])
    env_vars: Dict[str, str] = field(default_factory=dict)
    max_output_bytes: int = 1_000_000


@dataclass
class SandboxResult:
    """Result from a sandbox execution."""
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
    memory_used_mb: float = 0.0
    command_blocked: Optional[str] = None
    secrets_redacted: List[str] = field(default_factory=list)


class CommandPolicyChecker:
    """Checks commands against a safety policy before execution."""

    BLOCKED_PATTERNS = [
        (r'\brm\s+-rf\b.*\s+/', "Recursive force delete from root"),
        (r'\bchmod\s+777', "Insecure permissions (777)"),
        (r'\bmkfs\b', "Filesystem format command"),
        (r':\(\)\s*\{', "Fork bomb"),
        (r'\bcurl\b.*\|\s*(?:bash|sh)', "curl pipe to shell"),
        (r'\bwget\b.*\|\s*(?:bash|sh)', "wget pipe to shell"),
        (r'\bdd\s+if=.*of=/dev/', "Direct disk write"),
        (r'\bshutdown\b', "System shutdown"),
        (r'\breboot\b', "System reboot"),
        (r'\binit\s+[06]', "Init to runlevel 0 or 6"),
        (r'\bmount\b.*\b/dev/sd', "Mount block device"),
        (r'\biptables\b', "Firewall manipulation"),
        (r'\bsysctl\b', "Kernel parameter modification"),
        (r'\bnc\b.*-l', "Netcat listener"),
        (r'\bncat\b.*-l', "Ncat listener"),
    ]

    @classmethod
    def check(cls, command: str) -> Optional[str]:
        """Check if a command is blocked. Returns reason if blocked, None if allowed."""
        for pattern, reason in cls.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return reason
        return None

    @classmethod
    def is_allowed(cls, command: str) -> bool:
        """Return True if the command is allowed."""
        return cls.check(command) is None


class SecretRedactor:
    """Redacts secrets from text output."""

    SECRET_PATTERNS = [
        # API keys
        (r'sk-[a-zA-Z0-9]{20,}', 'sk-***REDACTED***'),
        # AWS Access Keys
        (r'AKIA[0-9A-Z]{16}', 'AKIA***REDACTED***'),
        # AWS Secret Keys
        (r'[A-Za-z0-9/+=]{40}', None),  # Too broad, skip
        # Generic API key patterns
        (r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9]{16,}["\']?',
         'api_key=***REDACTED***'),
        # Bearer tokens
        (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer ***REDACTED***'),
        # Passwords
        (r'(?:password|passwd|pwd)\s*[=:]\s*\S+', 'password=***REDACTED***'),
        # Private keys
        (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----',
         '-----BEGIN PRIVATE KEY-----***REDACTED***-----END PRIVATE KEY-----'),
        # GitHub tokens
        (r'gh[ps]_[a-zA-Z0-9]{36}', 'gh_***REDACTED***'),
        # Slack tokens
        (r'xox[baprs]-[a-zA-Z0-9-]+', 'xox-***REDACTED***'),
    ]

    @classmethod
    def redact(cls, text: str) -> Tuple[str, List[str]]:
        """Redact secrets from text. Returns (redacted_text, list_of_redacted_types)."""
        redacted_types = []
        for pattern, replacement in cls.SECRET_PATTERNS:
            if replacement is None:
                continue
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                redacted_types.append(pattern[:30])
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text, redacted_types


class DockerSandbox:
    """Docker-based sandbox for executing commands safely.

    Supports three execution modes:
    1. Docker SDK (docker Python package)
    2. Docker CLI (subprocess calls to docker)
    3. Local fallback (subprocess with restrictions)
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._mode: Optional[str] = None

    def _detect_mode(self) -> str:
        """Detect the best available execution mode."""
        # Try Docker SDK first
        try:
            import docker
            client = docker.from_env()
            client.ping()
            self._mode = "sdk"
            return "sdk"
        except Exception:
            pass

        # Try Docker CLI
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._mode = "cli"
                return "cli"
        except Exception:
            pass

        # Fall back to local
        self._mode = "local"
        return "local"

    @property
    def mode(self) -> str:
        if self._mode is None:
            self._detect_mode()
        return self._mode  # type: ignore[return-value]

    def execute(self, command: str, cwd: Optional[str] = None) -> SandboxResult:
        """Execute a command in the sandbox."""
        # Check command policy
        block_reason = CommandPolicyChecker.check(command)
        if block_reason:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command blocked: {block_reason}",
                command_blocked=block_reason,
            )

        mode = self.mode
        if mode == "sdk":
            return self._execute_sdk(command, cwd)
        elif mode == "cli":
            return self._execute_cli(command, cwd)
        else:
            return self._execute_local(command, cwd)

    def _execute_sdk(self, command: str, cwd: Optional[str] = None) -> SandboxResult:
        """Execute using Docker SDK."""
        import docker
        client = docker.from_env()

        start_time = time.time()
        try:
            container = client.containers.run(
                self.config.image,
                command=command,
                detach=True,
                mem_limit=f"{self.config.max_memory_mb}m",
                network_disabled=self.config.network_disabled,
                environment=self.config.env_vars,
                working_dir=cwd or "/workspace",
            )
            try:
                result = container.wait(timeout=self.config.timeout_seconds)
            except Exception:
                container.kill()
                container.remove()
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr="Execution timed out",
                    timed_out=True,
                    duration_seconds=time.time() - start_time,
                )

            logs = container.logs()
            container.remove()

            stdout = logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else logs
            stdout, redacted = SecretRedactor.redact(stdout)

            return SandboxResult(
                exit_code=result.get("StatusCode", -1),
                stdout=stdout,
                stderr="",
                duration_seconds=time.time() - start_time,
                secrets_redacted=redacted,
            )
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _execute_cli(self, command: str, cwd: Optional[str] = None) -> SandboxResult:
        """Execute using Docker CLI."""
        start_time = time.time()
        docker_cmd = [
            "docker", "run", "--rm",
            "--memory", f"{self.config.max_memory_mb}m",
            "--network", "none" if self.config.network_disabled else "bridge",
        ]
        for k, v in self.config.env_vars.items():
            docker_cmd.extend(["-e", f"{k}={v}"])
        if cwd:
            docker_cmd.extend(["-w", cwd])
        docker_cmd.extend([self.config.image, "sh", "-c", command])

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=self.config.timeout_seconds,
            )
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")

            stdout, redacted_out = SecretRedactor.redact(stdout)
            stderr, redacted_err = SecretRedactor.redact(stderr)

            return SandboxResult(
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.time() - start_time,
                secrets_redacted=redacted_out + redacted_err,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                timed_out=True,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _execute_local(self, command: str, cwd: Optional[str] = None) -> SandboxResult:
        """Execute locally with restrictions (fallback mode)."""
        start_time = time.time()
        try:
            result = subprocess.run(
                ["sh", "-c", command],
                capture_output=True,
                timeout=self.config.timeout_seconds,
                cwd=cwd,
                env={**os.environ, **self.config.env_vars},
            )
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")

            stdout, redacted_out = SecretRedactor.redact(stdout)
            stderr, redacted_err = SecretRedactor.redact(stderr)

            return SandboxResult(
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.time() - start_time,
                secrets_redacted=redacted_out + redacted_err,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                timed_out=True,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start_time,
            )
