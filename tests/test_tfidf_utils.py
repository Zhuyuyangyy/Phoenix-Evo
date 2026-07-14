"""Tests for runtime/tfidf_utils.py — extracted TF-IDF utilities."""

from __future__ import annotations

import math

from runtime.tfidf_utils import (
    _compute_idf,
    _cosine_sim,
    _tfidf_vector,
    _tokenize,
    _tokenize_to_set,
    _word_split,
)


class TestTokenize:
    def test_english_tokens(self):
        tokens = _tokenize("fix encoding issue")
        assert "fix" in tokens
        assert "encoding" in tokens
        assert "issue" in tokens

    def test_short_tokens_filtered(self):
        tokens = _tokenize("a b cd ef")
        # Single-char English tokens should be filtered (MIN_TOKEN_LEN=2)
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "ef" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_chinese_chars(self):
        tokens = _tokenize("编码")
        # Chinese chars produce single chars + bigrams
        assert len(tokens) > 0

    def test_mixed(self):
        tokens = _tokenize("fix 编码 bug")
        assert "fix" in tokens
        assert "bug" in tokens
        assert len(tokens) >= 4  # at least 2 English + Chinese chars/bigrams


class TestTokenizeToSet:
    def test_deduplication(self):
        result = _tokenize_to_set("fix fix encoding encoding")
        assert "fix" in result
        assert "encoding" in result
        assert len(result) == 2  # deduplicated

    def test_empty(self):
        assert _tokenize_to_set("") == set()


class TestComputeIDF:
    def test_basic(self):
        docs = [["a", "b"], ["b", "c"]]
        idf = _compute_idf(docs)
        assert "a" in idf
        assert "b" in idf
        assert "c" in idf
        # 'b' appears in both docs → lower IDF
        assert idf["b"] < idf["a"]
        assert idf["b"] < idf["c"]

    def test_smoothed(self):
        docs = [["a"], ["b"]]
        idf = _compute_idf(docs)
        # smoothed IDF: ln((N+1)/(df+1)) + 1
        expected_a = math.log((2 + 1) / (1 + 1)) + 1
        assert abs(idf["a"] - expected_a) < 1e-9

    def test_empty_corpus(self):
        idf = _compute_idf([])
        assert idf == {}

    def test_single_doc(self):
        docs = [["a", "b", "c"]]
        idf = _compute_idf(docs)
        # All terms appear once → same IDF
        assert idf["a"] == idf["b"] == idf["c"]


class TestTfidfVector:
    def test_basic(self):
        tokens = ["a", "a", "b"]
        idf = {"a": 1.0, "b": 2.0}
        vec = _tfidf_vector(tokens, idf)
        assert "a" in vec
        assert "b" in vec
        # a appears twice → higher TF
        assert vec["a"] > 0
        assert vec["b"] > 0

    def test_empty_tokens(self):
        vec = _tfidf_vector([], {"a": 1.0})
        assert vec == {}

    def test_unknown_term(self):
        vec = _tfidf_vector(["a", "x"], {"a": 1.0})
        assert "a" in vec
        assert "x" not in vec  # not in IDF → skipped


class TestCosineSim:
    def test_identical_vectors(self):
        vec = {"a": 1.0, "b": 2.0}
        sim = _cosine_sim(vec, vec)
        assert abs(sim - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        sim = _cosine_sim(vec_a, vec_b)
        assert sim == 0.0

    def test_empty_vectors(self):
        assert _cosine_sim({}, {"a": 1.0}) == 0.0

    def test_partial_overlap(self):
        vec_a = {"a": 1.0, "b": 1.0}
        vec_b = {"a": 1.0, "c": 1.0}
        sim = _cosine_sim(vec_a, vec_b)
        assert 0.0 < sim < 1.0


class TestWordSplit:
    def test_returns_set(self):
        result = _word_split("fix encoding")
        assert isinstance(result, set)
        assert "fix" in result
        assert "encoding" in result

    def test_empty(self):
        assert _word_split("") == set()


class TestModuleImportSafety:
    """Verify that tfidf_utils has no circular import dependencies."""

    def test_import_does_not_trigger_core_init(self):
        # If this import succeeds, there's no circular dependency
        import importlib
        import sys

        # Remove any cached modules to force fresh import
        for mod in list(sys.modules):
            if "tfidf_utils" in mod or "skill_retriever" in mod:
                del sys.modules[mod]

        mod = importlib.import_module("runtime.tfidf_utils")
        assert hasattr(mod, "_compute_idf")
        assert hasattr(mod, "_tokenize")
