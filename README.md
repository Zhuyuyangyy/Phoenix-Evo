<p align="center">
  <h1 align="center">Phoenix-Evo</h1>
  <p align="center"><strong>Closed-Loop Agent Experience Governance System</strong></p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python 3.12">
    <img src="https://img.shields.io/badge/FastAPI-0.100+-green" alt="FastAPI">
    <img src="https://img.shields.io/badge/Docker-Supported-2496ED" alt="Docker">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  </p>
</p>

---

## Overview

Phoenix-Evo is an experience governance layer for autonomous agents. Rather than focusing on how an agent completes a task, Phoenix-Evo addresses the problem of how an agent can learn from tasks -- transforming execution trajectories into verified, safety-checked, and reusable skill assets.

Traditional agent frameworks (LangChain, AutoGPT, etc.) concentrate on task execution and discard the experience gained during that process. Phoenix-Evo introduces a closed-loop governance pipeline: every task execution produces a trajectory that is automatically evaluated, mined for reusable skills, verified for safety, subjected to pattern-based filtering, and stored in a governed skill registry. This creates a feedback loop where agents accumulate verified capabilities while a safety system prevents erroneous or dangerous experiences from contaminating the long-term skill corpus.

The system is designed as a middleware layer that sits alongside any agent execution framework. It does not replace the agent's execution logic; instead, it captures, validates, and governs the knowledge produced during execution. The architecture spans five evolutionary stages -- from basic trajectory-to-skill extraction (V0.1) through safety filtering (V0.2), lifecycle governance (V0.3), replay verification (V0.4), and full runtime integration with task lifecycle management, hook systems, and feedback loops (V0.5-V1.0).

## Key Features

- **Closed-Loop Governance Pipeline** -- Pipeline: Trajectory Logging, Post-Task Evaluation, Skill Mining, Verification, Safety Filter, and Registry Storage. Every task execution contributes to the agent's skill corpus with quality checks at each stage.

- **Pattern-Based Safety Filtering** -- Multi-layered safety checks using pattern matching. Detects dangerous operations (destructive commands, financial exploits, injection attacks, deceptive behaviors). Safety memory accumulates failure counts and triggers automatic quarantine after repeated failures.

- **Skill Lifecycle Governance (Curator)** -- Automated lifecycle management including similarity-based deduplication (merge threshold > 0.85), adaptive drift detection with automatic downgrade, archival of unused skills, and quarantine review workflows.

- **Replay Verification** -- Every skill is bound to its source trajectory and supports replay-based validation. Evidence scores are computed from source success, replay pass rate, runtime success rate, usage count, and recency factors.

- **Runtime Safety Gate** -- Eight hard rules evaluated before skill injection: draft/quarantine/archived status denial, evidence score thresholds, risk score limits, replay regression checks, and critical-task safety constraints.

- **Agent Runtime with Hook System** -- Complete task state machine (CREATED, ROUTING, INJECTING, RUNNING, SUCCESS, FAILED, CANCELLED) with 12 lifecycle hook points for extensible monitoring and intervention.

- **Feedback Loop** -- Runtime outcomes automatically flow back through OutcomeTracker and FeedbackDispatcher to update skill metadata, trigger quarantine reviews, and drive quality evolution.

- **Semantic Retrieval (V1.2)** -- Skills are retrieved using sentence-transformers embeddings (all-MiniLM-L6-v2) with cosine similarity, enabling true semantic matching between paraphrased queries and skill descriptions. TF-IDF + cosine similarity retained as a fallback when sentence-transformers is not installed. This addresses the limitation of bag-of-words models in capturing semantic equivalence.

- **Adaptive Drift Detection (V1.1)** -- Success rate and staleness thresholds are computed from the population distribution (mean +/- k*std) rather than fixed constants, enabling the system to adapt to the actual health profile of the skill corpus.

- **CLI and Daemon** -- Command-line interface for status monitoring, skill management, quarantine review, curator operations, daemon control, and metrics inspection.

## Architecture

```
                         +------------------------------------------+
                         |           CLI / API Layer                 |
                         +------------------------------------------+
                                          |
                         +------------------------------------------+
                         |       AgentRuntime (V0.8)                |
                         |  Task Lifecycle + Hooks + TaskStore       |
                         +------------------------------------------+
                                          |
                         +------------------------------------------+
                         |       PhoenixRuntime (V0.6)              |
                         |  SkillRouter -> RuntimeGuard -> Inject   |
                         +------------------------------------------+
                                          |
                         +------------------------------------------+
                         |       Feedback Loop (V0.7)               |
                         |  OutcomeTracker -> FeedbackDispatcher    |
                         +------------------------------------------+
                                          |
         +----------------------------------------------------------------+
         |              Core Governance Engine (V0.1 - V0.4)              |
         |  Trajectory -> Evaluate -> Mine -> Verify -> SafetyFilter     |
         |  -> Registry -> Curator -> Replay -> Evidence                 |
         +----------------------------------------------------------------+
                                          |
                         +------------------------------------------+
                         |       Integration Layer (V0.5)           |
                         |  HermesAdapter -> PhoenixBridge          |
                         +------------------------------------------+
```

### Closed-Loop Pipeline

```
Task Execution
       |
       v
Trajectory Logging
       |
       v
Post-Task Evaluation (rule-based, no LLM dependency)
       |
       v
Skill Mining (extract reusable skill candidate)
       |
       v
Skill Verification (safety + confidence check)
       |
       v
Safety Filter (approve / quarantine / reject)
       |
       v
Skill Registry (stored as draft, pending activation)
       |
       v
Next Task Reuse -> New Trajectory -> Loop
```

### Feedback Loop Data Flow

```
RuntimeReporter (one JSONL record per invocation)
  -> OutcomeTracker (periodic log scanning)
      3+ cumulative failures -> trigger quarantine
  -> FeedbackDispatcher (synchronous dispatch)
      SkillRegistry.record_outcome()
        SkillCard metadata update (usage_count, success_rate, ...)
          Curator.scan() reviews quarantine_skills
            quarantine_skill -> downgrade / delete / restore
```

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.12 |
| Web Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 |
| Database | SQLAlchemy + aiosqlite |
| Numerical Computing | NumPy + SciPy |
| HTTP Client | httpx |
| Monitoring | Prometheus |
| Containerization | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio |

## Quick Start

### Prerequisites

- Python 3.12 or higher
- pip package manager

### Installation

```bash
git clone https://github.com/your-org/Phoenix-Evo.git
cd Phoenix-Evo
pip install -r requirements.txt
```

### Running Demos

```bash
# V0.6: Skill Router runtime demonstration
python runtime/demo_v0.6.py

# V0.7: Feedback loop demonstration
python runtime/demo_v0.7_feedback.py

# V0.8: Agent runtime with full task lifecycle
python runtime/demo_v0.8_agent_runtime.py
```

### Docker Deployment

```bash
docker-compose up -d
```

| Port | Service |
|------|---------|
| 8000 | PhoenixRuntime HTTP API |
| 9090 | Prometheus Metrics |

### CLI Usage

```bash
python -m cli.phoenix_cli status --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli skills list --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli skills activate <skill_id> --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli quarantine review --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli curator run --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli daemon start --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli metrics --base-dir ./Phoenix-Evo
python -m cli.phoenix_cli replay <task_id> --base-dir ./Phoenix-Evo
```

### Code Example

```python
from runtime.agent_runtime import AgentRuntime
from pathlib import Path

runtime = AgentRuntime(phoenix_base_dir=Path("Phoenix-Evo"))
runtime.hooks.on_success(lambda ctx: print(f"Done: {ctx.task_id}"))

ctx = runtime.run(
    task_description="Fix WSL Chinese path encoding",
    task_type="debugging",
    risk_level="low",
    execute_fn=lambda c: fix_path(c.injected_context),
)
# ctx.state == TaskState.SUCCESS
```

## Project Structure

```
Phoenix-Evo/
├── core/                          # Core governance modules
│   ├── phoenix_evo.py             # V0.1 main orchestrator
│   ├── trajectory_logger.py       # Trajectory recording
│   ├── post_task_evaluator.py     # Post-task evaluation
│   ├── skill_miner.py             # Skill extraction
│   ├── skill_verifier.py          # Skill verification (safety layer)
│   ├── skill_registry.py          # Skill registry manager
│   ├── skill_curator.py           # Skill governance (dedup/drift/archive)
│   ├── skill_evidence.py          # Evidence binding
│   ├── skill_replay.py            # Replay verification
│   ├── skill_similarity.py        # Similarity computation (TF-IDF)
│   ├── skill_benchmark.py         # Skill benchmarking
│   ├── immune_guard.py            # Safety filter
│   ├── immune_memory.py           # Safety memory
│   ├── quarantine_manager.py      # Quarantine management
│   ├── replay_manager.py          # Replay management
│   ├── replay_reporter.py         # Replay reporting
│   ├── drift_detector.py          # Adaptive drift detection
│   ├── risk_policy.py             # Risk policy
│   ├── execution_guard.py         # Execution guard
│   ├── curator_policy.py          # Governance policy
│   └── runtime_reporter.py        # Invocation log recorder
├── runtime/                       # Runtime modules
│   ├── phoenix_runtime.py         # Skill Router runtime
│   ├── phoenix_daemon.py          # Background daemon
│   ├── phoenix_metrics.py         # Metrics collection
│   ├── agent_runtime.py           # Task lifecycle manager
│   ├── skill_retriever.py         # Semantic retrieval (TF-IDF + cosine)
│   ├── semantic_retriever.py      # Sentence-embedding retrieval (V1.2)
│   ├── skill_router.py            # Routing decisions (DENY/ALLOW/REVIEW)
│   ├── runtime_guard.py           # Security gate (8 rules)
│   ├── context_injector.py        # Context injection
│   ├── fallback_manager.py        # Fallback strategy
│   ├── outcome_tracker.py         # Task outcome tracking
│   ├── feedback_dispatcher.py     # Feedback dispatch
│   ├── project_router.py          # Project-level routing
│   ├── task_type_classifier.py    # Task type classifier
│   ├── skill_injection_policy.py  # Skill injection policy
│   ├── runtime_skill_bridge.py    # Runtime-skill bridge
│   └── seed_skills.py             # Seed skills
├── integrations/                  # Integration modules
│   ├── hermes_adapter.py          # Hermes event adapter
│   ├── hermes_skill_exporter.py   # Hermes skill exporter
│   ├── phoenix_bridge.py          # Phoenix bridge
│   ├── async_bridge.py            # Async bridge
│   └── integration_policy.py      # Integration policy
├── cli/                           # Command-line interface
│   └── phoenix_cli.py             # CLI entry point
├── skills/                        # Skill storage
│   ├── draft/                     # Candidate skills (pending activation)
│   ├── active/                    # Activated skills
│   ├── archived/                  # Archived skills
│   └── rejections/                # Rejected skills
├── data/trajectories/             # Trajectory history
├── logs/                          # Runtime logs
├── tests/                         # Test suite
│   ├── test_smoke.py              # Smoke tests
│   ├── test_self_evolution_loop.py
│   ├── test_immune_guard.py
│   ├── test_runtime_router.py
│   ├── test_curator.py
│   ├── test_evidence_replay.py
│   ├── test_drift_detector.py
│   ├── test_retrieval_comparison.py
│   └── test_semantic_retrieval.py  # V1.2: Semantic retrieval tests
├── docs/                          # Technical documentation
├── Dockerfile                     # Multi-stage Docker build
├── docker-compose.yml             # Docker Compose orchestration
├── requirements.txt               # Python dependencies
└── start.sh                       # Startup script
```

## Runtime Guard Rules

| # | Rule | Decision |
|---|------|----------|
| 1 | Skill status is draft | DENY |
| 2 | Skill status is quarantine | DENY |
| 3 | Skill status is archived | DENY |
| 4 | evidence_score < 0.60 | DENY |
| 5 | risk_score > 0.50 | DENY |
| 6 | replay_regression = true | DENY |
| 7 | task_risk = critical AND skill_risk != low | DENY |
| 8 | high/critical task AND no replay record | REVIEW_REQUIRED |

## Security Constraints

- Candidate skills are always stored in `skills/draft/` and never auto-activated
- Skills involving deletion, payment, bypass, or attack patterns are rejected by the safety system
- All skills are traceable to their original trajectory
- Automatic modification of active skills is prohibited
- Automatic deletion of skills is prohibited

## Benchmarks & Results

Benchmarks and comparative experiments are defined in the test suite (`tests/test_retrieval_comparison.py`). Formal benchmark results are pending publication.

## Research & Publications

Phoenix-Evo addresses the problem of governing agent-accumulated procedural knowledge:

- **Experience Governance** -- A framework for managing agent-accumulated knowledge with safety guarantees, addressing the gap between task execution and experience reuse in autonomous agents.
- **Pattern-Based Safety Filtering** -- Multi-layer pattern matching and failure memory to prevent experience poisoning in agents that accumulate skills over time.
- **Skill Lifecycle Management** -- Automated governance of skill assets including similarity-based deduplication, adaptive drift detection, evidence-based quality scoring, and replay verification.

Related technical documentation is available in the `docs/` directory, covering the evolution from V0.1 through V1.0.

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| V0.1 | Trajectory to skill extraction | Completed |
| V0.2 | Safety filtering system | Completed |
| V0.3 | Lifecycle governance (merge/drift/archive) | Completed |
| V0.4 | Replay verification and evidence scoring | Completed |
| V0.5 | Hermes integration bridge | Completed |
| V0.6 | PhoenixRuntime skill router | Completed |
| V0.7 | Runtime feedback loop | Completed |
| V0.8 | Agent runtime with task lifecycle | Completed |
| V0.9 | Daemon, metrics, CLI, stability patches | Completed |
| V1.0 | Production-ready: project routing, task classification, namespace governance | Completed |
| V1.1 | Semantic retrieval (TF-IDF), adaptive drift detection | Completed |
| V1.2 | Sentence-embedding semantic retrieval, SCI Q2 review fixes | Completed |
| V1.5 | Engineering baseline: modern type annotations, lint compliance, real LLM experiment infrastructure, enterprise modules | **Current** |

### V1.5 Engineering Baseline (Current Release)

This version is an **engineering modernization + real experiment infrastructure** release, not a major feature release. Key changes:

- **Python 3.12 modern type annotations** across all 176 source files (`Dict`→`dict`, `List`→`list`, `Optional[X]`→`X | None`, `str+Enum`→`StrEnum`)
- **Full ruff lint compliance** with expanded rule set
- **Real LLM experiment infrastructure**: DeepSeek API adapter, PhoenixBench E1-E6 experiment runners, statistical analysis framework (bootstrap CI, Cohen's d, Bonferroni correction)
- **4 new enterprise-grade modules**: `core/distributed` (federated sharing, LRU+TTL cache), `core/enterprise` (RBAC, audit, compliance), `core/multi_agent` (collaboration protocol, consensus), `core/self_repair` (degradation detection, A/B testing)
- **FastAPI health endpoint** on PhoenixRuntimeDaemon for Docker healthcheck support
- **Build artifacts removed from git** (`coverage.xml`, `.phoenix_reproducibility/` added to `.gitignore`)

**Important caveat**: E1 experiment results show ceiling effects (100% success in both conditions), making effectiveness claims preliminary. This release establishes the engineering foundation for future rigorous experimental validation.

### Future Directions

- **V1.3** -- Skill versioning, cross-project skill sharing, automated replay test framework
- **V2.0** -- Multi-agent collaborative evolution with shared safety memory, composite skill generation, adaptive routing
- **Long-term** -- Distributed skill library, federated skill sharing with privacy preservation, self-repairing architecture

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit changes (`git commit -m 'Add your feature'`)
4. Push to remote (`git push origin feature/your-feature`)
5. Create a Pull Request

All new features must include tests. Run `pytest tests/` to ensure all tests pass before submitting. Follow PEP 8 code style. Core module changes require corresponding documentation updates in `docs/`.

## License

This project is licensed under the [MIT License](LICENSE).

---

*"Governance is not about automatically trusting accumulated experience -- it is about automatically verifying, monitoring, and curating it."*
