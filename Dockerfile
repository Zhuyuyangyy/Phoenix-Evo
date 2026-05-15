# ─────────────────────────────────────────────────────────────────────────────
# Phoenix-Evo V1.0 Multi-Stage Dockerfile
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt* /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt 2>/dev/null \
    || pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt 2>/dev/null \
    || echo "No requirements.txt — will install inline below"

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="Phoenix-Evo"
LABEL version="1.0"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PHOENIX_BASE_DIR=/phoenix \
    PHOENIX_LOG_LEVEL=INFO

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /phoenix

# Install Phoenix-Evo Python dependencies (inline)
RUN pip install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn \
    prometheus-client \
    httpx \
    tenacity

# Copy source from builder stage (or from context if available)
# In CI: COPY --from=builder /build /phoenix
# For local dev, the entire project is copied
COPY . /phoenix/

# ── Directory layout ───────────────────────────────────────────────────────────
RUN mkdir -p /phoenix/skills \
             /phoenix/trajectories \
             /phoenix/replays \
             /phoenix/quarantine \
             /phoenix/logs

# ── Ports ────────────────────────────────────────────────────────────────────
# 8000 — PhoenixRuntime HTTP API (FastAPI)
# 9090 — Prometheus metrics scrape endpoint
EXPOSE 8000 9090

# ── Healthcheck ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health \
    || curl -f http://localhost:8000/ \
    || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Default: start the PhoenixRuntimeDaemon
# Override with: docker run ... python -m cli.phoenix_cli status --base-dir /phoenix
ENTRYPOINT ["python", "-m", "runtime.phoenix_daemon"]
CMD ["--help"]
