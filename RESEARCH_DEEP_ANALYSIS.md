# Phoenix-Evo Deep Research Analysis

**Date:** 2026-05-29
**Analyst:** Deep Research Agent
**Subject:** Self-Evolving Agent Experience Governance -- Scientific Problem Analysis

---

## 1. Core Research Problem: What Scientific Problem Does Skill Memory Face in Self-Evolving Agents?

### 1.1 The Problem Statement

The fundamental scientific problem is:

> **How can autonomous agents accumulate, govern, and safely reuse experiential knowledge (procedural skills) across task executions, without suffering from silent skill degradation, experience poisoning, or knowledge fragmentation?**

This is not a traditional continual learning problem (which deals with model weights), not a retrieval problem (which deals with relevance), and not a memory management problem (which deals with storage). It is a distinct problem at the intersection of all three, with a unique constraint: **the knowledge being managed is symbolic, procedural, and safety-critical**.

### 1.2 Why This Problem Is Scientifically Distinct

Phoenix-Evo's architecture reveals that agent skill memory faces at least four interrelated sub-problems that have no unified solution in the existing literature:

**Sub-problem 1: Experience-to-Skill Distillation.** Raw execution trajectories are noisy, redundant, and contain implicit assumptions about the execution environment. The challenge is not merely to store trajectories, but to extract reusable procedural knowledge (skills) that generalizes beyond the original context. Phoenix-Evo's `PostTaskEvaluator` (core/post_task_evaluator.py) implements this as a multi-dimensional scoring function with six weighted dimensions (success, no_error, no_fix, verification, tool_efficiency, no_repeat), with a quality threshold of 0.7 for extraction. The scientific question is: what is the theoretically optimal extraction boundary, and how does it interact with the downstream governance pipeline?

**Sub-problem 2: Skill Quality Verification Without Ground Truth.** Once a skill is extracted, there is no labeled dataset to verify whether it is "correct" in general. Phoenix-Evo's approach is multi-layered: `SkillVerifier` (pattern-matching + rule-based), `ImmuneGuard` (risk profiling + immune memory), and `SkillReplay` (benchmark-case replay). The fundamental difficulty is that verification must be done without access to the future deployment context -- it is an out-of-distribution generalization problem for symbolic knowledge.

**Sub-problem 3: Skill Lifecycle Governance.** Skills are not static assets; they degrade, become redundant, or mutate. Phoenix-Evo's `DriftDetector` monitors four dimensions (success rate drift, risk level drift, usage staleness, rapid failure), and `CuratorPolicy` makes lifecycle decisions (merge, archive, downgrade, quarantine). The scientific question is: can we formalize a "skill metabolism" model analogous to biological metabolism, where the rate of skill creation, degradation, and elimination reaches a dynamic equilibrium?

**Sub-problem 4: Safe Experience Reuse Under Distribution Shift.** A skill that was verified in context A may fail silently in context B. Phoenix-Evo's `ExecutionGuard` attempts to catch this via context-match scoring (word overlap between task goal and skill goal, with block threshold 0.15 and warn threshold 0.30). But this is a surface-level heuristic. The deeper scientific question is: how can an agent detect that the deployment context has drifted from the verification context, without having to fail first?

### 1.3 The Formulation

Let me formalize this as a concrete research problem:

Define a skill as a tuple S = (procedure, inputs, validation, failure_cases, evidence_card). An agent accumulates a skill corpus C = {S_1, S_2, ..., S_n} over time. At each time step t, the agent faces a new task T_t and must decide:

1. Whether to retrieve a skill S_i from C to assist with T_t
2. Whether the retrieved S_i is safe to apply in the current context
3. Whether the outcome of applying S_i should update S_i's evidence card
4. Whether S_i should be promoted, demoted, quarantined, or archived

The optimization objective is to maximize long-term task success rate while minimizing two failure modes:
- **False Acceptance:** applying a dangerous or degraded skill (skill contamination)
- **False Rejection:** discarding a valid skill due to spurious failure signals (catastrophic forgetting of skills)

Phoenix-Evo's entire architecture -- from TrajectoryLogger through ImmuneGuard to Curator -- is a concrete implementation of this optimization. The scientific contribution is the closed-loop governance framework and the specific mechanisms (evidence replay, immune memory, drift detection) that make it tractable.

---

## 2. Why Existing Methods Cannot Solve This

### 2.1 RAG (Retrieval-Augmented Generation)

RAG retrieves relevant documents from a corpus and injects them into the LLM context. This is fundamentally insufficient for agent skill memory for three reasons:

**No quality governance.** RAG uses similarity-based retrieval (cosine similarity, BM25) with no concept of document quality, safety, or lifecycle. A dangerous or outdated document scores equally well if it is semantically relevant. Phoenix-Evo's `SkillRetriever` (runtime/skill_retriever.py) adds multi-dimensional scoring: keyword match + evidence_score + replay_pass_rate + risk_level, with a routing decision engine that classifies skills into auto_use / confirm_use / review_first / blocked. RAG has no equivalent.

**No experience poisoning defense.** If a poisoned document enters the RAG corpus, it will be retrieved and used indefinitely. There is no immune system. Phoenix-Evo's `ImmuneGuard` implements eight dangerous pattern categories (privilege_escalation, data_theft, destruction, network_attack, privacy_violation, payment_fraud, persistence, ai_harm) with keyword-based detection and immune memory accumulation. After 3 failures of the same pattern, the skill is automatically quarantined. RAG has no such mechanism.

**No lifecycle management.** RAG corpora are append-only. Documents are never deprecated, merged, or archived. Phoenix-Evo's `SkillCurator` implements automated lifecycle management: similarity-based deduplication (merge threshold > 0.60), drift detection, and automated governance decisions (merge, archive, downgrade, quarantine). Over time, a RAG corpus accumulates stale, redundant, and conflicting documents with no mechanism to resolve them.

### 2.2 Agent Memory Systems (MemGPT, Reflexion, Generative Agents)

Modern agent memory systems address a related but distinct problem:

**MemGPT** manages a hierarchical memory (working memory + archival memory) for a single agent session. It solves the context window limitation but has no concept of skill verification, immune defense, or lifecycle governance. Skills in MemGPT are just text entries; there is no evidence binding, no replay validation, no drift detection.

**Reflexion** stores self-reflections as verbal reinforcement signals. These reflections are plain text with no structured format, no safety checking, and no deduplication. A Reflexion agent can accumulate contradictory reflections over time with no mechanism to resolve them. Phoenix-Evo's `SkillCard` (core/skill_evidence.py) binds each skill to structured evidence: source_trajectory_ids, replay_pass_count, replay_fail_count, promotion_ready status. This is a fundamentally richer representation.

**Generative Agents** (Park et al., 2023) store observations and reflections in a retrieval stream. The memory has a recency + importance + relevance scoring function, but no safety governance, no quality verification, and no lifecycle management. A generative agent's memory can accumulate dangerous or false observations with no mechanism to quarantine them.

The key distinction: existing agent memory systems treat all memories as equally valid. Phoenix-Evo introduces the concept of **governed memory** where every memory (skill) must pass through a multi-layer security pipeline before it can influence agent behavior, and continues to be monitored after activation.

### 2.3 Fine-Tuning

Fine-tuning embeds experiential knowledge into model weights. This has three fatal flaws for agent skill memory:

**Catastrophic forgetting.** Fine-tuning on new skills degrades old skills. There is no selective mechanism to preserve specific skills while updating others. Phoenix-Evo's skill corpus is external to the model; skills are stored as structured documents in a registry, not as weight modifications. Adding a new skill never degrades existing skills.

**No auditability.** Fine-tuned knowledge is distributed across billions of parameters and cannot be inspected, audited, or selectively removed. Phoenix-Evo's skills are human-readable markdown files with explicit provenance (source trajectory), verification history (evidence card), and lifecycle status (draft/active/archived/quarantined). Every skill decision is traceable.

**No safety governance.** Fine-tuning on dangerous experiences permanently embeds those experiences in the model. There is no immune system to prevent dangerous knowledge from being learned. Phoenix-Evo's ImmuneGuard intercepts dangerous experiences before they enter the skill corpus.

### 2.4 Prompt Engineering

Prompt engineering encodes experiential knowledge as instructions in the system prompt. This has fundamental scalability and governance limitations:

**Context window bottleneck.** As skills accumulate, they cannot all fit in the system prompt. There is no mechanism to select which skills are most relevant to the current task. Phoenix-Evo's SkillRetriever performs multi-path retrieval (keyword + vector + tag) to select the most relevant skills.

**No lifecycle management.** Prompt instructions are static. They are never updated based on execution outcomes, never deprecated when they become stale, and never deduplicated when they overlap. Phoenix-Evo's OutcomeTracker and FeedbackDispatcher create a closed feedback loop where every execution outcome updates skill metadata.

**No safety governance.** Any instruction can be added to the system prompt, including dangerous ones. There is no verification or immune defense. Phoenix-Evo's multi-layer security pipeline (Verifier + ImmuneGuard + ExecutionGuard + RuntimeGuard) provides defense-in-depth.

---

## 3. Key Technical Contradictions

### 3.1 Plasticity vs. Stability

This is the classical dilemma from continual learning, manifested differently in agent skill memory:

**In neural networks:** plasticity means the ability to learn new patterns; stability means retaining old patterns. The tension is mediated by weight regularization (EWC, SI), rehearsal (experience replay), or architectural isolation (progressive neural networks).

**In agent skill memory:** plasticity means the ability to extract and activate new skills from each task execution; stability means preventing the skill corpus from being corrupted by erroneous or context-specific experiences. The tension manifests as:

- If the extraction threshold is too low (high plasticity), the corpus floods with low-quality skills, including overgeneralized ones (Phoenix-Evo detects this: `procedure_step_count < 2` triggers overgeneralization quarantine in risk_policy.py line 121).
- If the extraction threshold is too high (high stability), the agent fails to learn from valid experiences, remaining in a static state.
- If the activation gate is too permissive, dangerous skills enter the active corpus.
- If the activation gate is too restrictive, valid skills are perpetually stuck in draft.

Phoenix-Evo's approach is a **multi-stage gated pipeline**:

```
Trajectory -> Evaluator (quality > 0.7) -> Verifier (6 checks) -> ImmuneGuard (8 risk categories)
-> Draft -> Replay (pass rate >= 70%) -> Active
```

Each stage has a different plasticity-stability tradeoff:
- Evaluator: favors plasticity (extract if quality > 0.5 with fixes)
- ImmuneGuard: favors stability (reject on any high-risk tag)
- Replay: balanced (promote if pass rate >= 70% AND no regression AND risk_delta <= 0)

The scientific question is: **can we formulate an optimal gating policy that maximizes long-term cumulative reward (task success) while bounding the risk of skill contamination?** This is a constrained optimization problem that could be approached via constrained MDP or Bayesian optimization.

### 3.2 Memory Reuse vs. Skill Contamination

This is the central safety tension:

**Memory reuse** is the core value proposition of agent skill memory. A skill that was extracted from task T_1 and successfully applied to tasks T_2, T_3, ..., T_k represents a cumulative efficiency gain. The more a skill is reused, the higher its evidence_score, and the more confidently it can be applied.

**Skill contamination** occurs when a flawed skill is repeatedly applied, reinforcing the flawed pattern. This is a positive feedback loop: the skill gets more usage, its evidence_score increases, it gets applied more frequently, and the failures accumulate. Phoenix-Evo's `OutcomeTracker` (runtime/outcome_tracker.py) detects this via the `consecutive_failures` counter: after 2 consecutive failures, the skill is flagged for replay; after 3, it is flagged for review; after risk incidents exceed threshold, it is quarantined.

The deeper issue is **silent contamination**: a skill that works 80% of the time but causes subtle damage in the remaining 20%. The damage may not be immediately apparent (e.g., a file-writing skill that occasionally corrupts encoding). Phoenix-Evo's evidence score includes a `runtime_success_rate` component (weight 0.20) that tracks this over time, but the detection latency is proportional to the failure rate -- rare failures take longer to detect.

### 3.3 Generalization vs. Specificity

Skills must be general enough to apply to new tasks but specific enough to be safe and effective:

**Over-generalized skills** (detected by Phoenix-Evo's `overgeneralized` property: `procedure_step_count < 2`) are vague instructions that could apply to anything but help with nothing. Example: "Always verify your output" -- universally true but operationally useless.

**Over-specific skills** are tied to a single context and fail to transfer. Phoenix-Evo's `ExecutionGuard` detects this via context_match_score: if the task goal and skill goal share fewer than 15% of words, the skill is blocked.

The sweet spot is a skill that captures the **procedural essence** of a task type, with explicit inputs, steps, validation, and failure cases. Phoenix-Evo's `SkillMiner` extracts these structured components from trajectories, but the quality of extraction depends on the trajectory's completeness and the evaluator's scoring function.

---

## 4. What Is Irreplaceable About This Approach

### 4.1 Skill Drift Detection (core/drift_detector.py)

Phoenix-Evo's DriftDetector monitors four independent drift dimensions:

1. **Success rate drift:** `success_rate < 0.50` triggers critical severity. This detects skills that are silently failing.
2. **Risk level drift:** If `current_risk > initial_risk`, the skill has become more dangerous over time. This detects skills that accumulate side effects.
3. **Usage staleness:** Skills unused for > 30 days are flagged. This detects skills that are no longer relevant to the task distribution.
4. **Rapid failure:** If `usage_count >= 3 AND success_count == 0`, the skill is critically failing. This detects skills that were extracted from atypical successful trajectories.

**Why this is irreplaceable:** No other agent memory system performs multi-dimensional health monitoring of its own knowledge base. RAG does not track whether its documents are becoming stale. Fine-tuning does not track whether its learned knowledge is degrading. Prompt engineering does not track whether its instructions are becoming counterproductive. This is a **meta-cognitive capability** -- the agent's ability to monitor the quality of its own knowledge.

The DriftDetector produces `SkillHealthReport` objects with severity levels (stable/warning/drift/critical) and actionable recommendations. These reports feed into the CuratorPolicy, which makes automated governance decisions. This creates a **self-healing knowledge base** that can detect and respond to its own degradation.

### 4.2 Evidence Replay (core/skill_replay.py)

Evidence replay is the mechanism that bridges the gap between offline verification and online performance:

**The gap:** A skill can pass all offline checks (pattern matching, risk assessment, deduplication) but still fail in deployment because the verification context was not representative of the deployment context.

**Phoenix-Evo's solution:** Replay the skill against benchmark cases and compare with/without-skill behavior. The `SkillReplay.replay()` method (core/skill_replay.py lines 227-343) computes four delta metrics:
- `success_delta`: does the skill improve task success?
- `error_delta`: does the skill reduce errors?
- `risk_delta`: does the skill increase risk?
- `step_delta`: does the skill reduce execution steps?

**Why this is irreplaceable:** This is the only mechanism in any agent framework that provides **empirical validation of skill quality through controlled experimentation**. It is analogous to A/B testing in software engineering, but applied to agent knowledge. The EvidencePolicy (core/skill_replay.py lines 89-200) uses these replay results to make promotion decisions:

- `replay_pass_rate >= 0.70 AND no regression AND risk_delta <= 0 AND evidence_complete` -> promote
- `regression_found == True` -> quarantine
- `replay_pass_rate < 0.70` -> quarantine
- `risk_delta > 0.05` -> quarantine

This creates a **meritocratic skill corpus** where skills earn their place through demonstrated performance, not merely through extraction from a successful trajectory.

### 4.3 Immune Memory (core/immune_memory.py)

Phoenix-Evo's immune memory is a novel mechanism for detecting recurring failure patterns:

**How it works:** When a skill fails the ImmuneGuard examination (decision = quarantine or reject) AND has high-risk tags, the failure is recorded in `immune_memory.json` with a fingerprint (skill_name[:40] + sorted risk tags). When the same fingerprint accumulates >= 3 failures, all future skills matching that fingerprint are automatically quarantined.

**Why this is irreplaceable:** This is the only mechanism that provides **cross-skill failure pattern recognition**. It is not tracking individual skill failures; it is tracking failure *patterns* across different skills. If multiple different skills with the same risk tags (e.g., "privilege_escalation") keep being extracted from trajectories, the immune system learns that this entire category of experience is toxic and preemptively quarantines new instances.

This is directly inspired by the biological adaptive immune system, where B-cells and T-cells develop memory of specific pathogens. The analogy is precise:
- **Antigen** = dangerous skill pattern (risk tags + skill name prefix)
- **Antibody** = immune memory record (failure count + quarantine flag)
- **Immune response** = automatic quarantine when failure count >= threshold

### 4.4 The Closed Feedback Loop

The most irreplaceable aspect of Phoenix-Evo is not any single component, but the **closed-loop architecture**:

```
Task Execution -> Trajectory -> Evaluation -> Mining -> Verification -> Immune Guard
-> Skill Registry -> Runtime Retrieval -> Execution -> Outcome Tracking -> Feedback
-> Drift Detection -> Curator Governance -> Skill Registry Update -> Next Task
```

No other agent framework implements this complete loop. The closest analog is the biological immune system's clonal selection + affinity maturation cycle, where:
- Successful antibodies are amplified (skill promotion)
- Failed antibodies are eliminated (skill quarantine)
- The antibody repertoire evolves over time (skill corpus governance)

This closed loop is what enables **self-healing**: the system can detect its own failures (via OutcomeTracker), diagnose the root cause (via DriftDetector), and take corrective action (via CuratorPolicy) -- all without human intervention, except for edge cases that require human review (via ReviewAction).

---

## 5. Strongest Baselines

### 5.1 Baseline 1: Vanilla Agent with RAG Memory

**Implementation:** An agent that stores execution trajectories in a vector database and retrieves the top-k most similar trajectories for each new task. No verification, no immune defense, no lifecycle management.

**Expected failure modes:**
- Retrieves dangerous trajectories (e.g., containing `rm -rf`) for similar-looking tasks
- Retrieves stale trajectories that no longer apply to the current environment
- Accumulates redundant and conflicting trajectories over time
- No mechanism to detect or correct retrieval failures

**Phoenix-Evo advantage:** Multi-layer security (Verifier + ImmuneGuard + ExecutionGuard), lifecycle governance (Curator), drift detection, evidence replay.

### 5.2 Baseline 2: Fine-Tuned Agent

**Implementation:** An agent that fine-tunes its model on execution trajectories after each task. Uses LoRA or full fine-tuning.

**Expected failure modes:**
- Catastrophic forgetting: new skills overwrite old skills
- No auditability: cannot inspect what was learned
- No safety governance: dangerous experiences are permanently encoded
- High computational cost: requires GPU for each update
- No selective unlearning: cannot remove a specific dangerous skill

**Phoenix-Evo advantage:** External skill corpus (no catastrophic forgetting), human-readable skills (full auditability), ImmuneGuard (safety governance), lightweight (no GPU required), selective lifecycle management.

### 5.3 Baseline 3: Prompt-Engineered Agent with Skill Library

**Implementation:** An agent that maintains a library of skill instructions in markdown format and injects relevant skills into the system prompt. Skills are manually curated by humans.

**Expected failure modes:**
- Does not scale: manual curation cannot keep up with task volume
- No automatic quality assessment: human curators may miss subtle errors
- No drift detection: stale skills remain in the library indefinitely
- No feedback loop: execution outcomes do not update skill quality
- Context window limitation: only a few skills can be injected at a time

**Phoenix-Evo advantage:** Automatic skill extraction and verification, automated lifecycle governance, drift detection, closed feedback loop, intelligent retrieval (top-k selection).

### 5.4 Baseline 4: Reflexion Agent

**Implementation:** An agent that generates natural language self-reflections after task failures and stores them for future reference.

**Expected failure modes:**
- Reflections are unstructured natural language with no safety checking
- No deduplication: the same reflection can be stored multiple times
- No quality governance: a wrong reflection is stored with equal weight as a correct one
- No lifecycle management: reflections are never deprecated or updated
- Contradictory reflections can coexist without resolution

**Phoenix-Evo advantage:** Structured skill representation (inputs, procedure, validation, failure_cases), ImmuneGuard (safety checking), Curator (deduplication and lifecycle), DriftDetector (quality monitoring), EvidencePolicy (promotion governance).

### 5.5 Comparative Summary

| Dimension | RAG Memory | Fine-Tuning | Prompt Library | Reflexion | Phoenix-Evo |
|-----------|-----------|-------------|----------------|-----------|-------------|
| Experience format | Raw text | Model weights | Markdown instructions | Natural language | Structured skill + evidence card |
| Safety governance | None | None | Manual | None | Multi-layer automated |
| Quality verification | None | Training loss | Manual | None | Replay + evidence scoring |
| Lifecycle management | Append-only | Overwrite | Manual | Append-only | Automated (Curator) |
| Drift detection | None | None | None | None | 4-dimensional |
| Feedback loop | None | Implicit (loss) | None | Partial (reflection) | Complete (OutcomeTracker) |
| Catastrophic forgetting | N/A | Severe | N/A | N/A | None (external corpus) |
| Auditability | Low | None | High | Medium | High (full provenance) |
| Scalability | High | Low (GPU) | Low (manual) | High | High |

---

## 6. Failure Cases That Prove the Problem Is Real

### 6.1 Case Study: The Zero-Success Skills (V0.9.2 Feedback Report)

The V0.9.2 real task feedback report (docs/v0_9_2_real_task_feedback_report.md) reveals a critical failure pattern:

```
signature_first_debugging: success=0
error_message_as_contract_signal: success=0
demo_repair_workflow: success=0
```

These three skills were extracted from successful trajectories (they passed the PostTaskEvaluator with quality > 0.7), passed the SkillVerifier (no dangerous patterns, not overgeneralized), and were stored in the skill registry as active skills. However, when deployed in the real runtime, they achieved zero successes.

**What this proves:**
1. **Offline verification is insufficient.** A skill can pass all automated checks and still fail in deployment. This is the fundamental motivation for evidence replay.
2. **The feedback loop is essential.** Without the OutcomeTracker recording these failures, the system would never detect that these skills are broken. The DriftDetector would eventually flag them (success_rate = 0.0 triggers critical severity after MIN_USAGE_FOR_DRIFT = 3 uses), but only after causing damage.
3. **The gap between extraction context and deployment context is real.** These skills were extracted from specific trajectories with specific tool configurations, but deployed in a different runtime environment (Hermes integration). The skills' procedures were context-dependent in ways that the extraction process did not capture.

**Phoenix-Evo's response:** The OutcomeTracker detected the consecutive failures and triggered the Curator's drift detection, which flagged these skills for quarantine. This is the self-healing mechanism in action -- but it is inherently reactive (damage must occur before correction).

### 6.2 Case Study: The Silent Contamination Scenario

Consider a hypothetical but realistic scenario that Phoenix-Evo's architecture is designed to prevent:

A coding agent extracts a skill "write_file_with_encoding" from a successful trajectory where it wrote a Python file with UTF-8 encoding. The skill passes all checks: quality > 0.7, no dangerous patterns, 3 procedure steps, evidence card created. It is promoted to active.

However, the skill's procedure says "write content to file path" without specifying encoding. When applied to a task involving Chinese characters on a WSL filesystem, the default encoding (locale-dependent) may produce null bytes -- exactly the bug that CASE-001 in Phoenix-Bench was designed to test.

**Without Phoenix-Evo:** The skill is applied, the file is written with encoding errors, and the corruption is not detected until much later. The skill continues to be applied to similar tasks, silently corrupting files.

**With Phoenix-Evo:** The OutcomeTracker records the failure. After 2 consecutive failures, the skill is flagged for replay. The DriftDetector detects success_rate drift. The CuratorPolicy quarantines the skill. The next time a similar task arrives, the quarantined skill is not injected, and the agent falls back to manual execution.

### 6.3 Case Study: The Immune Memory Accumulation

Phoenix-Evo's test suite (tests/test_immune_guard.py) reveals the immune memory mechanism:

When a skill candidate contains "sudo rm" (a destruction pattern), the ImmuneGuard rejects it and records the failure in ImmuneMemory. If the same agent keeps extracting skills with "sudo rm" from different trajectories (perhaps the agent has a bad habit of using destructive commands), the immune memory accumulates failures. After 3 failures matching the same fingerprint (skill_name[:40] + sorted risk tags), ALL future skills matching that fingerprint are automatically quarantined -- even if they pass the SkillVerifier.

**What this proves:**
1. **Pattern-level learning is possible.** The immune system learns not just from individual skill failures but from failure patterns across skills.
2. **Defense must be adaptive.** Static rule-based filtering (like keyword blocklists) cannot anticipate all dangerous patterns. The immune memory adapts to the specific failure patterns of a particular agent.
3. **The cost of false negatives is high.** A single dangerous skill that slips through the ImmuneGuard can cause cascading damage. The immune memory provides an escalating defense: the more the system sees a pattern, the more aggressively it blocks it.

### 6.4 Case Study: The Drift Detection Threshold Problem

Phoenix-Evo's DriftDetector uses fixed thresholds:
- `SUCCESS_RATE_WARNING = 0.70`
- `SUCCESS_RATE_CRITICAL = 0.50`
- `STALENESS_DAYS = 30`
- `MIN_USAGE_FOR_DRIFT = 3`

These thresholds are calibrated by engineering judgment, not by data. Consider a skill that starts with success_rate = 0.95 and gradually degrades: 0.95 -> 0.90 -> 0.85 -> 0.80 -> 0.75 -> 0.70 (warning) -> 0.65 -> 0.60 -> 0.55 -> 0.50 (critical).

The DriftDetector only triggers a warning when success_rate drops below 0.70, and only triggers critical at 0.50. This means the skill can degrade from 0.95 to 0.71 without any intervention -- a 25% performance drop that goes undetected.

**What this proves:**
1. **Static thresholds are insufficient.** The detection sensitivity should adapt to the skill's historical performance distribution, not use fixed cutoffs.
2. **Early warning is critical.** By the time success_rate drops to 0.50, significant damage may have been done. The system needs anomaly detection, not just threshold crossing.
3. **The optimal threshold depends on the cost of false positives vs. false negatives.** In safety-critical domains (e.g., medical AI), the threshold should be much higher (e.g., 0.90). In exploratory domains, it can be lower.

This is a concrete scientific problem: **how to set adaptive drift detection thresholds that minimize the total cost of false positives (quarantining good skills) and false negatives (failing to detect degrading skills)?**

---

## 7. SCI Paper Topic Suggestions

### Paper 1: "Skill Metabolism: A Formal Framework for Lifecycle Governance of Agent-Extracted Procedural Knowledge"

**Venue:** NeurIPS 2026 or ICLR 2027 (Agent/Tool Use track)

**Core contribution:** Formalize the concept of "skill metabolism" -- the dynamic process by which an agent's skill corpus is created, verified, activated, monitored, degraded, and eliminated. Define a Markov Decision Process (MDP) over the skill lifecycle states (draft, active, stale, degraded, quarantined, archived, rejected) and prove that Phoenix-Evo's CuratorPolicy is an approximately optimal policy under certain assumptions.

**Key results:**
- Formal definition of skill corpus health as a function of creation rate, degradation rate, and elimination rate
- Proof that a closed feedback loop (OutcomeTracker -> DriftDetector -> CuratorPolicy) converges to a stable skill corpus under mild assumptions
- Ablation study using Phoenix-Bench (30 cases, 5 groups) showing that each governance component (Verifier, ImmuneGuard, Replay, Curator) contributes measurably to task success rate
- Comparison against RAG, fine-tuning, and prompt engineering baselines

**Novelty:** First formal treatment of agent skill lifecycle governance as a dynamic system. Existing work on continual learning focuses on model weights; this paper focuses on symbolic procedural knowledge with explicit lifecycle states.

### Paper 2: "Immune-Inspired Defense Against Experience Poisoning in Self-Evolving Agents"

**Venue:** AAMAS 2027 (Autonomous Agents and Multi-Agent Systems) or AAAI 2027 (AI Safety track)

**Core contribution:** Introduce the concept of "experience poisoning" -- the injection of dangerous or erroneous experiences into an agent's skill corpus -- and propose an immune-inspired multi-layer defense system. Formalize the analogy between biological immune mechanisms and agent experience governance:

| Biological Immune | Agent Immune (Phoenix-Evo) |
|---|---|
| Innate immunity (pattern recognition) | SkillVerifier (keyword pattern matching) |
| Adaptive immunity (antigen-specific response) | ImmuneMemory (failure pattern accumulation) |
| Immune tolerance (self/non-self discrimination) | EvidencePolicy (verified/unverified discrimination) |
| Clonal selection (amplify successful antibodies) | Skill promotion (amplify successful skills) |
| Immune memory (remember past pathogens) | ImmuneMemory.json (remember past failure patterns) |
| Autoimmune disease (attack self) | False rejection (quarantine valid skills) |

**Key results:**
- Formal definition of experience poisoning attack vectors (adversarial trajectory injection, subtle skill corruption, distribution shift exploitation)
- Multi-layer defense model with provable containment guarantees under specific attack models
- Empirical evaluation showing that the immune system reduces dangerous skill activation by > 90% compared to no-immune baselines
- Analysis of the false positive rate (valid skills quarantined) and the cost of human review

**Novelty:** First application of immunological theory to agent experience governance. Existing AI safety work focuses on alignment at the model level; this paper focuses on safety at the knowledge level.

### Paper 3: "Evidence Replay: Empirical Validation of Agent-Extracted Skills Through Controlled Re-execution"

**Venue:** ICML 2027 or ACL 2027 (Agent/Tool Use track)

**Core contribution:** Introduce "evidence replay" as a mechanism for validating agent-extracted skills through controlled re-execution against benchmark cases. Define a formal model of skill quality as a function of replay performance:

```
evidence_score(S) = w_1 * source_success(S) + w_2 * replay_pass_rate(S)
                  + w_3 * runtime_success_rate(S) + w_4 * usage_count_norm(S)
                  + w_5 * recency_factor(S)
```

where the weights w_1...w_5 are calibrated to maximize the correlation between evidence_score and actual deployment success rate.

**Key results:**
- Formal definition of evidence replay as a hypothesis testing problem: H0 (skill is harmful) vs. H1 (skill is beneficial)
- Optimal number of replay cases required to achieve a target confidence level (derived from sequential testing theory)
- Empirical demonstration that evidence_score is a better predictor of deployment success than alternative metrics (source trajectory quality, similarity to existing skills, human expert judgment)
- Analysis of the replay gap: the difference between replay performance and deployment performance, and how to minimize it

**Novelty:** First formal treatment of skill validation through controlled re-execution. Existing work on agent evaluation focuses on task-level metrics; this paper focuses on skill-level validation with formal statistical guarantees.

---

## 8. Summary

Phoenix-Evo addresses a scientifically genuine and practically important problem: **how to make agent-accumulated knowledge safe, reliable, and self-improving over time.** The problem is genuine because:

1. Agents will inevitably accumulate experiential knowledge as they execute tasks.
2. This knowledge will inevitably include errors, outdated information, and context-dependent procedures.
3. Without governance, this knowledge will cause cascading failures as it is reused.

The existing approaches (RAG, fine-tuning, prompt engineering, Reflexion) each address a fragment of the problem but none provides a complete solution. Phoenix-Evo's contribution is the **closed-loop governance framework** with specific mechanisms (drift detection, evidence replay, immune memory, curator policy) that together create a self-healing knowledge base.

The three proposed SCI papers formalize the key scientific contributions:
1. **Skill Metabolism** -- the dynamic lifecycle of agent knowledge (systems theory contribution)
2. **Immune-Inspired Defense** -- the security of agent knowledge (AI safety contribution)
3. **Evidence Replay** -- the validation of agent knowledge (empirical methodology contribution)

---

*"Self-evolution is not about automatically trusting oneself -- it is about automatically doubting, verifying, and consolidating oneself."*
-- Phoenix-Evo Design Philosophy
