"""Reproducibility manager for Phoenix paper experiments."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExperimentRun:
    """A recorded experiment run for reproducibility."""
    run_id: str
    experiment_id: str
    timestamp: float = field(default_factory=time.time)
    parameters: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    random_seed: int | None = None
    code_version: str = ""
    data_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute a hash of the run for verification."""
        payload = json.dumps({
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "parameters": self.parameters,
            "results": self.results,
            "random_seed": self.random_seed,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ReproducibilityManager:
    """Manages reproducibility of paper experiments.

    Records experiment runs with full provenance and provides
    verification that results can be reproduced.
    """

    def __init__(self, storage_dir: str = ".phoenix_reproducibility"):
        self.storage_dir = storage_dir
        self._runs: dict[str, ExperimentRun] = {}

    def record_run(
        self,
        experiment_id: str,
        parameters: dict[str, Any],
        results: dict[str, Any],
        random_seed: int | None = None,
        code_version: str = "",
        environment: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        """Record an experiment run."""
        import uuid
        run_id = f"run_{uuid.uuid4().hex[:8]}"

        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            parameters=parameters,
            results=results,
            random_seed=random_seed,
            code_version=code_version,
            environment=environment or self._get_environment(),
        )
        run.data_hash = run.compute_hash()
        self._runs[run_id] = run

        # Persist to disk
        self._save_run(run)

        return run

    def verify_run(self, run_id: str) -> dict[str, Any]:
        """Verify that a recorded run's hash is still valid."""
        run = self._runs.get(run_id)
        if not run:
            return {"valid": False, "reason": "Run not found"}

        current_hash = run.compute_hash()
        if current_hash != run.data_hash:
            return {"valid": False, "reason": "Hash mismatch - data may have been modified"}

        return {"valid": True, "run_id": run_id}

    def reproduce(
        self,
        run_id: str,
        executor: Any | None = None,
    ) -> ExperimentRun | None:
        """Attempt to reproduce a previous run."""
        original = self._runs.get(run_id)
        if not original:
            return None

        # Create a new run with the same parameters
        new_run = self.record_run(
            experiment_id=original.experiment_id,
            parameters=original.parameters,
            results={},  # Will be filled by executor
            random_seed=original.random_seed,
            code_version=original.code_version,
        )

        if executor:
            try:
                new_results = executor(original.parameters, original.random_seed)
                new_run.results = new_results
                new_run.data_hash = new_run.compute_hash()
            except Exception as e:
                new_run.results = {"error": str(e)}

        return new_run

    def compare_runs(self, run_id_1: str, run_id_2: str) -> dict[str, Any]:
        """Compare two experiment runs."""
        run1 = self._runs.get(run_id_1)
        run2 = self._runs.get(run_id_2)

        if not run1 or not run2:
            return {"comparable": False, "reason": "One or both runs not found"}

        # Compare parameters
        params_match = run1.parameters == run2.parameters

        # Compare results
        results_diff = {}
        all_keys = set(list(run1.results.keys()) + list(run2.results.keys()))
        for key in all_keys:
            v1 = run1.results.get(key)
            v2 = run2.results.get(key)
            if v1 != v2:
                results_diff[key] = {"run1": v1, "run2": v2}

        return {
            "comparable": True,
            "params_match": params_match,
            "results_match": len(results_diff) == 0,
            "results_diff": results_diff,
        }

    def get_run(self, run_id: str) -> ExperimentRun | None:
        """Get a recorded run."""
        return self._runs.get(run_id)

    def list_runs(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        """List recorded runs, optionally filtered by experiment."""
        runs = list(self._runs.values())
        if experiment_id:
            runs = [r for r in runs if r.experiment_id == experiment_id]
        return [
            {
                "run_id": r.run_id,
                "experiment_id": r.experiment_id,
                "timestamp": r.timestamp,
                "data_hash": r.data_hash,
            }
            for r in runs
        ]

    def _save_run(self, run: ExperimentRun) -> None:
        """Save a run to disk."""
        os.makedirs(self.storage_dir, exist_ok=True)
        filepath = os.path.join(self.storage_dir, f"{run.run_id}.json")
        with open(filepath, "w") as f:
            json.dump({
                "run_id": run.run_id,
                "experiment_id": run.experiment_id,
                "timestamp": run.timestamp,
                "parameters": run.parameters,
                "results": run.results,
                "environment": run.environment,
                "random_seed": run.random_seed,
                "code_version": run.code_version,
                "data_hash": run.data_hash,
            }, f, indent=2, default=str)

    @staticmethod
    def _get_environment() -> dict[str, Any]:
        """Get the current environment info."""
        import sys
        return {
            "python_version": sys.version,
            "platform": sys.platform,
        }
