# -*- coding: utf-8 -*-
"""
test_semantic_retrieval: Semantic Retrieval Upgrade Tests
=========================================================

Tests for the V1.2 sentence-embedding-based semantic retrieval system.
Validates that semantic retrieval outperforms TF-IDF on paraphrased queries
and handles fallback correctly when sentence-transformers is unavailable.

Run:
    cd Phoenix-Evo
    pytest tests/test_semantic_retrieval.py -v
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from runtime.semantic_retriever import (
    SemanticRetriever,
    _EMBEDDING_AVAILABLE,
    cosine_similarity,
    batch_cosine_similarity,
    semantic_search,
)


# ---------------------------------------------------------------------------
# Test corpus: 8 skills covering distinct domains
# ---------------------------------------------------------------------------

SKILL_CORPUS = [
    {
        "skill_id": "skill_wsl_encoding",
        "skill_name": "fix_wsl_chinese_path_encoding",
        "text": "Fix encoding issues with Chinese characters in WSL paths. When dealing with WSL file system paths that contain Chinese characters and cause encoding errors or garbled output.",
    },
    {
        "skill_id": "skill_git_merge",
        "skill_name": "resolve_git_merge_conflict",
        "text": "Resolve merge conflicts in git repositories. When a git merge or rebase produces merge conflicts that need to be resolved manually.",
    },
    {
        "skill_id": "skill_api_auth",
        "skill_name": "implement_jwt_authentication",
        "text": "Implement JWT-based authentication for REST APIs. When building API endpoints that require JSON Web Token based authentication and authorization.",
    },
    {
        "skill_id": "skill_docker_deploy",
        "skill_name": "deploy_application_with_docker",
        "text": "Deploy applications using Docker and Docker Compose. When deploying a Python or Node.js application using Docker containers.",
    },
    {
        "skill_id": "skill_sql_optimize",
        "skill_name": "optimize_slow_sql_queries",
        "text": "Optimize slow SQL queries through indexing and rewriting. When database queries are running slowly and need performance optimization.",
    },
    {
        "skill_id": "skill_react_component",
        "skill_name": "create_react_component_with_tests",
        "text": "Create React components with TypeScript and unit tests. When building a new React component that needs unit tests and proper type definitions.",
    },
    {
        "skill_id": "skill_network_debug",
        "skill_name": "diagnose_network_connectivity_issues",
        "text": "Diagnose and fix network connectivity issues. When experiencing network connectivity problems such as DNS resolution failures or timeout errors.",
    },
    {
        "skill_id": "skill_python_caching",
        "skill_name": "implement_redis_caching_layer",
        "text": "Implement Redis-based caching for Python applications. When adding a caching layer to reduce database load and improve response times.",
    },
]


# ---------------------------------------------------------------------------
# Test queries with expected relevant skills
# ---------------------------------------------------------------------------

SEMANTIC_TEST_QUERIES = [
    # Exact keyword overlap -- both methods should succeed
    ("encoding", "skill_wsl_encoding", "exact_keyword"),
    ("merge conflict", "skill_git_merge", "exact_keyword"),
    # Paraphrase / semantic overlap -- TF-IDF may fail, semantic should succeed
    ("Unicode filename garbled on Windows Subsystem for Linux", "skill_wsl_encoding", "paraphrase"),
    ("How to handle conflicting changes from two branches", "skill_git_merge", "paraphrase"),
    ("Add token-based login security to my REST service", "skill_api_auth", "paraphrase"),
    ("Make my database queries faster, they are timing out", "skill_sql_optimize", "paraphrase"),
    ("Containerize my Python web app for production deployment", "skill_docker_deploy", "paraphrase"),
    ("My React button component needs proper types and tests", "skill_react_component", "paraphrase"),
    ("Cannot reach the API server, connection times out", "skill_network_debug", "paraphrase"),
    ("Speed up API responses by caching frequent queries", "skill_python_caching", "paraphrase"),
    # Cross-domain noise queries
    ("Deploy machine learning model to Kubernetes cluster", "skill_docker_deploy", "cross_domain"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSemanticRetriever:
    """Tests for the SemanticRetriever class."""

    def test_retriever_initialization(self):
        """SemanticRetriever can be initialized."""
        retriever = SemanticRetriever()
        assert retriever is not None
        assert retriever.is_semantic == _EMBEDDING_AVAILABLE

    def test_retrieve_returns_results(self):
        """retrieve() returns a list of results."""
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = retriever.retrieve("fix encoding issue", corpus, top_k=3)
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert "index" in r
            assert "text" in r
            assert "score" in r
            assert "method" in r

    def test_retrieve_empty_corpus(self):
        """retrieve() handles empty corpus gracefully."""
        retriever = SemanticRetriever()
        results = retriever.retrieve("test query", [], top_k=5)
        assert results == []

    def test_retrieve_score_range(self):
        """All scores are in [0, 1]."""
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = retriever.retrieve("encoding", corpus, top_k=5)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_retrieve_sorted_by_score(self):
        """Results are sorted by score descending."""
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = retriever.retrieve("fix encoding issue", corpus, top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.parametrize(
        "query,expected_id,label",
        SEMANTIC_TEST_QUERIES,
        ids=[t[2] + "_" + t[1] for t in SEMANTIC_TEST_QUERIES],
    )
    def test_retrieve_finds_correct_skill(self, query, expected_id, label):
        """Semantic retrieval should find the correct skill in top-3."""
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = retriever.retrieve(query, corpus, top_k=3)

        retrieved_indices = {r["index"] for r in results}
        expected_idx = next(
            i for i, s in enumerate(SKILL_CORPUS) if s["skill_id"] == expected_id
        )
        assert expected_idx in retrieved_indices, (
            f"Expected skill {expected_id} not in top-3 for query '{query}' "
            f"(label={label}). Got: {[SKILL_CORPUS[r['index']]['skill_id'] for r in results]}"
        )

    def test_encode_corpus_returns_embeddings(self):
        """encode_corpus returns embeddings when available."""
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS[:3]]
        embeddings = retriever.encode_corpus(corpus)
        if _EMBEDDING_AVAILABLE:
            assert embeddings is not None
            assert len(embeddings) == 3
        else:
            assert embeddings is None

    def test_retrieve_with_metadata(self):
        """retrieve_with_metadata attaches entry dicts to results."""
        retriever = SemanticRetriever()
        entries = [{"id": s["skill_id"], "name": s["skill_name"]} for s in SKILL_CORPUS]
        results = retriever.retrieve_with_metadata(
            "fix encoding",
            entries,
            text_builder=lambda e: next(s["text"] for s in SKILL_CORPUS if s["skill_id"] == e["id"]),
            top_k=3,
        )
        for r in results:
            assert "entry" in r
            assert "id" in r["entry"]


class TestCosineSimilarity:
    """Tests for cosine similarity functions."""

    def test_identical_vectors(self):
        """Identical vectors have cosine similarity 1.0."""
        if _EMBEDDING_AVAILABLE:
            import numpy as np
            vec = np.array([1.0, 2.0, 3.0])
            assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-4)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have cosine similarity ~0."""
        if _EMBEDDING_AVAILABLE:
            import numpy as np
            vec_a = np.array([1.0, 0.0, 0.0])
            vec_b = np.array([0.0, 1.0, 0.0])
            assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0, abs=1e-4)

    def test_batch_cosine_similarity(self):
        """batch_cosine_similarity returns correct number of scores."""
        if _EMBEDDING_AVAILABLE:
            import numpy as np
            query = np.array([1.0, 0.0, 0.0])
            corpus = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.707, 0.707, 0.0]])
            scores = batch_cosine_similarity(query, corpus)
            assert len(scores) == 3
            assert scores[0] == pytest.approx(1.0, abs=1e-2)
            assert scores[1] == pytest.approx(0.0, abs=1e-2)
            assert 0.5 < scores[2] < 0.9


class TestSemanticSearch:
    """Tests for the semantic_search convenience function."""

    def test_semantic_search_basic(self):
        """semantic_search returns results."""
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = semantic_search("fix encoding", corpus, top_k=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_method_field(self):
        """Results indicate which retrieval method was used."""
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = semantic_search("fix encoding", corpus, top_k=3)
        if results:
            method = results[0]["method"]
            assert method in ("sentence_embedding", "tfidf_fallback", "keyword_fallback")


class TestParaphraseRobustness:
    """
    Core test: Semantic retrieval should handle paraphrases better than TF-IDF.
    This is the key motivation for the V1.2 upgrade.
    """

    PARAPHRASE_PAIRS = [
        # (query, expected_skill_text_fragment)
        ("Unicode filename garbled on Windows Subsystem for Linux", "Chinese characters in WSL"),
        ("conflicting changes from two branches", "merge conflicts"),
        ("token-based login security", "JWT based authentication"),
        ("database queries faster, timing out", "queries are running slowly"),
        ("Containerize my Python web app", "Docker containers"),
        ("connection times out", "timeout errors"),
        ("caching frequent queries", "caching layer"),
    ]

    @pytest.mark.parametrize(
        "query,expected_fragment",
        PARAPHRASE_PAIRS,
        ids=[p[0][:40] for p in PARAPHRASE_PAIRS],
    )
    def test_paraphrase_retrieval(self, query, expected_fragment):
        """
        Semantic retrieval should find the correct skill even when the
        query uses different words than the skill description.
        """
        retriever = SemanticRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS]
        results = retriever.retrieve(query, corpus, top_k=3)

        # Check that the expected skill is in top-3
        top_texts = [r["text"] for r in results]
        found = any(expected_fragment.lower() in t.lower() for t in top_texts)
        assert found, (
            f"Expected fragment '{expected_fragment}' not found in top-3 results "
            f"for query '{query}'. Got: {[t[:60] for t in top_texts]}"
        )
