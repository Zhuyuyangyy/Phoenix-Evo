# Limitations

## Experiment Design

- **E1 ceiling effect:** The 25-task governance benchmark was too easy; both conditions (with and without governance) achieved 100% success. This provides no evidence that Phoenix-Evo improves success rate.
- **No external baselines:** No comparison against RAG-based memory, reflexion, or prompt library baselines.
- **Single LLM provider:** All experiments used DeepSeek (`deepseek-chat`) only. Results may not generalize to other providers or models.

## Unvalidated Modules

- **Enterprise, distributed, multi_agent, self_repair:** These modules are infrastructure scaffolding added in v1.5. They have no empirical validation.
- **Drift detection:** Validated only in simulation, not in production deployment.
- **Safety filtering:** Has not been adversarially stress-tested. The 0% dangerous activation rate in E3 reflects easy test cases, not robustness under adversarial input.

## Scale & Coverage

- **Skill versioning and cross-project sharing:** Implemented but untested at scale.
- **No multi-agent experiments:** Multi-agent collaborative evolution has not been empirically evaluated.
