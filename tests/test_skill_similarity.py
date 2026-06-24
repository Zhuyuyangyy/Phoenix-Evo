"""
Tests for SkillSimilarity module.
"""

import pytest

from core.skill_similarity import (
    SimilarityResult,
    SkillVectorizer,
    _compute_idf,
    _cosine_sim,
    _name_similarity,
    _tfidf_vector,
    _tokenize,
)


class TestTokenize:
    """Test suite for tokenization."""

    def test_tokenize_english(self):
        """Test English tokenization."""
        tokens = _tokenize("Fix WSL Chinese path encoding")
        assert "fix" in tokens
        assert "wsl" in tokens

    def test_tokenize_chinese(self):
        """Test Chinese tokenization."""
        tokens = _tokenize("修复WSL中文路径编码问题")
        assert any("修复" in t for t in tokens)

    def test_tokenize_mixed(self):
        """Test mixed Chinese/English tokenization."""
        tokens = _tokenize("Fix WSL 中文路径 encoding")
        assert "fix" in tokens
        assert "wsl" in tokens
        assert any("中文" in t for t in tokens)

    def test_tokenize_short_tokens_filtered(self):
        """Test that short tokens are filtered."""
        tokens = _tokenize("a bb ccc")
        assert "a" not in tokens
        assert "bb" in tokens
        assert "ccc" in tokens


class TestCosineSimilarity:
    """Test suite for cosine similarity."""

    def test_identical_vectors(self):
        """Test similarity of identical vectors."""
        vec = {"a": 1.0, "b": 2.0, "c": 3.0}
        assert _cosine_sim(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors."""
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert _cosine_sim(vec_a, vec_b) == 0.0

    def test_similar_vectors(self):
        """Test similarity of similar vectors."""
        vec_a = {"a": 1.0, "b": 0.5}
        vec_b = {"a": 0.9, "b": 0.6}
        sim = _cosine_sim(vec_a, vec_b)
        assert 0.8 < sim < 1.0

    def test_empty_vectors(self):
        """Test similarity of empty vectors."""
        assert _cosine_sim({}, {}) == 0.0

    def test_one_empty_vector(self):
        """Test similarity with one empty vector."""
        vec = {"a": 1.0}
        assert _cosine_sim(vec, {}) == 0.0


class TestNameSimilarity:
    """Test suite for name similarity."""

    def test_identical_names(self):
        """Test similarity of identical names."""
        assert _name_similarity("test_skill", "test_skill") == 1.0

    def test_similar_names(self):
        """Test similarity of similar names."""
        sim = _name_similarity("fix_wsl_path", "fix_wsl_encoding")
        assert sim > 0.3

    def test_different_names(self):
        """Test similarity of different names."""
        sim = _name_similarity("fix_wsl_path", "deploy_kubernetes")
        assert sim < 0.5

    def test_empty_names(self):
        """Test similarity with empty names."""
        assert _name_similarity("", "test") == 0.0
        assert _name_similarity("test", "") == 0.0


class TestIDF:
    """Test suite for IDF computation."""

    def test_compute_idf_basic(self):
        """Test basic IDF computation."""
        documents = [["a", "b", "c"], ["b", "c", "d"]]
        vocab = {"a", "b", "c", "d"}
        idf = _compute_idf(documents, vocab)
        assert "a" in idf
        assert "b" in idf
        # "a" appears in 1 doc, "b" in 2 docs
        assert idf["a"] > idf["b"]

    def test_compute_idf_single_doc(self):
        """Test IDF computation with single document."""
        documents = [["a", "b"]]
        vocab = {"a", "b"}
        idf = _compute_idf(documents, vocab)
        assert idf["a"] == idf["b"]


class TestTFIDF:
    """Test suite for TF-IDF vectorization."""

    def test_tfidf_vector_basic(self):
        """Test basic TF-IDF vectorization."""
        tokens = ["a", "b", "a"]
        idf = {"a": 1.5, "b": 2.0}
        vec = _tfidf_vector(tokens, idf)
        assert "a" in vec
        assert "b" in vec
        assert vec["a"] > vec["b"]  # "a" appears twice

    def test_tfidf_vector_unknown_term(self):
        """Test TF-IDF with unknown terms."""
        tokens = ["a", "unknown"]
        idf = {"a": 1.5}
        vec = _tfidf_vector(tokens, idf)
        assert "a" in vec
        assert "unknown" not in vec


class TestSkillVectorizer:
    """Test suite for SkillVectorizer."""

    def _make_entries(self):
        """Helper to create test skill entries."""
        return [
            {
                "skill_id": "skill_001",
                "skill_name": "fix_wsl_path",
                "status": "active",
            },
            {
                "skill_id": "skill_002",
                "skill_name": "fix_wsl_encoding",
                "status": "active",
            },
            {
                "skill_id": "skill_003",
                "skill_name": "deploy_kubernetes",
                "status": "active",
            },
        ]

    def test_init_builds_vectors(self, tmp_path):
        """Test that initialization builds vectors."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        assert len(vectorizer.vectors) == len(entries)

    def test_compute_pairwise_returns_results(self, tmp_path):
        """Test that compute_pairwise returns results."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        results = vectorizer.compute_pairwise()
        assert len(results) > 0
        assert isinstance(results[0], SimilarityResult)

    def test_compute_pairwise_sorted(self, tmp_path):
        """Test that results are sorted by score."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        results = vectorizer.compute_pairwise()
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_get_groups(self, tmp_path):
        """Test that get_groups returns groups."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        groups = vectorizer.get_groups()
        assert len(groups) > 0
        # Each skill should be in exactly one group
        all_ids = [sid for group in groups for sid in group]
        assert len(all_ids) == len(entries)

    def test_similarity_result_fields(self, tmp_path):
        """Test that SimilarityResult has all required fields."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        results = vectorizer.compute_pairwise()
        result = results[0]
        assert hasattr(result, "skill_a")
        assert hasattr(result, "skill_b")
        assert hasattr(result, "score")
        assert hasattr(result, "name_sim")
        assert hasattr(result, "content_sim")
        assert hasattr(result, "recommendation")

    def test_recommendation_values(self, tmp_path):
        """Test that recommendation values are valid."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        results = vectorizer.compute_pairwise()
        for result in results:
            assert result.recommendation in ("merge", "review", "independent")

    def test_score_range(self, tmp_path):
        """Test that scores are in valid range."""
        entries = self._make_entries()
        vectorizer = SkillVectorizer(entries, root=tmp_path)
        results = vectorizer.compute_pairwise()
        for result in results:
            assert 0.0 <= result.score <= 1.0
            assert 0.0 <= result.name_sim <= 1.0
            assert 0.0 <= result.content_sim <= 1.0
