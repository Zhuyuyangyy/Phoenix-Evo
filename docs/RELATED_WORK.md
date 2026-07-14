# Related Work and Positioning

This document provides the formal related-work positioning requested in the
Q2 SCI review (Round 3 finding: "No formal citations added. No comparison
with Voyager, Reflexion, ExpeL, MemoryBank."). It is written to be lifted
into Section 2 of the paper with minimal editing.

Phoenix-Evo's paper-facing name for the framework is **Governed Skill Memory
(GSM)**: closed-loop lifecycle management for agent-extracted procedural
knowledge (extraction → verification → activation → monitoring → retirement).

---

## 1. Agent Skill and Experience Memory Systems

**Voyager** (Wang et al., 2023) [1] introduced the skill library for LLM
agents: verified Minecraft programs are stored and retrieved by embedding
similarity for reuse. Voyager validates a skill once, at acquisition time,
by executing it in the environment. GSM differs in three ways: (i) skills
are *governed after* acquisition — success-rate drift, staleness, and risk
are monitored continuously and skills can be quarantined or retired; (ii)
acquisition-time verification is complemented by *evidence replay*
(with-skill vs. without-skill comparison) rather than a single execution
check; (iii) Voyager assumes a benign, closed world (a game), while GSM's
immune layer explicitly models poisoned or dangerous experience entering
the corpus.

**Reflexion** (Shinn et al., 2023) [2] stores verbal self-reflections in an
episodic memory buffer to improve subsequent trials of the same task.
Reflections are unstructured natural-language text, are never verified, and
accumulate without lifecycle management. GSM stores *structured procedural
skills* with preconditions, applicability conditions, and evidence scores,
and every stored artifact carries a trust state that can be revoked.

**ExpeL** (Zhao et al., 2024) [3] extracts cross-task insights and rules
from pooled trajectories and injects them at inference time. Like GSM, it
mines reusable knowledge from experience; unlike GSM, extracted insights
are append-only — there is no verification, no deprecation, and no defense
against extracting the wrong lesson from a poisoned trajectory.

**Generative Agents** (Park et al., 2023) [4] maintain a memory stream
scored by recency, importance, and relevance for social simulation. The
memory is declarative (observations, reflections), not procedural, and the
scoring governs *retrieval priority*, not *trustworthiness*.

**MemoryBank** (Zhong et al., 2024) [5] adds Ebbinghaus-inspired forgetting
to long-term conversational memory. Its lifecycle mechanism (decay by time
and revisit frequency) is the closest prior to GSM's staleness handling,
but it manages declarative dialogue memory, applies no correctness or
safety checks, and its forgetting curve is time-driven rather than
outcome-driven. GSM retires skills based on *measured deployment outcomes*
(success-rate drift), not elapsed time alone.

**Agent Workflow Memory** (Wang et al., 2024) [6] induces reusable
workflows from web-navigation trajectories and injects them into the agent
context — the closest prior work to GSM's skill mining stage. AWM's
workflows, however, enter memory without verification and remain there
indefinitely; AWM reports no mechanism for detecting that an induced
workflow has become stale or harmful.

## 2. Memory Poisoning and Knowledge-Base Attacks

Retrieval-augmented systems inherit the integrity of their knowledge store.
**PoisonedRAG** (Zou et al., 2024) [7] shows that injecting a handful of
crafted passages into a RAG corpus reliably steers generations;
**AgentPoison** (Chen et al., 2024) [8] extends this to agent memory and
demonstrates backdoor triggers implanted through poisoned demonstrations.
These attacks motivate GSM's central design decision: experience must be
*screened before admission* (immune guard), *validated before reuse*
(evidence replay), and *revocable after admission* (quarantine and
rejection records). Prior agent-memory systems [1-6] have no equivalent
admission or revocation control.

## 3. Retrieval for Skill Reuse

Skill retrieval in prior systems is embedding-based top-k similarity
(Voyager [1], AWM [6]) or scored recency/relevance mixtures (Generative
Agents [4]). GSM's retrieval stack is a three-tier fallback
(sentence-embedding → TF-IDF → keyword) with a hybrid score that folds in
task-type match and risk. Our retrieval benchmark
(`experiments/retrieval_benchmark/`) measures this stack against BM25
(Robertson & Zaragoza, 2009) [9] and reports where lexical methods fail
(paraphrase queries) — the empirical justification for the embedding tier.
The acceptance-threshold sensitivity analysis further quantifies the
false-injection risk of unthresholded top-k retrieval on out-of-scope
queries, which no prior skill-memory system reports.

## 4. Comparison Table

| Capability | Voyager [1] | Reflexion [2] | ExpeL [3] | Gen. Agents [4] | MemoryBank [5] | AWM [6] | **GSM (this work)** |
|---|---|---|---|---|---|---|---|
| Procedural skill extraction | yes | no (text reflections) | partial (insights) | no | no | yes | yes |
| Verification before reuse | once, at acquisition | no | no | no | no | no | evidence replay + scoring |
| Safety screening of experience | no | no | no | no | no | no | immune guard + quarantine |
| Lifecycle (staleness / retirement) | no | no | no | no | time-decay | no | outcome-driven drift + curator |
| Closed loop from deployment outcomes | no | within-task only | no | no | revisit counts | no | outcome tracker → governance |
| Threat model for poisoned experience | no | no | no | no | no | no | yes |

## 5. Positioning Summary

The individual ingredients of GSM are standard (embedding retrieval,
quality scoring, quarantine lists). The contribution defended in the paper
is the **closed governance loop over the full lifecycle of agent-extracted
skills** — a loop that no system in [1-6] implements, and that the attack
literature [7, 8] shows is necessary. Claims are scoped accordingly: GSM is
not "self-evolving AI"; it is lifecycle management with measurable
admission, validation, monitoring, and retirement policies.

## References

[1] G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan,
A. Anandkumar. "Voyager: An Open-Ended Embodied Agent with Large Language
Models." arXiv:2305.16291, 2023.

[2] N. Shinn, F. Cassano, E. Berman, A. Gopinath, K. Narasimhan, S. Yao.
"Reflexion: Language Agents with Verbal Reinforcement Learning."
NeurIPS 2023. arXiv:2303.11366.

[3] A. Zhao, D. Huang, Q. Xu, M. Lin, Y.-J. Liu, G. Huang. "ExpeL: LLM
Agents Are Experiential Learners." AAAI 2024. arXiv:2308.10144.

[4] J. S. Park, J. C. O'Brien, C. J. Cai, M. R. Morris, P. Liang,
M. S. Bernstein. "Generative Agents: Interactive Simulacra of Human
Behavior." UIST 2023. arXiv:2304.03442.

[5] W. Zhong, L. Guo, Q. Gao, H. Ye, Y. Wang. "MemoryBank: Enhancing Large
Language Models with Long-Term Memory." AAAI 2024. arXiv:2305.10250.

[6] Z. Z. Wang, J. Mao, D. Fried, G. Neubig. "Agent Workflow Memory."
arXiv:2409.07429, 2024.

[7] W. Zou, R. Geng, B. Wang, J. Jia. "PoisonedRAG: Knowledge Corruption
Attacks to Retrieval-Augmented Generation of Large Language Models."
USENIX Security 2025. arXiv:2402.07867.

[8] Z. Chen, Z. Xiang, C. Xiao, D. Song, B. Li. "AgentPoison: Red-teaming
LLM Agents via Poisoning Memory or Knowledge Bases." NeurIPS 2024.
arXiv:2407.12784.

[9] S. Robertson, H. Zaragoza. "The Probabilistic Relevance Framework:
BM25 and Beyond." Foundations and Trends in Information Retrieval, 2009.
