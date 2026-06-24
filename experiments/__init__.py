"""
Phoenix-Evo Experiments Package
Agent对比实验框架
"""

# Lazy imports to avoid breaking if optional modules are missing
def __getattr__(name):
    if name in ("AgentTask", "TASK_DEFINITIONS", "TaskCategory", "DifficultyLevel"):
        from .task_definitions import TASK_DEFINITIONS, AgentTask, DifficultyLevel, TaskCategory  # noqa: F401
        return locals()[name]
    if name in ("ExperimentRunner", "ExperimentConfig", "ExecutionResult"):
        from .run_experiment import ExecutionResult, ExperimentConfig, ExperimentRunner  # noqa: F401
        return locals()[name]
    if name in ("run_analysis", "StatsSummary"):
        from .analyze_results import StatsSummary, run_analysis  # noqa: F401
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
