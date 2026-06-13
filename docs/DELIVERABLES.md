# Phoenix-Evo -- Deliverables Package

**Generated**: 2026-05-29
**Status**: Pre-submission (Major Revision Required)

---

## 1. Paper Status

### Primary Paper (Single Paper Recommendation)

| Field | Value |
|-------|-------|
| **Title** | Governed Skill Memory: Closed-Loop Lifecycle Management for Agent-Extracted Procedural Knowledge |
| **Target Venue** | AAMAS 2027 (Autonomous Agents and Multi-Agent Systems) |
| **Backup Venue** | ICSE 2027 (Software Engineering) |
| **Readiness** | 20% -- Strong architecture, zero experiments |
| **SCI Review Score** | 5.63/10 (Major Revision Required) |

**Core Claim**: Autonomous agents that accumulate procedural knowledge across task executions require active governance to prevent skill degradation, experience poisoning, and knowledge fragmentation. GSM integrates three mechanisms: (1) multi-dimensional drift detection, (2) evidence replay for empirical skill validation, and (3) immune memory for adaptive defense against recurring failure patterns.

**Key Differences from Current Claims**:
- No "self-evolving" -- replaced with "governed lifecycle management"
- No "immune-inspired defense" as standalone -- immune memory is one of three mechanisms
- No "five patentable innovations" -- one coherent framework with three mechanisms
- No biological metaphors in title/abstract -- keep as motivation only

**Contributions**:
1. Formalization of skill lifecycle as a dynamic system (states + transitions + convergence)
2. Multiplicative Skill Trust Score: T(S) = T_ev * T_re * T_rt * T_im (any dimension collapse = total collapse)
3. Closed-loop governance pipeline: Trajectory -> Evaluation -> Mining -> Verification -> Registry -> Runtime -> Outcome -> Drift -> Curator
4. Empirical evidence on real tasks with Claude/GPT agents

---

## 2. Patent Status

| Item | Status | Notes |
|------|--------|-------|
| **Patent Disclosures** | OVERCLAIMED | Claims "five patentable innovations" but each is standard technique with biological metaphor |
| **Filing Recommendation** | DO NOT FILE AS-IS | Current claims lack novelty; would be rejected |
| **Revised Patent Potential** | MEDIUM | After honest reformulation, 2-3 defensible patents possible |

### Honest Patent Assessment

| Current Claim | Reality | Revised Patent Potential |
|---------------|---------|-------------------------|
| "Immune-Inspired Defense" | Keyword blacklist + counter | LOW -- standard content filtering |
| "Evidence-Based Lifecycle" | Provenance tracking + quality metrics | MEDIUM -- if combined with replay verification |
| "Context-Aware Routing" | Keyword matching + weighted scoring | LOW -- Jaccard overlap is prior art |
| "Self-Evolving Mining" | Template-based summarization | LOW -- standard NLP |
| "Metabolic Governance" | TTL-based garbage collection | LOW -- standard cache management |

**Recommendation**: Strip biological metaphors. File patents only after implementing genuinely novel mechanisms (adaptive drift detection, evidence replay with real execution, semantic retrieval).

---

## 3. Dataset Recommendations

### Current Data Assets

| Asset | Size | Status | Limitation |
|-------|------|--------|------------|
| Trajectory files | 70+ files | USABLE | Format undocumented, no relevance judgments |
| Task definitions | 50 tasks, 11 categories | USABLE | Synthetic, not from real agent execution |
| Skill corpus | 8 skills (5 active, 3 archived) | USABLE | Too small for meaningful retrieval evaluation |

### Required Datasets

| Dataset | Purpose | Source | Priority |
|---------|---------|--------|----------|
| **Real agent trajectories** | End-to-end validation | Claude/GPT API execution on real coding tasks | P0 |
| **Human-annotated relevance judgments** | Retrieval benchmark | Manual annotation of query-skill relevance | P0 |
| **Adversarial skill injections** | Poisoning defense evaluation | Manual creation of dangerous/misleading skills | P0 |
| **Voyager skill library** | Baseline comparison | Wang et al., 2023 (public release) | P1 |
| **Reflexion trajectories** | Baseline comparison | Shinn et al., 2023 (public release) | P1 |
| **ExpeL task demonstrations** | Baseline comparison | Zhao et al., 2023 (public release) | P1 |

### Data Generation Plan

1. **Real LLM tasks**: Execute 30+ coding tasks with Claude API, record full trajectories
2. **Relevance judgments**: Annotate 50 queries x 8 skills with binary relevance (2+ annotators, Cohen's kappa)
3. **Adversarial skills**: Create 20+ dangerous skills (command injection, data exfiltration, infinite loops)

---

## 4. GPU / Hardware Requirements

### Current System (TF-IDF + Keyword Matching)

| Component | Requirement |
|-----------|-------------|
| CPU | Any modern x86_64 |
| RAM | < 512 MB |
| GPU | NOT REQUIRED |
| Storage | < 100 MB |

### Planned Upgrades (Semantic Retrieval + Real Experiments)

| Component | Requirement | Purpose |
|-----------|-------------|---------|
| GPU | 1x NVIDIA RTX 3060 or better | Sentence-transformers inference (all-MiniLM-L6-v2) |
| RAM | 8-16 GB | Embedding computation + FAISS index |
| Storage | 10 GB | Model weights + vector index |
| LLM API | Claude API / OpenAI API credits | Real task execution (~$100-200 for 30+ tasks x 5 conditions) |
| Compute Time | ~10-20 GPU-hours | Embedding training + retrieval benchmark |

### Cloud Option

| Provider | Instance | Cost Estimate |
|----------|----------|---------------|
| AWS | g4dn.xlarge (T4) | ~$0.5/hour, ~$10-20 total |
| GCP | n1-standard-4 + T4 | ~$0.4/hour, ~$8-16 total |
| AutoDL | RTX 3060 | ~0.5 RMB/hour, ~10-20 RMB total |

---

## 5. Experiment Plan

### Required Experiments (6 Total)

| # | Experiment | Purpose | Metrics | Baselines | Status |
|---|------------|---------|---------|-----------|--------|
| E1 | End-to-end task performance | Prove GSM improves agent performance | Task success rate, skill reuse rate | Vanilla agent, RAG memory, Reflexion, prompt library | **NOT STARTED** |
| E2 | Ablation study | Prove each mechanism contributes | Task success rate w/o each mechanism | GSM full vs GSM-{drift, replay, immune} | **NOT STARTED** |
| E3 | Experience poisoning defense | Prove immune memory reduces dangerous activations | Dangerous activation rate, FP rate | No defense, keyword-only, GSM full | **NOT STARTED** |
| E4 | Drift detection sensitivity | Prove drift detection catches degradation earlier | Detection latency, precision/recall | Fixed thresholds, CUSUM, GSM adaptive | **NOT STARTED** |
| E5 | Scalability | Prove system scales | Retrieval latency, governance overhead | 100, 500, 1000, 5000 skills | **NOT STARTED** |
| E6 | Real failure case study | Prove problem is real | V0.9.2 zero-success skills analysis | Qualitative analysis | **NOT STARTED** |

### Phase 1: Fix the Foundation (Weeks 1-2)

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| 1.1 | Upgrade retrieval to semantic search | sentence-transformers + FAISS, TF-IDF as fallback | 2-3 days |
| 1.2 | Integrate with real LLM agent | Claude API connection, real task execution | 3-5 days |
| 1.3 | Run E1 baseline experiments | 30+ tasks x 5 conditions, 3+ runs each | 5-7 days |
| 1.4 | Remove overclaimed language | Rewrite all docs, strip biological metaphors | 1 day |

### Phase 2: Strengthen Mechanisms (Weeks 3-4)

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| 2.1 | Implement adaptive drift detection | CUSUM or Bayesian change-point detection | 2-3 days |
| 2.2 | Run E2 ablation experiments | Remove each mechanism, measure impact | 3-4 days |
| 2.3 | Run E3 poisoning defense experiments | Inject adversarial trajectories | 2-3 days |
| 2.4 | Optimize evidence score weights | Bayesian optimization on 5 factors | 2 days |

### Phase 3: Write the Paper (Weeks 5-7)

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| 3.1 | Write Introduction + Related Work | Problem motivation, 5+ system comparisons | 3 days |
| 3.2 | Write Framework section | Formal definitions, Skill Trust Score, lifecycle | 3 days |
| 3.3 | Write Experiments section | All 6 experiments with tables/figures | 3 days |
| 3.4 | Internal review + revision | 2-3 reader feedback | 3 days |

### Statistical Requirements

- 30+ real tasks per condition
- 3+ independent runs per task
- Paired t-test or Wilcoxon signed-rank for pairwise comparisons
- 95% bootstrap confidence intervals
- Cohen's d effect size reporting

---

## 6. Next Actions (Priority Order)

### Immediate (This Week)

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 1 | Upgrade retrieval: sentence-transformers (all-MiniLM-L6-v2) + FAISS | Engineering | Day 3 |
| 2 | Connect to Claude API for real task execution | Engineering | Day 5 |
| 3 | Strip "self-evolving", "immune-inspired", "patentable" from all docs | Research | Day 7 |

### Short-Term (Weeks 1-2)

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 4 | Run E1: 30+ tasks x 5 conditions (vanilla, RAG, Reflexion, prompt lib, GSM) | Research | Week 2 |
| 5 | Implement adaptive drift detection (CUSUM) | Engineering | Week 2 |
| 6 | Add formal Related Work section (Voyager, Reflexion, ExpeL, MemoryBank) | Research | Week 2 |

### Medium-Term (Weeks 3-7)

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 7 | Run E2 ablation + E3 poisoning + E4 drift experiments | Research | Week 4 |
| 8 | Run E5 scalability + E6 case study | Research | Week 4 |
| 9 | Complete paper draft (AAMAS format) | Research | Week 6 |
| 10 | Internal review + revision | Research | Week 7 |

### Patent Action

| # | Action | Status |
|---|--------|--------|
| 1 | DO NOT FILE current patents | Claims are overclaimed |
| 2 | Reformulate after experiments prove genuine novelty | Wait for E1-E4 results |

---

## 7. Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Real experiments show no improvement over baselines | Fatal for paper | Focus on poisoning defense + drift detection as unique contributions |
| Claude API costs exceed budget | Delays experiments | Use smaller task set (15 tasks x 5 conditions) for initial proof |
| Sentence-transformers too slow for production | Weakens practical claim | Use FAISS index with pre-computed embeddings |
| AAMAS deadline missed | Delays publication | Target ICSE 2027 as backup (later deadline) |

---

## 8. Verdict Summary

**One-line verdict**: Phoenix-Evo has a real contribution buried under overclaiming and under-testing. Strip the marketing, upgrade the implementation, run the experiments, and you have a viable AAMAS paper.

**Current readiness**: 20% (strong architecture, zero experiments)
**After Phase 1 fixes**: 50% (real retrieval + real agent integration + baseline experiments)
**After Phase 2 fixes**: 75% (full experiment suite + honest positioning)
**After Phase 3**: 90% (publication-ready)
**Estimated total effort**: 6-8 weeks of focused work

---

## 9. Baseline Systems for Comparison

| System | Type | Source | Relevance |
|--------|------|--------|-----------|
| **Voyager** (Wang et al., 2023) | Skill library for LLM agents | Public | Direct competitor -- skill storage without governance |
| **Reflexion** (Shinn et al., 2023) | Self-reflection and experience learning | Public | Competitor -- unstructured reflections without safety |
| **ExpeL** (Zhao et al., 2023) | Experience learning from demonstrations | Public | Competitor -- experience extraction without lifecycle |
| **Generative Agents** (Park et al., 2023) | Memory in agent simulations | Public | Related -- memory without governance |
| **MemoryBank** (Zhong et al., 2024) | Long-term memory for LLM agents | Public | Related -- memory without safety filtering |
| **LangChain Memory** | Conversation buffer/window | Open source | Weak baseline -- no skill extraction |
| **MemGPT** (Packer et al., 2023) | Hierarchical memory management | Public | Related -- memory management without governance |

---

*Generated from: RESEARCH_VERDICT.md, SCI_REVIEW_Q2.md, debate_critic.md, debate_advocate.md, INNOVATION_ROADMAP.md*
