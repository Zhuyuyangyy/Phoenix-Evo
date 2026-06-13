# Governed Skill Memory for Agent-Extracted Procedural Knowledge
**Target:** AAMAS 2027
**Status:** Skeleton Draft

---

## Abstract
- Problem: Agents lack structured memory for procedural knowledge
- Gap: No governance mechanism for skill extraction and reuse
- Approach: 6-stage pipeline with governed skill memory
- Results: 50-task evaluation + ablation
- Contribution: First governed memory framework for agent procedural learning

## 1. Introduction
- Background: LLM agents and procedural knowledge
- Motivation: Why governance matters for skill memory
- Research questions: RQ1-RQ3
- Paper organization

## 2. Related Work
- 2.1 Agent memory systems
- 2.2 Procedural knowledge extraction
- 2.3 Skill libraries and reuse
- 2.4 Governance in multi-agent systems

## 3. Methodology
- 3.1 System overview
- 3.2 Stage 1: Trajectory observation
- 3.3 Stage 2: Skill extraction
- 3.4 Stage 3: Validation & filtering
- 3.5 Stage 4: Memory encoding
- 3.6 Stage 5: Governance rules
- 3.7 Stage 6: Skill retrieval & application

**Figure 1: 6-Stage Pipeline Architecture**

## 4. Experiments
- 4.1 Benchmark: 50 procedural tasks
- 4.2 Baselines (5 methods):
  - Vanilla ReAct
  - Reflexion
  - Voyager
  - GITM
  - Ours w/o governance
- 4.3 Evaluation metrics: Success rate, Efficiency, Skill reuse rate
- 4.4 Main results

**Table 1: 50-Task Performance**
| Method | Success% | Avg Steps | Skill Reuse |
|--------|----------|-----------|-------------|
| ReAct | | | |
| Reflexion | | | |
| Voyager | | | |
| GITM | | | |
| Ours w/o gov | | | |
| Ours (full) | | | |

**Table 2: Ablation Study**
| Variant | Success% | Delta |
|---------|----------|-------|
| Full pipeline | | - |
| w/o trajectory obs | | |
| w/o validation | | |
| w/o governance | | |
| w/o memory encoding | | |

**Table 3: Governance Impact**
| Governance Level | Success% | Safety Score |
|------------------|----------|--------------|
| None | | |
| Basic | | |
| Strict | | |

## 5. Discussion
- 5.1 Governance trade-offs
- 5.2 Skill generalization
- 5.3 Scalability analysis
- 5.4 Limitations

## 6. Conclusion
- Summary of contributions
- Future work: multi-agent skill sharing

---

## References
- [Key papers to cite: 25-35 references]
