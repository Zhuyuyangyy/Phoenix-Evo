# ─────────────────────────────────────────────────────────────────────────────
# Phoenix-Evo V1.1 Production Dockerfile
# Multi-stage build for optimized production image
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="Phoenix-Evo Team"
LABEL version="1.1.0"
LABEL description="Phoenix-Evo: Self-Evolving Agent Experience Governance System"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/phoenix \
    PHOENIX_BASE_DIR=/phoenix \
    PHOENIX_LOG_LEVEL=INFO \
    PHOENIX_HOST=0.0.0.0 \
    PHOENIX_PORT=8000

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r phoenix && useradd -r -g phoenix -d /phoenix -s /sbin/nologin phoenix

WORKDIR /phoenix

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY core/ /phoenix/core/
COPY runtime/ /phoenix/runtime/
COPY integrations/ /phoenix/integrations/
COPY cli/ /phoenix/cli/
COPY __init__.py /phoenix/
COPY start.sh /phoenix/

# Create data directories
RUN mkdir -p /phoenix/skills/draft \
             /phoenix/skills/active \
             /phoenix/skills/archived \
             /phoenix/skills/quarantine \
             /phoenix/skills/rejections \
             /phoenix/data/trajectories \
             /phoenix/data/benchmarks \
             /phoenix/evidence/skill_cards \
             /phoenix/evidence/replay_reports \
             /phoenix/evidence/runtime_logs \
             /phoenix/logs \
             /phoenix/runtime/fallback_logs

# Set ownership
RUN chown -R phoenix:phoenix /phoenix

# Switch to non-root user
USER phoenix

# ── Ports ────────────────────────────────────────────────────────────────────
# 8000 — PhoenixRuntime HTTP API (FastAPI)
# 9090 — Prometheus metrics scrape endpoint
EXPOSE 8000 9090

# ── Healthcheck ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Volumes ──────────────────────────────────────────────────────────────────
VOLUME ["/phoenix/skills", "/phoenix/data", "/phoenix/evidence", "/phoenix/logs"]

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Use tini for proper signal handling
ENTRYPOINT ["tini", "--"]

# Default: start the PhoenixRuntimeDaemon
CMD ["python", "-m", "runtime.phoenix_daemon", "/phoenix"]
