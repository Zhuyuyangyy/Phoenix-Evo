"""
Run all experiments and generate reports
"""

import os
import sys

# 添加experiments目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ablation import analyze_ablation_results, generate_ablation_report, run_ablation_study, save_ablation_results
from analyze_results import run_analysis
from run_experiment import ExperimentConfig, ExperimentRunner


def main():
    """运行完整实验流程"""
    print("=" * 70)
    print("PHOENIX-EVO COMPREHENSIVE EXPERIMENT SUITE")
    print("=" * 70)

    output_dir = "D:/ZYY Project/Phoenix-Evo/experiments/results"

    # ===== Part 1: Main Experiment =====
    print("\n" + "=" * 70)
    print("PART 1: MAIN EXPERIMENT (50 tasks)")
    print("=" * 70)

    config = ExperimentConfig(
        num_runs_per_task=5,
        random_seed=42,
        output_dir=output_dir,
    )

    print("\n[1/4] Running main experiment...")
    runner = ExperimentRunner(config)
    runner.run_experiment()
    runner.print_summary()

    print("\n[2/4] Saving main results...")
    results_path = runner.save_results()

    print("\n[3/4] Performing statistical analysis...")
    report_path = f"{output_dir}/report.md"
    analyses = run_analysis(results_path, report_path)

    # ===== Part 2: Ablation Study =====
    print("\n" + "=" * 70)
    print("PART 2: ABLATION STUDY")
    print("=" * 70)

    print("\n[4/4] Running ablation study...")
    ablation_results = run_ablation_study(num_runs=5, seed=42)
    ablation_analysis = analyze_ablation_results(ablation_results)
    save_ablation_results(ablation_results, ablation_analysis, output_dir)
    generate_ablation_report(ablation_analysis, f"{output_dir}/ablation_report.md")

    # ===== Summary =====
    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
    print(f"\nMain Results: {output_dir}/results.json")
    print(f"Main Report:  {output_dir}/report.md")
    print(f"Ablation Results: {output_dir}/ablation_results.json")
    print(f"Ablation Report:  {output_dir}/ablation_report.md")

    return analyses, ablation_analysis


if __name__ == "__main__":
    main()
