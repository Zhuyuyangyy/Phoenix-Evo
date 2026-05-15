"""
TrajectoryLogger: 轨迹记录器
V0.1 — Phoenix-Evo

职责：任务执行过程中持续记录 actions、tool_calls、errors、fixes。
      任务完成后生成完整 trajectory JSON，保存至 data/trajectories/。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class TrajectoryLogger:
    """
    记录单个任务的完整执行轨迹。

    使用方式：
        logger = TrajectoryLogger(task_goal="用户目标描述", task_type="coding")
        logger.start()
        logger.log_action("read_file", {"path": "/tmp/test.py"})
        logger.log_tool_call("terminal", {"command": "ls"})
        logger.log_error("patch", "FileNotFoundError: ...")
        logger.log_fix("patch", "retry with absolute path")
        result = logger.complete(success=True, final_output="...", artifacts=["/tmp/out.txt"])
        # result == trajectory dict
    """

    def __init__(
        self,
        task_goal: str,
        task_type: str = "general",
        risk_level: str = "low",
        session_id: str = None,
    ):
        self.task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.task_goal = task_goal
        self.task_type = task_type
        self.risk_level = risk_level
        self.session_id = session_id or datetime.now().strftime("%Y%m%d")

        self._plan: list[dict] = []
        self._actions: list[dict] = []
        self._tool_calls: list[dict] = []
        self._errors: list[dict] = []
        self._fixes: list[dict] = []
        self._started_at: str | None = None
        self._completed_at: str | None = None

    # ── 记录 API ────────────────────────────────────────────────

    def start(self) -> None:
        self._started_at = datetime.now().isoformat()

    def log_plan_step(self, step: str, expected: str = "") -> None:
        self._plan.append({"step": step, "expected": expected, "logged_at": datetime.now().isoformat()})

    def log_action(self, action: str, params: dict[str, Any] | None = None, result: str = "") -> None:
        self._actions.append({
            "action": action,
            "params": params or {},
            "result": result,
            "logged_at": datetime.now().isoformat(),
        })

    def log_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        raw_result: str = "",
        error: str = "",
    ) -> None:
        entry = {
            "tool": tool_name,
            "args": args or {},
            "raw_result": raw_result[:500] if raw_result else "",  # 截断避免过大
            "error": error,
            "logged_at": datetime.now().isoformat(),
        }
        self._tool_calls.append(entry)
        # 同步记入 actions，供技能提取使用
        self.log_action(tool_name, args, raw_result[:200] if raw_result else ("error: " + error if error else ""))
        if error:
            self.log_error(tool_name, error)

    def log_error(self, phase: str, message: str, recoverable: bool = False) -> None:
        self._errors.append({
            "phase": phase,
            "message": message,
            "recoverable": recoverable,
            "logged_at": datetime.now().isoformat(),
        })

    def log_fix(self, phase: str, strategy: str, succeeded: bool = True) -> None:
        self._fixes.append({
            "phase": phase,
            "strategy": strategy,
            "succeeded": succeeded,
            "logged_at": datetime.now().isoformat(),
        })

    def log_artifact(self, path: str) -> None:
        """标记一个产物路径（如生成的代码、文档）。"""
        self._actions[-1]["artifact"] = path if self._actions else path

    # ── 完成 ────────────────────────────────────────────────────

    def complete(
        self,
        success: bool,
        final_output: str = "",
        artifacts: list[str] | None = None,
    ) -> dict:
        self._completed_at = datetime.now().isoformat()
        duration = ""
        if self._started_at and self._completed_at:
            start = datetime.fromisoformat(self._started_at)
            end = datetime.fromisoformat(self._completed_at)
            delta = end - start
            duration = f"{delta.total_seconds():.1f}s"

        trajectory = {
            "task_id": self.task_id,
            "task_goal": self.task_goal,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "session_id": self.session_id,
            "started_at": self._started_at,
            "completed_at": self._completed_at,
            "duration": duration,
            "plan": self._plan,
            "actions": self._actions,
            "tool_calls": self._tool_calls,
            "errors": self._errors,
            "fixes": self._fixes,
            "final_output": final_output[:2000] if final_output else "",
            "artifacts": artifacts or [],
            "success": success,
        }

        self._save(trajectory)
        return trajectory

    # ── 持久化 ─────────────────────────────────────────────────

    def _save(self, trajectory: dict) -> Path:
        out_dir = Path(__file__).parent.parent / "data" / "trajectories"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{trajectory['task_id']}.json"
        path.write_text(json.dumps(trajectory, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def load(task_id: str) -> dict:
        traj_dir = Path(__file__).parent.parent / "data" / "trajectories"
        path = traj_dir / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def list_trajectories(limit: int = 50) -> list[dict]:
        traj_dir = Path(__file__).parent.parent / "data" / "trajectories"
        if not traj_dir.exists():
            return []
        files = sorted(traj_dir.glob("task_*.json"), reverse=True)
        results = []
        for f in files[:limit]:
            d = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "task_id": d["task_id"],
                "task_goal": d["task_goal"],
                "task_type": d["task_type"],
                "success": d["success"],
                "completed_at": d["completed_at"],
                "duration": d.get("duration", ""),
            })
        return results
