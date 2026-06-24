"""Tests for paper experiments."""

import pytest

from experiments.paper.experiment_definitions import (
    ALL_EXPERIMENTS, E1, E2, E3, E4, E5, E6, ExperimentDefinition,
)
from experiments.paper.ablation_runner import AblationRunner, AblationConfig, AblationResult
from experiments.paper.case_study import CaseStudyAnalyzer, CaseStudy, CaseStudyResult
from experiments.paper.paper_generator import PaperGenerator
from experiments.paper.reproducibility import ReproducibilityManager, ExperimentRun


class TestExperimentDefinitions:
    def test_all_experiments_defined(self):
        assert len(ALL_EXPERIMENTS) == 6
        for eid in ["E1", "E2", "E3", "E4", "E5", "E6"]:
            assert eid in ALL_EXPERIMENTS

    def test_e1_safety(self):
        assert E1.experiment_id == "E1"
        assert "safety" in E1.title.lower() or "Safety" in E1.title
        assert E1.sample_size > 0

    def test_e2_drift(self):
        assert E2.experiment_id == "E2"
        assert "drift" in E2.title.lower() or "Drift" in E2.title

    def test_e3_trust(self):
        assert E3.experiment_id == "E3"
        assert "trust" in E3.title.lower() or "Trust" in E3.title

    def test_e4_multi_agent(self):
        assert E4.experiment_id == "E4"
        assert "multi" in E4.title.lower() or "Multi" in E4.title or "agent" in E4.title.lower()

    def test_e5_self_repair(self):
        assert E5.experiment_id == "E5"
        assert "repair" in E5.title.lower() or "Repair" in E5.title

    def test_e6_end_to_end(self):
        assert E6.experiment_id == "E6"
        assert "end" in E6.title.lower() or "End" in E6.title

    def test_experiment_fields(self):
        for exp in ALL_EXPERIMENTS.values():
            assert isinstance(exp, ExperimentDefinition)
            assert exp.hypothesis
            assert exp.independent_variables
            assert exp.dependent_variables
            assert exp.sample_size > 0
            assert 0 < exp.significance_level < 1


class TestAblationRunner:
    def test_create_ablation(self):
        runner = AblationRunner()
        config = runner.create_ablation(E1)
        assert config.experiment_id == "E1"
        assert len(config.components) > 0

    def test_run_ablation(self):
        runner = AblationRunner()
        config = runner.create_ablation(E1, components=["a", "b"])
        results = runner.run_ablation(config)
        # 2 components => 3 combinations (a, b, ab)
        assert len(results) == 3

    def test_run_with_evaluator(self):
        runner = AblationRunner()
        config = runner.create_ablation(E1, components=["safety", "drift"])

        def evaluator(enabled):
            return {"score": len(enabled) * 0.5}

        results = runner.run_ablation(config, evaluator=evaluator)
        assert len(results) > 0
        assert all("score" in r.metrics for r in results)

    def test_analyze_contributions(self):
        runner = AblationRunner()
        config = runner.create_ablation(E1, components=["a", "b"])
        results = runner.run_ablation(config)
        contributions = runner.analyze_contributions(results)
        assert isinstance(contributions, dict)

    def test_get_results(self):
        runner = AblationRunner()
        config = runner.create_ablation(E1, components=["a"])
        runner.run_ablation(config)
        results = runner.get_results()
        assert len(results) > 0


class TestCaseStudyAnalyzer:
    def test_create_case(self):
        analyzer = CaseStudyAnalyzer()
        case = analyzer.create_case(
            title="Test Case",
            description="A test case",
            scenario={"risk_level": "high"},
            expected_behavior="safe execution",
        )
        assert case.case_id is not None
        assert case.title == "Test Case"

    def test_analyze(self):
        analyzer = CaseStudyAnalyzer()
        case = analyzer.create_case(
            title="Test",
            description="test",
            scenario={"risk_level": "high", "tool_access": "unrestricted"},
            expected_behavior="safe",
        )
        result = analyzer.analyze(case)
        assert result.severity == "high"
        assert len(result.findings) > 0

    def test_list_cases(self):
        analyzer = CaseStudyAnalyzer()
        analyzer.create_case("C1", "desc1", {}, "expected1")
        analyzer.create_case("C2", "desc2", {}, "expected2")
        cases = analyzer.list_cases()
        assert len(cases) == 2

    def test_generate_summary(self):
        analyzer = CaseStudyAnalyzer()
        case = analyzer.create_case("C1", "desc", {"risk_level": "high"}, "expected")
        analyzer.analyze(case)
        summary = analyzer.generate_summary()
        assert summary["total_cases"] == 1
        assert summary["analyzed_cases"] == 1


class TestPaperGenerator:
    def test_generate_abstract(self):
        gen = PaperGenerator()
        abstract = gen.generate_abstract()
        assert "Phoenix" in abstract
        assert len(abstract) > 100

    def test_generate_introduction(self):
        gen = PaperGenerator()
        intro = gen.generate_introduction()
        assert "Introduction" in intro

    def test_generate_methodology(self):
        gen = PaperGenerator()
        method = gen.generate_methodology()
        assert "Methodology" in method

    def test_generate_results(self):
        gen = PaperGenerator()
        results = gen.generate_results()
        assert "Results" in results

    def test_generate_with_data(self):
        gen = PaperGenerator()
        gen.add_experiment_result("E1", {"safety_improvement": 0.55})
        results = gen.generate_results()
        assert "0.55" in results

    def test_generate_ablation_section(self):
        gen = PaperGenerator()
        section = gen.generate_ablation_section()
        assert "Ablation" in section

    def test_generate_conclusion(self):
        gen = PaperGenerator()
        conclusion = gen.generate_conclusion()
        assert "Conclusion" in conclusion

    def test_generate_full_paper(self):
        gen = PaperGenerator()
        paper = gen.generate_full_paper()
        assert "Phoenix" in paper
        assert "Introduction" in paper
        assert "Conclusion" in paper


class TestReproducibilityManager:
    def test_record_run(self):
        mgr = ReproducibilityManager()
        run = mgr.record_run(
            experiment_id="E1",
            parameters={"model": "gpt-4"},
            results={"accuracy": 0.95},
            random_seed=42,
        )
        assert run.run_id is not None
        assert run.data_hash is not None

    def test_verify_run(self):
        mgr = ReproducibilityManager()
        run = mgr.record_run(
            experiment_id="E1",
            parameters={"model": "gpt-4"},
            results={"accuracy": 0.95},
        )
        verification = mgr.verify_run(run.run_id)
        assert verification["valid"] is True

    def test_compare_runs(self):
        mgr = ReproducibilityManager()
        run1 = mgr.record_run("E1", {"x": 1}, {"acc": 0.9})
        run2 = mgr.record_run("E1", {"x": 1}, {"acc": 0.95})
        comparison = mgr.compare_runs(run1.run_id, run2.run_id)
        assert comparison["comparable"] is True
        assert comparison["results_match"] is False

    def test_list_runs(self):
        mgr = ReproducibilityManager()
        mgr.record_run("E1", {}, {"acc": 0.9})
        mgr.record_run("E2", {}, {"acc": 0.8})
        runs = mgr.list_runs()
        assert len(runs) == 2
        e1_runs = mgr.list_runs(experiment_id="E1")
        assert len(e1_runs) == 1
