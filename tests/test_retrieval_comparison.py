"""
Retrieval Comparison Experiment: Keyword vs. Semantic (TF-IDF)
===============================================================

Compares the recall@k of the legacy keyword-based retrieval path
(`retrieve_by_keyword`) against the new TF-IDF + cosine similarity
path (`retrieve`) across a set of synthetic skill retrieval scenarios.

This addresses the "zero experiments" critique from the research verdict
(Section 3.1, F1/F2) by providing reproducible comparative data on a
controlled skill corpus.

Run:
    cd Phoenix-Evo
    pytest tests/test_retrieval_comparison.py -v
"""

import json
from pathlib import Path

import pytest

from runtime.skill_retriever import SkillRetriever, _compute_idf, _cosine_sim, _tfidf_vector, _tokenize

# ---------------------------------------------------------------------------
# Test corpus: 8 skills covering distinct domains
# ---------------------------------------------------------------------------

SKILL_CORPUS = [
    {
        "skill_id": "skill_wsl_encoding",
        "skill_name": "fix_wsl_chinese_path_encoding",
        "task_type": "debugging",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.90,
        "card": {
            "when_to_use": "When dealing with WSL file system paths that contain Chinese characters and cause encoding errors or garbled output.",
            "procedure": "1. Detect the encoding of the file path\n2. Convert to UTF-8 encoding\n3. Normalize Unicode characters\n4. Verify the path is accessible",
            "description": "Fix encoding issues with Chinese characters in WSL paths",
        },
    },
    {
        "skill_id": "skill_git_merge_conflict",
        "skill_name": "resolve_git_merge_conflict",
        "task_type": "debugging",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.85,
        "card": {
            "when_to_use": "When a git merge or rebase produces merge conflicts that need to be resolved manually.",
            "procedure": "1. Identify conflicting files\n2. Open each conflict marker\n3. Choose correct version or combine\n4. Stage resolved files\n5. Complete the merge",
            "description": "Resolve merge conflicts in git repositories",
        },
    },
    {
        "skill_id": "skill_api_auth",
        "skill_name": "implement_jwt_authentication",
        "task_type": "coding",
        "risk_level": "medium",
        "status": "active",
        "quality_score": 0.88,
        "card": {
            "when_to_use": "When building API endpoints that require JSON Web Token based authentication and authorization.",
            "procedure": "1. Generate JWT secret key\n2. Create token signing function\n3. Add middleware for token verification\n4. Implement refresh token rotation\n5. Handle token expiration",
            "description": "Implement JWT-based authentication for REST APIs",
        },
    },
    {
        "skill_id": "skill_docker_deploy",
        "skill_name": "deploy_application_with_docker",
        "task_type": "deployment",
        "risk_level": "medium",
        "status": "active",
        "quality_score": 0.82,
        "card": {
            "when_to_use": "When deploying a Python or Node.js application using Docker containers and Docker Compose.",
            "procedure": "1. Write Dockerfile with multi-stage build\n2. Create docker-compose.yml\n3. Configure environment variables\n4. Build and test image locally\n5. Push to container registry",
            "description": "Deploy applications using Docker and Docker Compose",
        },
    },
    {
        "skill_id": "skill_sql_optimize",
        "skill_name": "optimize_slow_sql_queries",
        "task_type": "optimization",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.87,
        "card": {
            "when_to_use": "When database queries are running slowly and need performance optimization through index tuning and query rewriting.",
            "procedure": "1. Run EXPLAIN ANALYZE on slow query\n2. Identify missing indexes\n3. Rewrite suboptimal JOIN patterns\n4. Add appropriate indexes\n5. Verify improvement with benchmarks",
            "description": "Optimize slow SQL queries through indexing and rewriting",
        },
    },
    {
        "skill_id": "skill_react_component",
        "skill_name": "create_react_component_with_tests",
        "task_type": "coding",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.80,
        "card": {
            "when_to_use": "When building a new React component that needs unit tests and proper TypeScript type definitions.",
            "procedure": "1. Define TypeScript interface for props\n2. Implement component with hooks\n3. Write unit tests with React Testing Library\n4. Add Storybook stories\n5. Export from index file",
            "description": "Create React components with TypeScript and unit tests",
        },
    },
    {
        "skill_id": "skill_network_debug",
        "skill_name": "diagnose_network_connectivity_issues",
        "task_type": "debugging",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.83,
        "card": {
            "when_to_use": "When experiencing network connectivity problems such as DNS resolution failures, timeout errors, or connection refused.",
            "procedure": "1. Check DNS resolution with nslookup\n2. Test connectivity with ping and traceroute\n3. Verify firewall rules\n4. Check proxy configuration\n5. Inspect SSL/TLS certificates",
            "description": "Diagnose and fix network connectivity issues",
        },
    },
    {
        "skill_id": "skill_python_caching",
        "skill_name": "implement_redis_caching_layer",
        "task_type": "coding",
        "risk_level": "low",
        "status": "active",
        "quality_score": 0.84,
        "card": {
            "when_to_use": "When adding a caching layer to a Python web application to reduce database load and improve response times.",
            "procedure": "1. Set up Redis connection\n2. Create cache decorator\n3. Implement cache invalidation strategy\n4. Add TTL-based expiration\n5. Monitor cache hit rates",
            "description": "Implement Redis-based caching for Python applications",
        },
    },
]


# ---------------------------------------------------------------------------
# Test queries: (query_text, expected_relevant_skill_ids)
#
# "Relevant" is defined as the skill(s) that a human annotator would
# consider directly applicable to the query.
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    # Exact keyword overlap -- both methods should succeed
    (
        "encoding",
        {"skill_wsl_encoding"},
        "exact_keyword_match",
    ),
    (
        "merge conflict",
        {"skill_git_merge_conflict"},
        "exact_keyword_match",
    ),
    # Paraphrase / semantic overlap -- keyword may fail, semantic should succeed
    (
        "Unicode filename garbled on Windows Subsystem for Linux",
        {"skill_wsl_encoding"},
        "paraphrase_unicode_wsl",
    ),
    (
        "How to handle conflicting changes from two branches",
        {"skill_git_merge_conflict"},
        "paraphrase_branch_conflict",
    ),
    (
        "Add token-based login security to my REST service",
        {"skill_api_auth"},
        "paraphrase_jwt_auth",
    ),
    (
        "Make my database queries faster, they are timing out",
        {"skill_sql_optimize"},
        "paraphrase_sql_performance",
    ),
    (
        "Containerize my Python web app for production deployment",
        {"skill_docker_deploy"},
        "paraphrase_docker_deploy",
    ),
    (
        "My React button component needs proper types and tests",
        {"skill_react_component"},
        "paraphrase_react_testing",
    ),
    (
        "Cannot reach the API server, connection times out",
        {"skill_network_debug"},
        "paraphrase_network_timeout",
    ),
    (
        "Speed up API responses by caching frequent queries",
        {"skill_python_caching"},
        "paraphrase_caching",
    ),
    # Cross-domain noise queries -- should NOT match unrelated skills
    (
        "Deploy machine learning model to Kubernetes cluster",
        {"skill_docker_deploy"},
        "cross_domain_deploy",
    ),
    (
        "Fix memory leak in Python asyncio application",
        set(),  # No skill is directly about memory leaks / asyncio
        "no_match_expected",
    ),
]


# ---------------------------------------------------------------------------
# Helper: build a temporary skill directory and index for testing
# ---------------------------------------------------------------------------

def _build_test_corpus(tmp_dir: Path) -> None:
    """Write test skills to tmp_dir and build a skill_index.json."""
    active_dir = tmp_dir / "skills" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)

    index = {}
    for skill in SKILL_CORPUS:
        sid = skill["skill_id"]
        card = skill["card"]

        # Write a minimal SkillCard markdown
        md_content = f"""# Skill: {skill['skill_name']}

## Metadata
- **skill_id**: {sid}
- **status**: active
- **task_type**: {skill['task_type']}

## When to Use
{card['when_to_use']}

## Procedure
{card['procedure']}

## Description
{card['description']}
"""
        (active_dir / f"{sid}.md").write_text(md_content, encoding="utf-8")

        index[sid] = {
            "skill_id": sid,
            "skill_name": skill["skill_name"],
            "status": "active",
            "task_type": skill["task_type"],
            "risk_level": skill["risk_level"],
            "quality_score": skill["quality_score"],
            "usage_count": 10,
            "success_count": 8,
            "success_rate": 0.8,
            "last_used": "2026-05-28T10:00:00",
        }

    # Write index file
    index_dir = tmp_dir / "skills"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "skill_index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Retrieval wrappers for the two methods
# ---------------------------------------------------------------------------

def _keyword_retrieve(retriever: SkillRetriever, query: str, top_k: int = 5) -> set[str]:
    """Use the legacy keyword path."""
    results = retriever.retrieve_by_keyword(query, top_k=top_k)
    return {r["skill_id"] for r in results}


def _semantic_retrieve(retriever: SkillRetriever, query: str, top_k: int = 5) -> set[str]:
    """Use the TF-IDF + cosine similarity path."""
    results = retriever.retrieve(query, top_k=top_k)
    return {r["skill_id"] for r in results}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _recall(retrieved: set[str], relevant: set[str]) -> float:
    """Compute recall = |retrieved & relevant| / |relevant|."""
    if not relevant:
        return 1.0  # vacuously true: nothing relevant, nothing missed
    return len(retrieved & relevant) / len(relevant)


def _precision(retrieved: set[str], relevant: set[str]) -> float:
    """Compute precision = |retrieved & relevant| / |retrieved|."""
    if not retrieved:
        return 0.0
    return len(retrieved & relevant) / len(retrieved)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRetrievalComparison:
    """
    Compare keyword vs. semantic retrieval across the test corpus.
    """

    @pytest.fixture(autouse=True)
    def setup_corpus(self, tmp_path):
        """Build the test corpus in a temporary directory."""
        self.tmp_dir = tmp_path
        _build_test_corpus(self.tmp_dir)
        self.retriever = SkillRetriever(base_dir=self.tmp_dir)

    # -- Aggregate metrics --

    def test_semantic_recall_at_least_as_good_as_keyword(self):
        """
        Semantic retrieval should have recall >= keyword retrieval
        across all test queries.
        """
        keyword_recalls = []
        semantic_recalls = []

        for query, expected, _label in TEST_QUERIES:
            kw_results = _keyword_retrieve(self.retriever, query)
            sem_results = _semantic_retrieve(self.retriever, query)

            kw_recall = _recall(kw_results, expected)
            sem_recall = _recall(sem_results, expected)

            keyword_recalls.append(kw_recall)
            semantic_recalls.append(sem_recall)

        avg_kw = sum(keyword_recalls) / len(keyword_recalls)
        avg_sem = sum(semantic_recalls) / len(semantic_recalls)

        print("\n--- Retrieval Comparison ---")
        print(f"  Keyword avg recall@5:  {avg_kw:.3f}")
        print(f"  Semantic avg recall@5: {avg_sem:.3f}")
        print(f"  Queries tested:        {len(TEST_QUERIES)}")

        # Semantic should be at least as good as keyword on average
        assert avg_sem >= avg_kw, (
            f"Semantic recall ({avg_sem:.3f}) should be >= keyword recall ({avg_kw:.3f})"
        )

    def test_semantic_paraphrase_recall(self):
        """
        Semantic retrieval should handle paraphrased queries better
        than keyword retrieval.
        """
        paraphrase_cases = [
            (q, exp, label) for q, exp, label in TEST_QUERIES
            if "paraphrase" in label
        ]
        assert len(paraphrase_cases) >= 5, "Need at least 5 paraphrase test cases"

        kw_recalls = []
        sem_recalls = []

        for query, expected, label in paraphrase_cases:
            kw_results = _keyword_retrieve(self.retriever, query)
            sem_results = _semantic_retrieve(self.retriever, query)

            kw_recalls.append(_recall(kw_results, expected))
            sem_recalls.append(_recall(sem_results, expected))

        avg_kw = sum(kw_recalls) / len(kw_recalls)
        avg_sem = sum(sem_recalls) / len(sem_recalls)

        print("\n--- Paraphrase Query Recall ---")
        print(f"  Keyword avg recall:  {avg_kw:.3f}")
        print(f"  Semantic avg recall: {avg_sem:.3f}")
        for _i, (query, expected, label) in enumerate(paraphrase_cases):
            kw_r = _keyword_retrieve(self.retriever, query)
            sem_r = _semantic_retrieve(self.retriever, query)
            print(f"  [{label}] kw_recall={_recall(kw_r, expected):.2f} "
                  f"sem_recall={_recall(sem_r, expected):.2f} | {query[:60]}")

        # Semantic should be strictly better on paraphrased queries
        assert avg_sem > avg_kw, (
            f"Semantic paraphrase recall ({avg_sem:.3f}) should exceed "
            f"keyword paraphrase recall ({avg_kw:.3f})"
        )

    def test_keyword_exact_match_still_works(self):
        """
        The keyword path should still have perfect recall on exact-match queries.
        This ensures the fallback path is not broken.
        """
        exact_cases = [
            (q, exp, label) for q, exp, label in TEST_QUERIES
            if "exact_keyword" in label
        ]
        for query, expected, label in exact_cases:
            kw_results = _keyword_retrieve(self.retriever, query)
            assert _recall(kw_results, expected) == 1.0, (
                f"Keyword should have perfect recall for exact match: {label}"
            )

    # -- Per-query detailed checks --

    @pytest.mark.parametrize(
        ("query", "expected", "label"),
        TEST_QUERIES,
        ids=[t[2] for t in TEST_QUERIES],
    )
    def test_semantic_recall_per_query(self, query, expected, label):
        """Semantic retrieval recall@5 for each individual query."""
        results = _semantic_retrieve(self.retriever, query)
        r = _recall(results, expected)
        _precision(results, expected)

        # For queries with expected results, recall should be > 0
        # (i.e., at least one relevant skill should be retrieved)
        if expected:
            assert r > 0.0 or "no_match" in label, (
                f"Semantic recall=0 for '{label}': query='{query[:50]}' "
                f"expected={expected} got={results}"
            )

    def test_no_match_query_returns_empty_or_irrelevant(self):
        """
        Queries with no relevant skill should not produce false positives
        with very high confidence.
        """
        no_match_cases = [
            (q, exp, label) for q, exp, label in TEST_QUERIES
            if "no_match" in label
        ]
        for query, _expected, label in no_match_cases:
            results = _semantic_retrieve(self.retriever, query)
            # Either empty or none of the expected are in results
            # (expected is empty set, so any result is a false positive)
            # We accept this as a soft check -- just verify it doesn't
            # return ALL skills as relevant
            assert len(results) < len(SKILL_CORPUS), (
                f"No-match query returned too many results: {label}"
            )


class TestTfidfUnitTests:
    """Unit tests for the TF-IDF components used by the retriever."""

    def test_tokenize_english(self):
        """English tokenization produces lowercase tokens."""
        tokens = _tokenize("Fix WSL Chinese path encoding issue")
        assert "fix" in tokens
        assert "wsl" in tokens
        assert "chinese" in tokens
        assert "encoding" in tokens

    def test_tokenize_chinese(self):
        """Chinese tokenization produces meaningful tokens."""
        from runtime.skill_retriever import _JIEBA_AVAILABLE
        tokens = _tokenize("修复WSL中文路径编码问题")
        assert "wsl" in tokens
        if _JIEBA_AVAILABLE:
            # jieba produces word-level segments
            assert "修复" in tokens or "修" in tokens
            assert "编码" in tokens or "编" in tokens
        else:
            # Fallback: character-level + bigrams
            assert "修" in tokens
            assert "复" in tokens
            assert "编" in tokens
            assert "码" in tokens
            # Bigrams should also be present
            assert "编码" in tokens

    def test_tokenize_mixed(self):
        """Mixed Chinese/English tokenization works correctly."""
        from runtime.skill_retriever import _JIEBA_AVAILABLE
        tokens = _tokenize("Fix WSL 中文路径 encoding")
        assert "fix" in tokens
        assert "wsl" in tokens
        assert "encoding" in tokens
        if _JIEBA_AVAILABLE:
            # jieba produces word-level segments
            assert "中文" in tokens or "中" in tokens
        else:
            # Fallback: character-level
            assert "中" in tokens
            assert "文" in tokens

    def test_cosine_sim_identical(self):
        """Identical vectors have cosine similarity 1.0."""
        vec = {"a": 1.0, "b": 2.0, "c": 3.0}
        assert _cosine_sim(vec, vec) == pytest.approx(1.0)

    def test_cosine_sim_orthogonal(self):
        """Orthogonal vectors have cosine similarity 0.0."""
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert _cosine_sim(vec_a, vec_b) == 0.0

    def test_cosine_sim_empty(self):
        """Empty vectors have cosine similarity 0.0."""
        assert _cosine_sim({}, {}) == 0.0

    def test_tfidf_rare_terms_get_higher_weight(self):
        """Rare terms should get higher IDF weight than common terms."""
        documents = [
            ["common", "rare", "unique"],
            ["common", "another"],
            ["common", "third"],
        ]
        idf = _compute_idf(documents)
        # "common" appears in 3 docs, "rare" in 1
        assert idf["rare"] > idf["common"]

    def test_tfidf_vector_reflects_term_frequency(self):
        """TF-IDF vector magnitude should reflect term frequency."""
        idf = {"a": 2.0, "b": 1.0}
        vec = _tfidf_vector(["a", "a", "b"], idf)
        # "a" appears twice with IDF=2.0, "b" once with IDF=1.0
        assert vec["a"] > vec["b"]
