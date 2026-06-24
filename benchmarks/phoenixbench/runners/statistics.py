"""Statistical analysis framework for PhoenixBench."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats


def bootstrap_ci(
    data: List[float],
    statistic: Callable = np.mean,
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """Compute bootstrap confidence interval for a statistic.

    Args:
        data: Sample data.
        statistic: Function to compute the statistic (default: mean).
        n_bootstrap: Number of bootstrap resamples.
        ci: Confidence level (default: 0.95).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (lower_bound, upper_bound).
    """
    rng = np.random.RandomState(seed)
    data_arr = np.array(data)
    boot_stats = []
    for _ in range(n_bootstrap):
        sample = rng.choice(data_arr, size=len(data_arr), replace=True)
        boot_stats.append(statistic(sample))
    boot_stats = np.array(boot_stats)
    alpha = 1 - ci
    lower = float(np.percentile(boot_stats, 100 * alpha / 2))
    upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    return lower, upper


def paired_significance_test(
    baseline_scores: List[float],
    treatment_scores: List[float],
) -> Dict[str, Any]:
    """Perform a paired significance test between baseline and treatment.

    Uses Wilcoxon signed-rank test (non-parametric) and paired t-test.

    Args:
        baseline_scores: Scores from the baseline condition.
        treatment_scores: Scores from the treatment condition.

    Returns:
        Dictionary with test results.
    """
    baseline = np.array(baseline_scores)
    treatment = np.array(treatment_scores)

    # Paired t-test
    t_stat, t_pvalue = scipy_stats.ttest_rel(baseline, treatment)

    # Wilcoxon signed-rank test
    try:
        w_stat, w_pvalue = scipy_stats.wilcoxon(baseline, treatment)
    except ValueError:
        # All differences are zero
        w_stat, w_pvalue = 0.0, 1.0

    # Effect size (Cohen's d for paired)
    diff = treatment - baseline
    d = float(np.mean(diff) / (np.std(diff, ddof=1) + 1e-10))

    return {
        "t_statistic": float(t_stat),
        "t_pvalue": float(t_pvalue),
        "wilcoxon_statistic": float(w_stat),
        "wilcoxon_pvalue": float(w_pvalue),
        "cohens_d_paired": d,
        "mean_diff": float(np.mean(diff)),
        "significant_005": t_pvalue < 0.05,
        "significant_001": t_pvalue < 0.01,
    }


def cohens_d(group1: List[float], group2: List[float]) -> float:
    """Compute Cohen's d effect size between two independent groups.

    Args:
        group1: First group of scores.
        group2: Second group of scores.

    Returns:
        Cohen's d value.
    """
    g1 = np.array(group1)
    g2 = np.array(group2)
    n1, n2 = len(g1), len(g2)
    var1 = np.var(g1, ddof=1)
    var2 = np.var(g2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std < 1e-10:
        return 0.0
    return float((np.mean(g1) - np.mean(g2)) / pooled_std)


def bonferroni_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Apply Bonferroni correction for multiple comparisons.

    Args:
        p_values: List of p-values from multiple tests.
        alpha: Family-wise error rate.

    Returns:
        Dictionary with corrected results.
    """
    n = len(p_values)
    corrected_alpha = alpha / n if n > 0 else alpha
    results = []
    for p in p_values:
        results.append({
            "original_p": p,
            "corrected_p": min(p * n, 1.0),
            "significant_before": p < alpha,
            "significant_after": p < corrected_alpha,
        })
    return {
        "alpha": alpha,
        "corrected_alpha": corrected_alpha,
        "n_tests": n,
        "results": results,
    }


def aggregate_results(jsonl_path: str) -> Dict[str, Any]:
    """Aggregate benchmark results from a JSONL file.

    Args:
        jsonl_path: Path to JSONL file with benchmark results.

    Returns:
        Aggregated statistics dictionary.
    """
    records = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return {"total_tasks": 0, "categories": {}}

    # Group by category
    categories: Dict[str, List[Dict]] = {}
    for rec in records:
        cat = rec.get("category", "uncategorized")
        categories.setdefault(cat, []).append(rec)

    aggregated = {
        "total_tasks": len(records),
        "categories": {},
    }

    for cat, recs in categories.items():
        scores = [r.get("score", 0.0) for r in recs]
        successes = [1 if r.get("success", False) else 0 for r in recs]
        times = [r.get("duration_seconds", 0.0) for r in recs]
        tokens = [r.get("total_tokens", 0) for r in recs]

        cat_stats = {
            "n_tasks": len(recs),
            "mean_score": float(np.mean(scores)) if scores else 0.0,
            "std_score": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0,
            "success_rate": float(np.mean(successes)) if successes else 0.0,
            "mean_duration": float(np.mean(times)) if times else 0.0,
            "mean_tokens": float(np.mean(tokens)) if tokens else 0.0,
        }

        # Bootstrap CI for mean score
        if len(scores) >= 2:
            lower, upper = bootstrap_ci(scores)
            cat_stats["score_ci_lower"] = lower
            cat_stats["score_ci_upper"] = upper

        aggregated["categories"][cat] = cat_stats

    return aggregated


def write_frozen_results(
    results: Dict[str, Any],
    output_dir: str,
    run_id: Optional[str] = None,
) -> str:
    """Write frozen (immutable) benchmark results to disk.

    Args:
        results: Aggregated results dictionary.
        output_dir: Directory to write results to.
        run_id: Optional run identifier. Auto-generated if not provided.

    Returns:
        Path to the written results file.
    """
    if run_id is None:
        run_id = str(uuid.uuid4())[:8]

    os.makedirs(output_dir, exist_ok=True)

    frozen = {
        "run_id": run_id,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    output_path = os.path.join(output_dir, f"frozen_{run_id}.json")
    with open(output_path, "w") as f:
        json.dump(frozen, f, indent=2, default=str)

    return output_path


def generate_report(aggregated: Dict[str, Any]) -> str:
    """Generate a human-readable report from aggregated results.

    Args:
        aggregated: Aggregated results from aggregate_results().

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("PhoenixBench Results Report")
    lines.append("=" * 60)
    lines.append(f"Total tasks: {aggregated.get('total_tasks', 0)}")
    lines.append("")

    for cat, stats in aggregated.get("categories", {}).items():
        lines.append(f"--- {cat} ---")
        lines.append(f"  Tasks: {stats.get('n_tasks', 0)}")
        lines.append(f"  Mean score: {stats.get('mean_score', 0):.4f}")
        lines.append(f"  Std score: {stats.get('std_score', 0):.4f}")
        lines.append(f"  Success rate: {stats.get('success_rate', 0):.2%}")
        if "score_ci_lower" in stats:
            lines.append(
                f"  95% CI: [{stats['score_ci_lower']:.4f}, {stats['score_ci_upper']:.4f}]"
            )
        lines.append(f"  Mean duration: {stats.get('mean_duration', 0):.2f}s")
        lines.append(f"  Mean tokens: {stats.get('mean_tokens', 0):.0f}")
        lines.append("")

    return "\n".join(lines)
