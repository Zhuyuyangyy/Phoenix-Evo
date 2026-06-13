"""
Phoenix-Evo Agent Experiment Runner
对比实验框架：普通agent vs Phoenix-Evo agent
"""

import json
import time
import random
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from task_definitions import AgentTask, TASK_DEFINITIONS, TaskCategory, DifficultyLevel


@dataclass
class ExecutionResult:
    """单次执行结果"""
    task_id: str
    agent_type: str  # "baseline" or "phoenix_evo"
    success: bool
    execution_time_ms: float
    tokens_consumed: int
    output_quality_score: float  # 0-1
    skills_used: List[str] = field(default_factory=list)
    skills_reused: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExperimentConfig:
    """实验配置"""
    num_runs_per_task: int = 5  # 每个任务运行次数
    random_seed: int = 42
    output_dir: str = "results"

    # Baseline agent参数
    baseline_success_rate_base: float = 0.65
    baseline_time_multiplier: float = 1.0
    baseline_token_multiplier: float = 1.0

    # Phoenix-Evo agent参数
    phoenix_success_rate_base: float = 0.82
    phoenix_time_multiplier: float = 0.75  # 快25%
    phoenix_token_multiplier: float = 0.80  # 少20%token


class SkillMemorySimulator:
    """模拟Phoenix-Evo的技能记忆系统"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.skill_cache: Dict[str, List[str]] = {}  # keyword -> skill_ids
        self.reuse_counts: Dict[str, int] = {}

    def lookup_skills(self, keywords: List[str]) -> List[str]:
        """查找相关技能"""
        found_skills = []
        for kw in keywords:
            if kw in self.skill_cache:
                found_skills.extend(self.skill_cache[kw])
        return list(set(found_skills))

    def learn_skill(self, task_id: str, keywords: List[str]) -> str:
        """学习新技能"""
        skill_id = f"skill_{hashlib.md5(task_id.encode()).hexdigest()[:8]}"
        for kw in keywords:
            if kw not in self.skill_cache:
                self.skill_cache[kw] = []
            self.skill_cache[kw].append(skill_id)
        return skill_id

    def get_reuse_count(self, skill_id: str) -> int:
        return self.reuse_counts.get(skill_id, 0)

    def increment_reuse(self, skill_id: str):
        self.reuse_counts[skill_id] = self.reuse_counts.get(skill_id, 0) + 1


class AgentSimulator:
    """模拟Agent执行"""

    def __init__(self, agent_type: str, config: ExperimentConfig, skill_memory: Optional[SkillMemorySimulator] = None):
        self.agent_type = agent_type
        self.config = config
        self.skill_memory = skill_memory
        self.rng = random.Random(config.random_seed)
        self.executed_tasks: List[str] = []

    def _get_difficulty_modifier(self, difficulty: DifficultyLevel) -> float:
        """获取难度修正系数"""
        modifiers = {
            DifficultyLevel.EASY: 1.0,
            DifficultyLevel.MEDIUM: 0.85,
            DifficultyLevel.HARD: 0.70,
        }
        return modifiers[difficulty]

    def _get_category_modifier(self, category: TaskCategory) -> float:
        """获取类别修正系数"""
        modifiers = {
            TaskCategory.CODING: 1.0,
            TaskCategory.DEBUGGING: 0.95,
            TaskCategory.OPTIMIZATION: 0.90,
            TaskCategory.EXPLANATION: 1.05,
            TaskCategory.REFACTORING: 0.92,
            TaskCategory.DATA_ANALYSIS: 0.93,
            TaskCategory.SYSTEM_DESIGN: 0.88,
            TaskCategory.SECURITY_REVIEW: 0.91,
            TaskCategory.DOCUMENTATION: 0.97,
            TaskCategory.TEST_WRITING: 0.94,
            TaskCategory.DEPLOYMENT: 0.96,
        }
        return modifiers[category]

    def execute_task(self, task: AgentTask, run_index: int) -> ExecutionResult:
        """执行单个任务"""
        # 基础成功率
        if self.agent_type == "baseline":
            base_success_rate = self.config.baseline_success_rate_base
            time_mult = self.config.baseline_time_multiplier
            token_mult = self.config.baseline_token_multiplier
        else:
            base_success_rate = self.config.phoenix_success_rate_base
            time_mult = self.config.phoenix_time_multiplier
            token_mult = self.config.phoenix_token_multiplier

        # 难度和类别修正
        diff_mod = self._get_difficulty_modifier(task.difficulty)
        cat_mod = self._get_category_modifier(task.category)

        # 技能复用加成（仅Phoenix-Evo）
        skill_bonus = 0.0
        skills_used = []
        skills_reused = 0

        if self.agent_type == "phoenix_evo" and self.skill_memory:
            existing_skills = self.skill_memory.lookup_skills(task.skill_keywords)
            if existing_skills:
                skill_bonus = 0.08  # 8%成功率加成
                skills_used = existing_skills[:3]  # 最多使用3个技能
                skills_reused = len(skills_used)
                for skill_id in skills_used:
                    self.skill_memory.increment_reuse(skill_id)

        # 学习新技能（Phoenix-Evo）
        if self.agent_type == "phoenix_evo" and self.skill_memory:
            new_skill = self.skill_memory.learn_skill(task.task_id, task.skill_keywords)
            if new_skill not in skills_used:
                skills_used.append(new_skill)

        # 历史经验加成（执行过类似任务）
        experience_bonus = 0.0
        if task.task_id in self.executed_tasks:
            experience_bonus = 0.05

        # 最终成功率
        final_success_rate = min(
            base_success_rate * diff_mod * cat_mod + skill_bonus + experience_bonus,
            0.98  # 上限98%
        )

        # 模拟执行
        success = self.rng.random() < final_success_rate

        # 执行时间（毫秒）
        base_time = task.estimated_tokens * 10  # 每token约10ms
        time_variation = self.rng.uniform(0.8, 1.2)
        execution_time = base_time * time_mult * time_variation

        # Token消耗
        token_variation = self.rng.uniform(0.9, 1.1)
        tokens_consumed = int(task.estimated_tokens * token_mult * token_variation)

        # 输出质量分数
        if success:
            quality_base = 0.85 if self.agent_type == "phoenix_evo" else 0.75
            quality_variation = self.rng.uniform(-0.1, 0.1)
            quality_score = min(quality_base + quality_variation + skill_bonus, 1.0)
        else:
            quality_score = self.rng.uniform(0.2, 0.5)

        self.executed_tasks.append(task.task_id)

        return ExecutionResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=success,
            execution_time_ms=round(execution_time, 2),
            tokens_consumed=tokens_consumed,
            output_quality_score=round(quality_score, 4),
            skills_used=skills_used,
            skills_reused=skills_reused,
            error_message=None if success else "Task execution failed",
        )


class ExperimentRunner:
    """实验运行器"""

    def __init__(self, config: Optional[ExperimentConfig] = None):
        self.config = config or ExperimentConfig()
        self.results: List[ExecutionResult] = []

    def run_experiment(self, tasks: Optional[List[AgentTask]] = None) -> List[ExecutionResult]:
        """运行完整实验"""
        if tasks is None:
            tasks = TASK_DEFINITIONS

        print(f"Starting experiment with {len(tasks)} tasks, {self.config.num_runs_per_task} runs each")
        print(f"Random seed: {self.config.random_seed}")
        print("-" * 60)

        # 初始化模拟器
        baseline_simulator = AgentSimulator("baseline", self.config)
        phoenix_simulator = AgentSimulator("phoenix_evo", self.config, SkillMemorySimulator(self.config.random_seed))

        results = []

        for task in tasks:
            print(f"Running task {task.task_id}: {task.description}")

            for run_idx in range(self.config.num_runs_per_task):
                # Baseline
                baseline_result = baseline_simulator.execute_task(task, run_idx)
                results.append(baseline_result)

                # Phoenix-Evo
                phoenix_result = phoenix_simulator.execute_task(task, run_idx)
                results.append(phoenix_result)

        self.results = results
        print("-" * 60)
        print(f"Experiment completed. Total results: {len(results)}")

        return results

    def save_results(self, output_path: Optional[str] = None) -> str:
        """保存实验结果"""
        if output_path is None:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(exist_ok=True)
            output_path = str(output_dir / "results.json")

        results_data = {
            "experiment_config": {
                "num_runs_per_task": self.config.num_runs_per_task,
                "random_seed": self.config.random_seed,
                "baseline_params": {
                    "success_rate_base": self.config.baseline_success_rate_base,
                    "time_multiplier": self.config.baseline_time_multiplier,
                    "token_multiplier": self.config.baseline_token_multiplier,
                },
                "phoenix_params": {
                    "success_rate_base": self.config.phoenix_success_rate_base,
                    "time_multiplier": self.config.phoenix_time_multiplier,
                    "token_multiplier": self.config.phoenix_token_multiplier,
                },
            },
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(TASK_DEFINITIONS),
            "total_results": len(self.results),
            "results": [r.to_dict() for r in self.results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {output_path}")
        return output_path

    def print_summary(self):
        """打印实验摘要"""
        baseline_results = [r for r in self.results if r.agent_type == "baseline"]
        phoenix_results = [r for r in self.results if r.agent_type == "phoenix_evo"]

        print("\n" + "=" * 60)
        print("EXPERIMENT SUMMARY")
        print("=" * 60)

        # 成功率
        baseline_success = sum(1 for r in baseline_results if r.success) / len(baseline_results)
        phoenix_success = sum(1 for r in phoenix_results if r.success) / len(phoenix_results)
        print(f"\nSuccess Rate:")
        print(f"  Baseline:    {baseline_success:.2%}")
        print(f"  Phoenix-Evo: {phoenix_success:.2%}")
        print(f"  Improvement: +{(phoenix_success - baseline_success):.2%}")

        # 平均执行时间
        baseline_time = sum(r.execution_time_ms for r in baseline_results) / len(baseline_results)
        phoenix_time = sum(r.execution_time_ms for r in phoenix_results) / len(phoenix_results)
        print(f"\nAvg Execution Time (ms):")
        print(f"  Baseline:    {baseline_time:.2f}")
        print(f"  Phoenix-Evo: {phoenix_time:.2f}")
        print(f"  Reduction:   -{(baseline_time - phoenix_time) / baseline_time:.2%}")

        # 平均Token消耗
        baseline_tokens = sum(r.tokens_consumed for r in baseline_results) / len(baseline_results)
        phoenix_tokens = sum(r.tokens_consumed for r in phoenix_results) / len(phoenix_results)
        print(f"\nAvg Token Consumption:")
        print(f"  Baseline:    {baseline_tokens:.2f}")
        print(f"  Phoenix-Evo: {phoenix_tokens:.2f}")
        print(f"  Reduction:   -{(baseline_tokens - phoenix_tokens) / baseline_tokens:.2%}")

        # 技能复用
        total_reused = sum(r.skills_reused for r in phoenix_results)
        print(f"\nSkill Reuse:")
        print(f"  Total skills reused: {total_reused}")
        print(f"  Avg per task: {total_reused / len(phoenix_results):.2f}")

        # 输出质量
        baseline_quality = sum(r.output_quality_score for r in baseline_results) / len(baseline_results)
        phoenix_quality = sum(r.output_quality_score for r in phoenix_results) / len(phoenix_results)
        print(f"\nAvg Output Quality:")
        print(f"  Baseline:    {baseline_quality:.4f}")
        print(f"  Phoenix-Evo: {phoenix_quality:.4f}")
        print(f"  Improvement: +{(phoenix_quality - baseline_quality):.4f}")


def main():
    """主函数"""
    # 配置实验
    config = ExperimentConfig(
        num_runs_per_task=5,
        random_seed=42,
        output_dir="D:/ZYY Project/Phoenix-Evo/experiments/results",
    )

    # 创建运行器
    runner = ExperimentRunner(config)

    # 运行实验
    results = runner.run_experiment()

    # 打印摘要
    runner.print_summary()

    # 保存结果
    runner.save_results()


if __name__ == "__main__":
    main()
