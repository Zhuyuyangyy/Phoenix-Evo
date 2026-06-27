"""
Phoenix-Evo V1.0 ReplayManager
===============================
Replays historical task trajectories and verifies skill behavior consistency.

ReplayResult dataclass:
  - task_id, original_session_id, skill_id
  - original_success, replay_success, verdict ("pass" | "fail" | "partial")
  - step_results: list[StepResult]
  - replayed_at, notes

Usage:
    manager = ReplayManager(phoenix_base_dir=Path("/path/to/Phoenix-Evo"))
    result = manager.replay(task_id, execute_fn=my_execute_fn)
    print(result.verdict, result.notes)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# ─────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    step_index: int
    step_name: str
    expected_output: Any
    actual_output: Any
    match: bool
    notes: str = ""


@dataclass
class ReplayResult:
    task_id: str
    skill_id: str
    original_session_id: str
    original_success: bool
    replay_success: bool
    verdict: str  # "pass" | "fail" | "partial" | "error"
    step_results: list[StepResult] = field(default_factory=list)
    replayed_at: str = ""
    notes: str = ""


# ─────────────────────────────────────────────────────────────
# ReplayManager
# ─────────────────────────────────────────────────────────────

class ReplayManager:
    """
    Replays historical trajectories to verify skill behavior consistency.

    execute_fn should have signature:
        execute_fn(step: dict) -> {"ok": bool, "output": str, ...}
    """

    def __init__(self, phoenix_base_dir: Path | str):
        self.base_dir = Path(phoenix_base_dir)
        self.trajectories_dir = self.base_dir / "trajectories"
        self.replays_dir = self.base_dir / "replays"
        self.replays_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ──────────────────────────────────────────────

    def list_replayable(self) -> list[dict]:
        """Return trajectories that have all required fields for replay."""
        if not self.trajectories_dir.exists():
            return []

        replayable = []
        for f in self.trajectories_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if self._has_required_fields(data):
                    replayable.append({
                        "task_id": data.get("task_id", f.stem),
                        "skill_id": data.get("skill_id", "unknown"),
                        "session_id": data.get("session_id", ""),
                        "steps_count": len(data.get("procedure", [])),
                        "original_success": data.get("success", False),
                        "created_at": data.get("created_at", ""),
                    })
            except Exception:
                continue
        return sorted(replayable, key=lambda x: x.get("created_at", ""), reverse=True)

    def replay(
        self,
        task_id: str,
        execute_fn: Callable[[dict], dict],
    ) -> ReplayResult:
        """
        Replay a single trajectory by task_id.

        execute_fn(step: dict) -> output dict
          - step contains: {name, procedure_id, args, expected_output}
          - should return {"ok": bool, "output": str}

        Returns ReplayResult.
        """
        trajectory = self._load_trajectory(task_id)
        if trajectory is None:
            return ReplayResult(
                task_id=task_id,
                skill_id="?",
                original_session_id="?",
                original_success=False,
                replay_success=False,
                verdict="error",
                notes=f"Trajectory '{task_id}' not found",
            )

        skill_id = trajectory.get("skill_id", "unknown")
        original_success = trajectory.get("success", False)
        session_id = trajectory.get("session_id", "")
        procedure = trajectory.get("procedure", [])

        if not procedure:
            return ReplayResult(
                task_id=task_id,
                skill_id=skill_id,
                original_session_id=session_id,
                original_success=original_success,
                replay_success=False,
                verdict="error",
                notes="Trajectory has no procedure steps",
            )

        step_results: list[StepResult] = []
        all_match = True
        any_mismatch = False

        for i, step in enumerate(procedure):
            step_name = step.get("name", f"step-{i}")
            expected = step.get("expected_output") or step.get("output") or ""
            args = step.get("args") or {}

            try:
                actual_raw = execute_fn({**step, "args": args})
                actual = actual_raw.get("output", str(actual_raw)) if isinstance(actual_raw, dict) else str(actual_raw)
                ok = actual_raw.get("ok", True) if isinstance(actual_raw, dict) else True
            except Exception as ex:
                actual = f"EXCEPTION: {ex}"
                ok = False

            match = ok and self._outputs_match(expected, actual)
            if not match:
                any_mismatch = True
                all_match = False

            step_results.append(StepResult(
                step_index=i,
                step_name=step_name,
                expected_output=expected,
                actual_output=actual,
                match=match,
                notes="" if match else f"Expected '{expected}', got '{actual}'",
            ))

        verdict = "pass" if all_match else ("partial" if not any_mismatch else "fail")
        replay_success = verdict in ("pass", "partial")

        result = ReplayResult(
            task_id=task_id,
            skill_id=skill_id,
            original_session_id=session_id,
            original_success=original_success,
            replay_success=replay_success,
            verdict=verdict,
            step_results=step_results,
            replayed_at=datetime.now().isoformat(),
            notes=f"{sum(1 for s in step_results if s.match)}/{len(step_results)} steps matched",
        )

        self._save_replay_result(result)
        return result

    def replay_batch(
        self,
        task_ids: list[str],
        execute_fn: Callable[[dict], dict],
    ) -> list[ReplayResult]:
        """Replay multiple trajectories."""
        return [self.replay(tid, execute_fn) for tid in task_ids]

    def get_replay_history(self, skill_id: str) -> list[ReplayResult]:
        """Load all saved replay results for a given skill_id."""
        results = []
        for f in self.replays_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("skill_id") == skill_id:
                    results.append(self._dict_to_result(data))
            except Exception:
                continue
        return sorted(results, key=lambda x: x.replayed_at, reverse=True)

    # ── Internal ───────────────────────────────────────────────

    def _has_required_fields(self, data: dict) -> bool:
        return bool(
            data.get("task_id")
            and data.get("skill_id")
            and isinstance(data.get("procedure"), list)
        )

    def _load_trajectory(self, task_id: str) -> dict | None:
        if not self.trajectories_dir.exists():
            return None
        # Try exact match first
        path = self.trajectories_dir / f"{task_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        # Fall back to glob
        for f in self.trajectories_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("task_id") == task_id:
                    return data
            except Exception:
                continue
        return None

    def _outputs_match(self, expected: Any, actual: Any) -> bool:
        """Flexible comparison — handles strings, dicts, booleans."""
        if expected == actual:
            return True
        # Normalize strings
        if isinstance(expected, str) and isinstance(actual, str):
            return expected.strip().lower() == actual.strip().lower()
        # Dict comparison (subset match)
        if isinstance(expected, dict) and isinstance(actual, dict):
            return all(expected.get(k) == actual.get(k) for k in expected)
        return False

    def _save_replay_result(self, result: ReplayResult) -> None:
        path = self.replays_dir / f"{result.task_id}_replay.json"
        data = {
            "task_id": result.task_id,
            "skill_id": result.skill_id,
            "original_session_id": result.original_session_id,
            "original_success": result.original_success,
            "replay_success": result.replay_success,
            "verdict": result.verdict,
            "replayed_at": result.replayed_at,
            "notes": result.notes,
            "step_results": [
                {
                    "step_index": s.step_index,
                    "step_name": s.step_name,
                    "expected_output": s.expected_output,
                    "actual_output": s.actual_output,
                    "match": s.match,
                    "notes": s.notes,
                }
                for s in result.step_results
            ],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _dict_to_result(data: dict) -> ReplayResult:
        return ReplayResult(
            task_id=data["task_id"],
            skill_id=data["skill_id"],
            original_session_id=data.get("original_session_id", ""),
            original_success=data.get("original_success", False),
            replay_success=data.get("replay_success", False),
            verdict=data.get("verdict", "error"),
            replayed_at=data.get("replayed_at", ""),
            notes=data.get("notes", ""),
            step_results=[
                StepResult(
                    step_index=s["step_index"],
                    step_name=s["step_name"],
                    expected_output=s["expected_output"],
                    actual_output=s["actual_output"],
                    match=s["match"],
                    notes=s.get("notes", ""),
                )
                for s in data.get("step_results", [])
            ],
        )


# ─────────────────────────────────────────────────────────────
# Quick Demo
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "trajectories").mkdir()

        # Write a sample trajectory
        traj = {
            "task_id": "task-demo-001",
            "skill_id": "code-review",
            "session_id": "session-abc",
            "success": True,
            "procedure": [
                {
                    "name": "parse_code",
                    "args": {"code": "def foo(): pass"},
                    "expected_output": "parsed",
                },
                {
                    "name": "lint",
                    "args": {},
                    "expected_output": "clean",
                },
            ],
            "created_at": datetime.now().isoformat(),
        }
        (base / "trajectories" / "task-demo-001.json").write_text(
            json.dumps(traj), encoding="utf-8"
        )

        manager = ReplayManager(phoenix_base_dir=base)

        print("=== list_replayable() ===")
        print(manager.list_replayable())

        print("\n=== replay() ===")
        def mock_execute_fn(step):
            if step["name"] == "parse_code":
                return {"ok": True, "output": "parsed"}
            if step["name"] == "lint":
                return {"ok": True, "output": "clean"}
            return None

        result = manager.replay("task-demo-001", execute_fn=mock_execute_fn)
        print(f"verdict={result.verdict}  notes={result.notes}")
        for s in result.step_results:
            print(f"  step-{s.step_index} {s.step_name}: match={s.match}  notes={s.notes}")

        print("\n=== get_replay_history() ===")
        print(manager.get_replay_history("code-review"))
