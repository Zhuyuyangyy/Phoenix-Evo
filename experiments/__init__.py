"""
Phoenix-Evo Experiments Package
Agent对比实验框架
"""

# Lazy imports to avoid breaking if optional modules are missing
def __getattr__(name):
    if name in ("AgentTask", "TASK_DEFINITIONS", "TaskCategory", "DifficultyLevel"):
        from .task_definitions import AgentTask, TASK_DEFINITIONS, TaskCategory, DifficultyLevel
        return locals()[name]
    if name in ("ExperimentRunner", "ExperimentConfig", "ExecutionResult"):
        from .run_experiment import ExperimentRunner, ExperimentConfig, ExecutionResult
        return locals()[name]
    if name in ("run_analysis", "StatsSummary"):
        from .analyze_results import run_analysis, StatsSummary
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
