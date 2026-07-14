# REPRODUCE.md - Phoenix-Evo

## Prerequisites

- **Python**: 3.12+
- **OS**: Linux / macOS / Windows
- **GPU**: Not required
- **SQLite**: Bundled (aiosqlite)

## Install

```bash
cd Phoenix-Evo
pip install -r requirements.txt
```

Dependencies: fastapi, uvicorn, pydantic, sqlalchemy, aiosqlite, httpx, tiktoken, numpy, scipy, pytest, pyyaml

## Smoke Test

```bash
python -m pytest tests/ -v
```

Expected: Tests in `tests/test_benchmark_runner.py`, `tests/test_curator.py`, `tests/test_evidence_replay.py`, `tests/test_immune_guard.py` pass.

## Run Demo

```bash
python demo.py
```

## Run Benchmark

```bash
# Real retrieval benchmark (labeled dataset, real measurements):
python -m experiments.retrieval_benchmark.run_benchmark
# -> experiments/results/retrieval_benchmark_{results.json,report.md}

# Threshold sensitivity analysis:
python -m experiments.retrieval_benchmark.sensitivity
# -> experiments/results/threshold_sensitivity_{results.json,report.md}

# Both run offline (TF-IDF / BM25 / keyword). The embedding column is added
# automatically when sentence-transformers + all-MiniLM-L6-v2 are available.

# Pre-existing benchmark data:
cat data/benchmarks/cases_009_030.json
# Trajectory data in data/trajectories/
```

## Expected Outputs

- Demo execution with self-evolving agent behavior
- Benchmark cases with evaluation scores
- Trajectory JSON files documenting agent evolution

## Known Issues

- Some demo files contain hardcoded `D:/ZYY Project` paths (see `demo_live_fully_working.py`, `demo_live*.py`)
- Runtime `project_router.py` references hardcoded paths
- Trajectory data files contain embedded path references
- tiktoken may require network access for first download

## Evidence Artifacts

- `data/benchmarks/` - Pre-computed benchmark cases
- `data/trajectories/` - Agent execution trajectories
- `docs/` - Documentation and evidence
