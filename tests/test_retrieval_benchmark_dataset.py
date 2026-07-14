"""
Tests for the real retrieval benchmark package
(experiments/retrieval_benchmark/).

Covers dataset integrity, metric correctness on hand-computed examples,
statistical determinism, and end-to-end method sanity.
"""

import pytest

from experiments.retrieval_benchmark import dataset, metrics
from experiments.retrieval_benchmark.dataset import (
    QUERIES,
    SKILLS,
    searchable_text,
    validate_dataset,
)
from experiments.retrieval_benchmark.methods import (
    available_methods,
    bm25_rank,
    keyword_rank,
    tfidf_rank,
)


class TestDatasetIntegrity:
    def test_dataset_is_valid(self):
        assert validate_dataset() == []

    def test_corpus_size(self):
        assert len(SKILLS) == 40

    def test_query_counts_by_category(self):
        counts = {}
        for q in QUERIES:
            counts[q.category] = counts.get(q.category, 0) + 1
        assert counts == {
            "exact_keyword": 10,
            "paraphrase": 20,
            "cross_domain": 10,
            "multi_intent": 8,
            "negative": 12,
        }

    def test_judged_and_negative_split(self):
        assert len(dataset.judged_queries()) == 48
        assert len(dataset.negative_queries()) == 12

    def test_grounded_skills_present(self):
        grounded = [s for s in SKILLS if s.grounded_in_repo]
        assert len(grounded) == 15

    def test_searchable_text_includes_name_words(self):
        skill = SKILLS[0]
        text = searchable_text(skill)
        assert "_" not in text.split(".")[0]
        assert skill.text in text


class TestMetrics:
    """Hand-computed examples pin the metric implementations."""

    QRELS = {"a": 2, "b": 1}

    def test_precision_at_k(self):
        assert metrics.precision_at_k(["a", "x", "b"], self.QRELS, 3) == pytest.approx(2 / 3)
        assert metrics.precision_at_k(["x", "y"], self.QRELS, 2) == 0.0

    def test_recall_at_k(self):
        assert metrics.recall_at_k(["a", "x", "y"], self.QRELS, 3) == pytest.approx(0.5)
        assert metrics.recall_at_k(["a", "b"], self.QRELS, 2) == pytest.approx(1.0)

    def test_mrr(self):
        assert metrics.mrr(["x", "a"], self.QRELS) == pytest.approx(0.5)
        assert metrics.mrr(["x", "y"], self.QRELS) == 0.0

    def test_ndcg_perfect_ranking_is_one(self):
        assert metrics.ndcg_at_k(["a", "b"], self.QRELS, 5) == pytest.approx(1.0)

    def test_ndcg_worse_ranking_is_less_than_one(self):
        swapped = metrics.ndcg_at_k(["b", "a"], self.QRELS, 5)
        assert 0.0 < swapped < 1.0

    def test_ndcg_no_relevant_retrieved(self):
        assert metrics.ndcg_at_k(["x", "y"], self.QRELS, 5) == 0.0

    def test_bootstrap_deterministic(self):
        values = [0.1, 0.5, 0.9, 0.3]
        ci1 = metrics.bootstrap_ci(values, n_resamples=500, seed=7)
        ci2 = metrics.bootstrap_ci(values, n_resamples=500, seed=7)
        assert ci1 == ci2
        assert ci1[0] <= sum(values) / len(values) <= ci1[1]

    def test_permutation_test_identical_distributions(self):
        vals = [0.5, 0.6, 0.7, 0.4]
        p = metrics.paired_permutation_test(vals, vals, n_resamples=200, seed=1)
        assert p == 1.0

    def test_permutation_test_detects_large_difference(self):
        a = [1.0] * 12
        b = [0.0] * 12
        p = metrics.paired_permutation_test(a, b, n_resamples=2000, seed=1)
        assert p < 0.01


class TestMethods:
    CORPUS = [searchable_text(s) for s in SKILLS]
    IDS = [s.skill_id for s in SKILLS]

    @pytest.mark.parametrize("rank_fn", [tfidf_rank, bm25_rank, keyword_rank])
    def test_full_ranking_returned(self, rank_fn):
        ranking = rank_fn("resolve git merge conflict", self.CORPUS)
        assert len(ranking) == len(self.CORPUS)
        scores = [s for _, s in ranking]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.parametrize("rank_fn", [tfidf_rank, bm25_rank, keyword_rank])
    def test_exact_keyword_query_hits_target(self, rank_fn):
        ranking = rank_fn("resolve git merge conflict", self.CORPUS)
        top3 = {self.IDS[i] for i, _ in ranking[:3]}
        assert "skill_git_merge" in top3

    def test_available_methods_always_includes_lexical(self):
        methods, unavailable = available_methods()
        assert {"tfidf", "bm25", "keyword"} <= set(methods.keys())
        # embedding is either runnable or has a recorded reason -- never silent
        assert ("embedding" in methods) != ("embedding" in unavailable)
