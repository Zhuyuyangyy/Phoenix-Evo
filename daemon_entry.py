#!/usr/bin/env python3
"""
Standalone entrypoint for PhoenixRuntimeDaemon + FastAPI health server.

This script is designed to be used as the Docker CMD entrypoint.
It avoids triggering runtime/__init__.py eager imports which can cause
circular import issues. Instead, it imports only what's needed directly.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger("phoenix_daemon")

    parser = argparse.ArgumentParser(description="PhoenixRuntimeDaemon")
    parser.add_argument("base_dir", type=Path, help="Phoenix-Evo base directory")
    parser.add_argument("--check-interval", type=int, default=300)
    parser.add_argument("--curator-interval", type=int, default=3600)
    args = parser.parse_args()

    # Start daemon threads (non-blocking; errors logged but don't crash the process)
    try:
        from runtime.phoenix_daemon import PhoenixRuntimeDaemon

        daemon = PhoenixRuntimeDaemon(
            phoenix_base_dir=args.base_dir,
            check_interval=args.check_interval,
            curator_interval=args.curator_interval,
        )
        daemon.start()
        logger.info("PhoenixRuntimeDaemon threads started")
    except Exception:
        logger.exception("Failed to start PhoenixRuntimeDaemon — continuing with HTTP server only")

    # Start FastAPI server for health checks
    host = os.environ.get("PHOENIX_HOST", "0.0.0.0")  # noqa: S104
    port = int(os.environ.get("PHOENIX_PORT", "8000"))

    try:
        import uvicorn

        from runtime.phoenix_daemon import get_app

        logger.info(f"Starting FastAPI server on {host}:{port}")
        uvicorn.run(get_app(), host=host, port=port, log_level="info")
    except Exception:
        logger.exception("FastAPI server failed to start")
        sys.exit(1)

if __name__ == "__main__":
    main()
