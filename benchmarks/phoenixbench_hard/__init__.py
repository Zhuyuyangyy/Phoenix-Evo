"""
PhoenixBench-Hard: 100 hard tasks × 5 baselines benchmark for v2.0.

Categories:
  - multi_file_bug_fix (25): Cross-cutting bug fixes spanning 3-5 files
  - repo_navigation_reuse (20): Codebase navigation with historical skill reuse
  - shell_devops_safety (15): Shell/devops tasks with safety traps
  - api_integration_stale (15): API integration with stale skill pitfalls
  - cross_project_transfer (15): Cross-project/domain skill transfer
  - unsafe_adversarial (10): Adversarial memory poisoning attempts

Baselines:
  - vanilla_agent: No Phoenix safety mechanisms
  - rag_memory: RAG-based memory (no governance)
  - reflexion: Self-reflection loop (no persistent memory)
  - prompt_library: Static prompt templates (no learning)
  - phoenix_gsm: Phoenix Governed Skill Memory (full governance)

Metrics:
  - task_success_rate
  - skill_reuse_precision
  - unsafe_activation_rate
  - replay_caught_regression_rate
  - drift_detection_delay
  - cost_per_success
  - latency_overhead
"""

__version__ = "2.0.0"
