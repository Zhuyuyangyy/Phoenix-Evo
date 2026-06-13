# Phoenix-Evo Architecture Documentation

## System Overview

Phoenix-Evo is a self-evolving experience governance layer for autonomous agents. The system implements a closed-loop pipeline that transforms execution trajectories into verified, immune-checked, replay-validated, and safely reusable skill assets.

## Core Architecture Principles

### 1. Self-Evolution Closed Loop

The fundamental architecture follows a closed-loop pattern:

```
Task Execution → Trajectory Logging → Post-Task Evaluation → Skill Mining →
Verification → Immune Guard → Registry Storage → Next Task Reuse → Loop
```

Each task execution produces a trajectory that is automatically evaluated, mined for reusable skills, verified for safety, subjected to immune defense, and stored in a governed skill registry.

### 2. Defense-in-Depth Security

The system implements multiple security layers:

- **Verification Layer**: Pattern-matching for dangerous operations, overgeneralization detection, duplicate checking
- **Immune Guard Layer**: Multi-category risk assessment, immune memory accumulation, automatic quarantine
- **Execution Guard Layer**: Context matching, risk amplification checks, input validation, output safety
- **Fallback Manager**: Automatic degradation on repeated failures

### 3. Evidence-Based Governance

Every skill is bound to its source trajectory and maintains an evidence card tracking:
- Source trajectory IDs
- Verification history
- Replay results
- Quality scores
- Promotion readiness

## Module Architecture

### Core Modules (core/)

#### PhoenixEvo (phoenix_evo.py)
Main orchestrator that manages the complete self-evolution pipeline. Coordinates all other modules.

**Key Responsibilities:**
- Initialize and configure all sub-modules
- Execute the full evolution loop
- Import external trajectories
- Query system status

#### TrajectoryLogger (trajectory_logger.py)
Records task execution trajectories including actions, tool calls, errors, and fixes.

**Key Responsibilities:**
- Log actions, tool calls, errors, fixes
- Generate complete trajectory JSON
- Persist to data/trajectories/

#### PostTaskEvaluator (post_task_evaluator.py)
Rule-based self-evaluator that assesses trajectory quality without LLM dependency.

**Key Responsibilities:**
- Score multiple dimensions (success, errors, fixes, verification, efficiency, repetition)
- Calculate weighted quality score
- Classify failure types
- Decide whether to extract skill

#### SkillMiner (skill_miner.py)
Extracts reusable skill candidates from trajectories.

**Key Responsibilities:**
- Extract inputs, procedure, validation, failure cases
- Generate skill markdown documentation
- Infer skill name from trajectory

#### SkillVerifier (skill_verifier.py)
Validates skill candidates for safety and trustworthiness.

**Key Responsibilities:**
- Check trajectory source credibility
- Assess task type risk
- Scan for dangerous content
- Detect overgeneralization
- Check for duplicates

#### SkillRegistry (skill_registry.py)
Manages skill lifecycle (candidate → draft → active → stale → archived).

**Key Responsibilities:**
- Add draft skills
- Activate skills (requires human approval)
- Archive skills
- Record usage statistics
- Maintain skill index

#### ImmuneGuard (immune_guard.py)
Multi-layered security system inspired by biological immune systems.

**Key Responsibilities:**
- Build risk profiles
- Evaluate dangerous patterns
- Make immune decisions (draft/quarantine/reject)
- Record failures to immune memory

#### RiskPolicy (risk_policy.py)
Defines immune rules metadata: dangerous behavior keywords, high-risk tags, quarantine thresholds.

**Key Responsibilities:**
- Define dangerous patterns by category
- Set risk level thresholds
- Compute immune decisions

#### ImmuneMemory (immune_memory.py)
Maintains historical failure records for "repeat failure immunity."

**Key Responsibilities:**
- Record skill failures
- Track failure counts
- Trigger automatic quarantine after repeated failures

#### QuarantineManager (quarantine_manager.py)
Manages quarantined skills requiring human review.

**Key Responsibilities:**
- Move skills to quarantine directory
- Record quarantine reasons
- Support human review workflow
- Resolve quarantine status

### Curator Modules (V0.3)

#### SkillCurator (skill_curator.py)
Automated lifecycle management including deduplication, drift detection, and archival.

**Key Responsibilities:**
- Periodic skill library scanning
- Similarity-based deduplication
- Drift detection and response
- Governance decision execution

#### SkillSimilarity (skill_similarity.py)
Computes skill similarity using TF-IDF + Cosine similarity.

**Key Responsibilities:**
- Tokenize skill content
- Build TF-IDF vectors
- Compute pairwise similarity
- Group similar skills

#### DriftDetector (drift_detector.py)
Detects skill behavior drift from original specifications.

**Key Responsibilities:**
- Success rate drift detection
- Risk level drift detection
- Usage frequency anomaly detection
- Rapid failure detection

#### CuratorPolicy (curator_policy.py)
Defines governance policies for skill lifecycle management.

**Key Responsibilities:**
- Merge similar skills
- Archive unused skills
- Downgrade degraded skills
- Quarantine problematic skills

### Evidence & Replay Modules (V0.4)

#### SkillEvidenceManager (skill_evidence.py)
Manages skill evidence cards tracking verification history.

**Key Responsibilities:**
- Create and maintain skill cards
- Record replay results
- Track promotion readiness
- Bind additional trajectories

#### SkillBenchmark (skill_benchmark.py)
Manages benchmark cases for skill evaluation.

**Key Responsibilities:**
- Define benchmark cases
- Search by keyword/risk tag
- Score skills against cases

#### SkillReplay (skill_replay.py)
Executes skill replay verification against benchmark cases.

**Key Responsibilities:**
- Replay skills against cases
- Compare with/without skill behavior
- Generate replay reports
- Detect regressions

### Runtime Modules (V0.5)

#### SkillRetriever (skill_retriever.py)
Retrieves relevant skills for current task.

**Key Responsibilities:**
- Multi-path retrieval (keyword + vector + tag)
- Pre-filtering (exclude quarantine/archived)
- Multi-dimensional scoring
- Top-k ranking

#### SkillRouter (skill_router.py)
Makes routing decisions for skill invocation.

**Key Responsibilities:**
- Evaluate evidence scores
- Assess replay pass rates
- Consider risk levels
- Make routing decisions (auto_use/confirm_use/review_first/blocked)

#### ExecutionGuard (execution_guard.py)
Final safety gate before skill invocation.

**Key Responsibilities:**
- Context matching
- Risk amplification checks
- Input validation
- Output safety checks

#### FallbackManager (fallback_manager.py)
Handles skill invocation failures.

**Key Responsibilities:**
- Record failures
- Decide fallback strategies
- Degrade skills on repeated failures
- Update success statistics

#### RuntimeReporter (runtime_reporter.py)
Records runtime invocation results and generates reports.

**Key Responsibilities:**
- Record skill invocations
- Generate runtime reports
- Calculate batch statistics
- Format reports

### Runtime Daemon

#### PhoenixRuntimeDaemon (phoenix_daemon.py)
Background service orchestrating periodic tasks.

**Key Responsibilities:**
- Periodic OutcomeTracker processing
- Periodic SkillCurator scans
- Metrics recording
- Graceful shutdown

## Data Flow

### Evolution Loop Data Flow

```
1. Task Execution
   ↓
2. TrajectoryLogger.complete()
   ↓
3. PostTaskEvaluator.evaluate()
   ↓ (if should_extract)
4. SkillMiner.mine()
   ↓
5. SkillVerifier.verify()
   ↓ (if passed)
6. ImmuneGuard.examine()
   ↓ (if draft)
7. SkillRegistry.add_draft()
   ↓
8. Skill Evidence Manager.create_card()
```

### Runtime Data Flow

```
1. Task Description
   ↓
2. SkillRetriever.retrieve()
   ↓
3. SkillRouter.route()
   ↓
4. ExecutionGuard.check()
   ↓ (if passed)
5. Skill Invocation
   ↓
6. FallbackManager.handle_success/failure()
   ↓
7. RuntimeReporter.create_report()
```

### Curator Data Flow

```
1. Periodic Trigger
   ↓
2. SkillVectorizer.compute_pairwise()
   ↓
3. DriftDetector.analyze_all()
   ↓
4. CuratorPolicy.decide()
   ↓
5. SkillCurator._execute_decision()
```

## Directory Structure

```
Phoenix-Evo/
├── core/                          # Core evolution modules
├── runtime/                       # Runtime modules
├── integrations/                  # Integration modules
├── cli/                           # Command-line interface
├── skills/                        # Skill storage
│   ├── draft/                     # Candidate skills
│   ├── active/                    # Activated skills
│   ├── archived/                  # Archived skills
│   ├── quarantine/                # Quarantined skills
│   └── rejections/                # Rejected skills
├── data/
│   ├── trajectories/              # Trajectory history
│   └── benchmarks/                # Benchmark cases
├── evidence/
│   ├── skill_cards/               # Skill evidence cards
│   ├── replay_reports/            # Replay reports
│   └── runtime_logs/              # Runtime logs
├── logs/                          # System logs
└── tests/                         # Test suite
```

## Configuration

### Module Configuration

PhoenixEvo supports selective module enabling/disabling:

```python
evo = PhoenixEvo.create_configured(
    base_dir="/path/to/phoenix",
    modules={
        "evaluator": True,
        "miner": True,
        "verifier": True,
        "immune_guard": True,
    }
)
```

### Threshold Configuration

Key thresholds are defined in their respective modules:

- **RiskPolicy**: Dangerous patterns, risk tags, repeat failure threshold
- **DriftDetector**: Staleness days, success rate thresholds
- **CuratorPolicy**: Merge threshold, review threshold
- **EvidencePolicy**: Replay pass rate threshold, minimum replay cases
- **ExecutionGuard**: Context match thresholds, destructive patterns
- **FallbackManager**: Consecutive fail threshold, total fail threshold

## Extension Points

### Custom Verifiers

Extend SkillVerifier with custom verification logic:

```python
class CustomVerifier(SkillVerifier):
    def verify(self, skill, trajectory):
        # Custom verification logic
        result = super().verify(skill, trajectory)
        # Additional checks
        return result
```

### Custom Curator Policies

Extend CuratorPolicy with custom governance rules:

```python
class CustomCuratorPolicy(CuratorPolicy):
    def decide(self, similarity_results, drift_reports, similarity_groups):
        decision = super().decide(similarity_results, drift_reports, similarity_groups)
        # Custom governance logic
        return decision
```

### Custom Runtime Hooks

Use the hook system for extensible monitoring:

```python
runtime.hooks.on_success(lambda ctx: custom_success_handler(ctx))
runtime.hooks.on_failure(lambda ctx: custom_failure_handler(ctx))
```
