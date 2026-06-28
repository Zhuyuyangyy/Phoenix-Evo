# Next Experiments: PhoenixBench-Hard

The E1 ceiling effect shows the current 25-task benchmark is insufficient to differentiate Phoenix-Evo governance from a no-governance baseline. A harder benchmark is required.

## PhoenixBench-Hard

**100 hard tasks** with a real difficulty gradient across 6 categories:

| # | Category | Count | Description |
|---|----------|-------|-------------|
| 1 | Multi-file bug fix | 25 | Requires reasoning across multiple files in a repo |
| 2 | Repo navigation + history reuse | 20 | Must locate relevant code and reuse prior solutions |
| 3 | Shell/DevOps with safety traps | 15 | Tasks where naive agents trigger destructive commands |
| 4 | API integration with stale skill traps | 15 | Outdated skills exist; agent must detect staleness |
| 5 | Cross-project skill transfer | 15 | Skills learned in one project applied to another |
| 6 | Unsafe/adversarial memory poisoning | 10 | Adversarial inputs designed to corrupt skill memory |

## Baselines

5 baselines, 3 seeds each:

| Baseline | Description |
|----------|-------------|
| `vanilla_agent` | No memory, no governance |
| `rag_memory` | RAG-based retrieval, no governance |
| `reflexion` | Reflexion-style self-correction |
| `prompt_library` | Static prompt/skill library |
| `phoenix_gsm` | Phoenix-Evo with governance + safety + memory |

**Total runs:** 100 tasks × 5 baselines × 3 seeds = **1,500**

## Metrics

| Metric | Description |
|--------|-------------|
| `task_success_rate` | Fraction of tasks completed correctly |
| `skill_reuse_precision` | Precision of reused skills (relevant / retrieved) |
| `unsafe_activation_rate` | Fraction of dangerous skill activations |
| `replay_caught_regression_rate` | Fraction of regressions caught by replay verification |
| `drift_detection_delay` | Steps until drift is detected |
| `cost_per_success` | Total API cost / successful tasks |
| `latency_overhead` | Additional latency from governance pipeline |

## v2.0 Release Conditions

v2.0 will be released only when **all** of the following are satisfied:

1. **Hard benchmark has differentiation** — PhoenixBench-Hard shows statistically significant differences between baselines (no ceiling effect).
2. **phoenix_gsm outperforms on safety/governance metrics** — `unsafe_activation_rate` and `replay_caught_regression_rate` are meaningfully better than all baselines.
3. **All results have bootstrap CI** — Confidence intervals computed via bootstrap resampling.
4. **Failure case analysis** — Qualitative analysis of all failure cases documented.
5. **Limitations documented** — Updated `docs/LIMITATIONS.md` reflecting v2.0 scope.
6. **CLAIMS_MATRIX updated** — Every claim in the paper/README traced to specific experiment IDs.
