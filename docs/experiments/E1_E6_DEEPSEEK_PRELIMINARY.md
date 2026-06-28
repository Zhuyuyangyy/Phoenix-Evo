# E1–E6 Preliminary Results (DeepSeek)

All results were obtained using the **real DeepSeek API** (`deepseek-chat` model). No mocks or simulators were used for LLM calls.

## E1 — Governance Effectiveness

- **Design:** 25 tasks × 2 conditions (with / without Phoenix-Evo governance)
- **Result:** Both conditions achieved **100% task success rate**
- **Interpretation:** **CEILING EFFECT** — tasks were too easy for either condition to fail. There is no statistically significant difference. **Cannot claim Phoenix-Evo significantly improves success rate based on E1 alone.**

## E3 — Safety Filtering

- **Result:** **0% dangerous activation** in both conditions
- **Interpretation:** Safety filtering works as intended but does not differentiate between conditions in this benchmark. A harder benchmark with adversarial safety traps is needed.

## E4 — Drift Detection

- **Result:** CUSUM-based adaptive detection identifies drift at **step 16** vs. fixed threshold detection at **step 28**
- **Interpretation:** CUSUM is faster at detecting drift (12 steps earlier).

## E5 — Scalability

- **Result:** Sub-linear scaling observed
- **5000 skills:** 47.40 ms retrieval latency
- **Interpretation:** Skill registry scales sub-linearly with skill count; retrieval remains practical at large corpus sizes.

## E6 — Trajectory Mining

- **Result:** 220 trajectories analyzed, **105 high-risk cases** identified
- **Interpretation:** Mining pipeline successfully surfaces high-risk trajectories for safety review.

## Key Caveat

**E1 shows a ceiling effect.** The 25-task benchmark does not provide evidence that Phoenix-Evo governance improves task success rates. Any claim of improvement requires a harder benchmark (see `docs/NEXT_EXPERIMENTS_HARD.md`).
