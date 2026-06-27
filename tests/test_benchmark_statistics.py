"""Tests for benchmark statistics."""

import json
import os
import tempfile

import numpy as np
import pytest

from benchmarks.phoenixbench.runners.statistics import (
    aggregate_results,
    bonferroni_correction,
    bootstrap_ci,
    cohens_d,
    generate_report,
    paired_significance_test,
    write_frozen_results,
)


class TestBootstrapCI:
    def test_basic_ci(self):
        data = list(range(100))
        lower, upper = bootstrap_ci(data, n_bootstrap=1000, seed=42)
        assert lower < upper
        assert lower < np.mean(data)
        assert upper > np.mean(data)

    def test_ci_contains_mean(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        lower, upper = bootstrap_ci(data, n_bootstrap=5000, seed=42)
        mean = np.mean(data)
        assert lower <= mean <= upper

    def test_ci_narrow_with_more_data(self):
        small_data = [1.0, 2.0, 3.0]
        large_data = list(np.random.RandomState(42).normal(2.0, 1.0, 1000))
        _, upper_small = bootstrap_ci(small_data, n_bootstrap=1000, seed=42)
        _, upper_large = bootstrap_ci(large_data, n_bootstrap=1000, seed=42)
        # Larger sample should have narrower CI
        assert (upper_large - np.mean(large_data)) <= (upper_small - np.mean(small_data)) + 0.5

    def test_reproducible(self):
        data = list(range(50))
        l1, u1 = bootstrap_ci(data, n_bootstrap=1000, seed=42)
        l2, u2 = bootstrap_ci(data, n_bootstrap=1000, seed=42)
        assert l1 == l2
        assert u1 == u2

    def test_different_seeds(self):
        data = list(range(50))
        l1, u1 = bootstrap_ci(data, n_bootstrap=1000, seed=42)
        l2, u2 = bootstrap_ci(data, n_bootstrap=1000, seed=99)
        # Different seeds may give different results
        # Just check they're both valid CIs
        assert l1 < u1
        assert l2 < u2

    def test_custom_statistic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        lower, upper = bootstrap_ci(data, statistic=np.median, n_bootstrap=1000, seed=42)
        assert lower < upper

    def test_single_value(self):
        data = [5.0]
        lower, upper = bootstrap_ci(data, n_bootstrap=100, seed=42)
        assert lower == upper == 5.0


class TestPairedSignificanceTest:
    def test_significant_difference(self):
        baseline = [1.0] * 30
        treatment = [2.0] * 30
        result = paired_significance_test(baseline, treatment)
        assert result["significant_005"] is True or result["t_pvalue"] < 0.05
        assert result["mean_diff"] == 1.0

    def test_no_difference(self):
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = paired_significance_test(scores, scores)
        assert result["mean_diff"] == 0.0
        # t_pvalue should be nan or 1.0 for identical data
        assert result["t_pvalue"] >= 0.99 or np.isnan(result["t_pvalue"])

    def test_result_fields(self):
        baseline = [1.0, 2.0, 3.0]
        treatment = [2.0, 3.0, 4.0]
        result = paired_significance_test(baseline, treatment)
        assert "t_statistic" in result
        assert "t_pvalue" in result
        assert "wilcoxon_statistic" in result
        assert "wilcoxon_pvalue" in result
        assert "cohens_d_paired" in result
        assert "mean_diff" in result

    def test_small_effect(self):
        baseline = list(np.random.RandomState(42).normal(0, 1, 100))
        treatment = [x + 0.01 for x in baseline]
        result = paired_significance_test(baseline, treatment)
        assert result["mean_diff"] == pytest.approx(0.01, abs=0.001)


class TestCohensD:
    def test_no_difference(self):
        d = cohens_d([1, 2, 3], [1, 2, 3])
        assert d == pytest.approx(0.0, abs=0.01)

    def test_large_difference(self):
        d = cohens_d([1, 1, 1, 1, 2], [10, 10, 10, 10, 9])
        assert abs(d) > 5.0  # Very large effect (magnitude)

    def test_medium_effect(self):
        d = cohens_d([1, 2, 3, 4, 5], [3, 4, 5, 6, 7])
        assert abs(d) > 0.5  # Positive effect size

    def test_equal_groups(self):
        d = cohens_d([5, 5, 5], [5, 5, 5])
        assert d == 0.0


class TestBonferroniCorrection:
    def test_basic_correction(self):
        p_values = [0.01, 0.03, 0.04]
        result = bonferroni_correction(p_values, alpha=0.05)
        assert result["n_tests"] == 3
        assert result["corrected_alpha"] == pytest.approx(0.05 / 3, abs=0.001)

    def test_significance_changes(self):
        p_values = [0.01, 0.03, 0.04]
        result = bonferroni_correction(p_values, alpha=0.05)
        # Only 0.01 should remain significant after correction
        assert result["results"][0]["significant_after"] is True
        assert result["results"][1]["significant_after"] is False

    def test_empty_p_values(self):
        result = bonferroni_correction([], alpha=0.05)
        assert result["n_tests"] == 0
        assert result["corrected_alpha"] == 0.05

    def test_single_test(self):
        result = bonferroni_correction([0.03], alpha=0.05)
        assert result["corrected_alpha"] == 0.05


class TestAggregateResults:
    def test_aggregate_basic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"category": "test", "score": 0.8, "success": True, "duration_seconds": 1.0, "total_tokens": 100}) + "\n")
            f.write(json.dumps({"category": "test", "score": 0.9, "success": True, "duration_seconds": 2.0, "total_tokens": 200}) + "\n")
            f.write(json.dumps({"category": "other", "score": 0.5, "success": False, "duration_seconds": 0.5, "total_tokens": 50}) + "\n")
            path = f.name

        try:
            result = aggregate_results(path)
            assert result["total_tasks"] == 3
            assert "test" in result["categories"]
            assert "other" in result["categories"]
            assert result["categories"]["test"]["mean_score"] == pytest.approx(0.85, abs=0.01)
        finally:
            os.unlink(path)

    def test_aggregate_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            result = aggregate_results(path)
            assert result["total_tasks"] == 0
        finally:
            os.unlink(path)


class TestWriteFrozenResults:
    def test_write_frozen(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = {"total_tasks": 10, "categories": {}}
            path = write_frozen_results(results, tmpdir, run_id="test123")
            assert os.path.exists(path)
            assert "test123" in path

            with open(path) as f:
                data = json.load(f)
            assert data["run_id"] == "test123"
            assert "frozen_at" in data

    def test_auto_run_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_frozen_results({"test": True}, tmpdir)
            assert os.path.exists(path)


class TestGenerateReport:
    def test_basic_report(self):
        aggregated = {
            "total_tasks": 5,
            "categories": {
                "coding": {
                    "n_tasks": 5,
                    "mean_score": 0.85,
                    "std_score": 0.1,
                    "success_rate": 0.8,
                    "mean_duration": 1.5,
                    "mean_tokens": 500,
                }
            }
        }
        report = generate_report(aggregated)
        assert "PhoenixBench" in report
        assert "coding" in report
        assert "0.85" in report

    def test_empty_report(self):
        report = generate_report({"total_tasks": 0, "categories": {}})
        assert "Total tasks: 0" in report
