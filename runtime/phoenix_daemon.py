"""
Phoenix-Evo V1.0 PhoenixRuntimeDaemon
======================================
Background service that orchestrates OutcomeTracker processing
and periodic SkillCurator scans.

Usage:
    daemon = PhoenixRuntimeDaemon(
        phoenix_base_dir=Path("/path/to/Phoenix-Evo"),
        check_interval=300,        # OutcomeTracker check interval (seconds)
        curator_interval=3600,    # SkillCurator scan interval (seconds)
    )
    daemon.start()
    ...  # runs until stop() is called
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


# ── FastAPI application for health checks and API ──────────────────────────

def _create_app() -> FastAPI:
    """Create the FastAPI application (lazy to avoid import at module level)."""
    from fastapi import FastAPI

    app = FastAPI(title="Phoenix-Evo", version="1.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = None


def get_app() -> FastAPI:
    """Return the singleton FastAPI app instance."""
    global app
    if app is None:
        app = _create_app()
    return app


class PhoenixRuntimeDaemon:
    """
    Background daemon that:
      - outcome_loop: periodically calls OutcomeTracker.process_pending()
      - curator_loop: periodically calls SkillCurator.scan()

    Handles SIGTERM gracefully via stop_event.
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str,
        check_interval: int = 300,
        curator_interval: int = 3600,
    ):
        self.base_dir = Path(phoenix_base_dir)
        self.check_interval = check_interval
        self.curator_interval = curator_interval

        self._stop_event = threading.Event()
        self._outcome_thread: threading.Thread | None = None
        self._curator_thread: threading.Thread | None = None
        self._started = False
        self._started_at: float | None = None

        # Lazy imports — allow phoenix modules to be absent until needed
        self._outcome_tracker = None
        self._curator = None
        self._metrics = None

    # ── Public API ──────────────────────────────────────────────

    def start(self) -> None:
        """Start both daemon threads. Idempotent."""
        if self._started:
            logger.warning("PhoenixRuntimeDaemon already running")
            return

        self._stop_event.clear()
        self._started = True
        self._started_at = time.time()

        self._outcome_thread = threading.Thread(
            target=self._outcome_loop, name="phoenix-outcome", daemon=True
        )
        self._curator_thread = threading.Thread(
            target=self._curator_loop, name="phoenix-curator", daemon=True
        )

        self._outcome_thread.start()
        self._curator_thread.start()

        logger.info(
            f"PhoenixRuntimeDaemon started — outcome every {self.check_interval}s, "
            f"curator every {self.curator_interval}s"
        )

    def stop(self, timeout: float = 10.0) -> None:
        """Stop both threads gracefully. Blocks up to `timeout` seconds."""
        if not self._started:
            return

        logger.info("Stopping PhoenixRuntimeDaemon...")
        self._stop_event.set()

        for t in [self._outcome_thread, self._curator_thread]:
            if t is not None:
                t.join(timeout=timeout)

        self._started = False
        logger.info("PhoenixRuntimeDaemon stopped")

    def is_running(self) -> bool:
        return self._started and not self._stop_event.is_set()

    @property
    def uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.time() - self._started_at

    # ── Internal Loops ───────────────────────────────────────────

    def _outcome_loop(self) -> None:
        """Periodically call OutcomeTracker.process_pending()."""
        import sys

        # Lazy import — only import when the thread actually starts
        OutcomeTracker = None
        try:
            sys.path.insert(0, str(self.base_dir))
            from runtime.outcome_tracker import OutcomeTracker as _OT
            OutcomeTracker = _OT
        except Exception as ex:
            logger.error(f"Failed to import OutcomeTracker: {ex}")
            return

        try:
            tracker = OutcomeTracker(phoenix_base_dir=self.base_dir)
        except Exception as ex:
            logger.error(f"Failed to instantiate OutcomeTracker: {ex}")
            return

        logger.info("OutcomeTracker loop started")
        consecutive_errors = 0

        while not self._stop_event.wait(timeout=self.check_interval):
            try:
                result = tracker.process_pending()
                consecutive_errors = 0
                if result.get("processed", 0) > 0:
                    logger.debug(
                        f"OutcomeTracker processed={result['processed']}, "
                        f"updated={result.get('updated',0)}"
                    )
                # Record in metrics
                self._record_outcome_process()
            except Exception as ex:
                consecutive_errors += 1
                logger.error(
                    f"OutcomeTracker.process_pending() error #{consecutive_errors}: {ex}"
                )

        logger.info("OutcomeTracker loop exited")

    def _curator_loop(self) -> None:
        """Periodically call SkillCurator.scan()."""
        SkillCurator = None
        try:
            from core.skill_curator import SkillCurator as _SC
            SkillCurator = _SC
        except Exception as ex:
            logger.error(f"Failed to import SkillCurator: {ex}")
            return

        try:
            curator = SkillCurator(phoenix_base_dir=self.base_dir)
        except Exception as ex:
            logger.error(f"Failed to instantiate SkillCurator: {ex}")
            return

        logger.info("SkillCurator loop started")
        consecutive_errors = 0

        while not self._stop_event.wait(timeout=self.curator_interval):
            try:
                report = curator.scan()
                consecutive_errors = 0
                logger.info(
                    f"Curator scan complete: scanned={report.skills_scanned}, "
                    f"updated={report.skills_updated}, quarantined={report.skills_quarantined}"
                )
                # Record in metrics
                self._record_curator_run(report)
            except Exception as ex:
                consecutive_errors += 1
                logger.error(f"SkillCurator.scan() error #{consecutive_errors}: {ex}")

        logger.info("SkillCurator loop exited")

    # ── Metrics recording ────────────────────────────────────────

    def _record_outcome_process(self) -> None:
        try:
            if self._metrics is None:
                from runtime.phoenix_metrics import PhoenixMetrics
                self._metrics = PhoenixMetrics(phoenix_base_dir=self.base_dir)
            self._metrics.record_outcome_process()
        except Exception as ex:
            logger.debug(f"Metrics recording skipped: {ex}")

    def _record_curator_run(self, report) -> None:
        try:
            if self._metrics is None:
                from runtime.phoenix_metrics import PhoenixMetrics
                self._metrics = PhoenixMetrics(phoenix_base_dir=self.base_dir)
            self._metrics.record_curator_run(report)
        except Exception as ex:
            logger.debug(f"Metrics recording skipped: {ex}")


# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import logging as _logging
    import sys

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(description="PhoenixRuntimeDaemon")
    parser.add_argument("base_dir", type=Path, help="Phoenix-Evo base directory")
    parser.add_argument("--check-interval", type=int, default=300, help="OutcomeTracker check interval (sec)")
    parser.add_argument("--curator-interval", type=int, default=3600, help="SkillCurator scan interval (sec)")
    args = parser.parse_args()

    # Start daemon threads (non-blocking; errors logged but don't crash the process)
    try:
        daemon = PhoenixRuntimeDaemon(
            phoenix_base_dir=args.base_dir,
            check_interval=args.check_interval,
            curator_interval=args.curator_interval,
        )
        daemon.start()
        logger.info("PhoenixRuntimeDaemon threads started")
    except Exception:
        logger.exception("Failed to start PhoenixRuntimeDaemon — continuing with HTTP server only")

    # Start FastAPI server for health checks and API
    host = os.environ.get("PHOENIX_HOST", "0.0.0.0")  # noqa: S104
    port = int(os.environ.get("PHOENIX_PORT", "8000"))

    import uvicorn

    logger.info(f"Starting FastAPI server on {host}:{port}")
    try:
        uvicorn.run(get_app(), host=host, port=port, log_level="info")
    except Exception:
        logger.exception("FastAPI server failed to start")
        sys.exit(1)
