"""
Retrieval Benchmark: Keyword vs. TF-IDF vs. Embedding
======================================================

Compares the recall@k and precision@k of three retrieval methods:
  1. Keyword  -- Jaccard word overlap (legacy baseline)
  2. TF-IDF   -- TF-IDF + cosine similarity (V1.1 upgrade)
  3. Embedding -- sentence-transformers all-MiniLM-L6-v2 (V1.3 upgrade)

This benchmark directly addresses the "zero experiments" critique
from the research verdict (Section 3.1, F1/F2) and provides
reproducible comparative data on a controlled skill corpus.

Run:
    cd Phoenix-Evo
    pytest tests/test_retrieval_benchmark.py -v -s

The -s flag is important to see the benchmark output table.
"""


import pytest

from runtime.embedding_retriever import (
    _EMBEDDING_AVAILABLE,
    EmbeddingRetriever,
    _compute_idf,
    _cosine_sim_sparse,
    _tokenize,
)

# ---------------------------------------------------------------------------
# Test corpus: 10 skills covering distinct domains
# ---------------------------------------------------------------------------

SKILL_CORPUS = [
    {
        "skill_id": "skill_wsl_encoding",
        "skill_name": "fix_wsl_chinese_path_encoding",
        "task_type": "debugging",
        "risk_level": "low",
        "quality_score": 0.90,
        "text": "Fix encoding issues with Chinese characters in WSL paths. When dealing with WSL file system paths that contain Chinese characters and cause encoding errors or garbled output. Convert to UTF-8 and normalize Unicode.",
        "when_to_use": "When dealing with WSL file system paths that contain Chinese characters and cause encoding errors or garbled output.",
    },
    {
        "skill_id": "skill_git_merge",
        "skill_name": "resolve_git_merge_conflict",
        "task_type": "debugging",
        "risk_level": "low",
        "quality_score": 0.85,
        "text": "Resolve merge conflicts in git repositories. When a git merge or rebase produces merge conflicts that need to be resolved manually. Identify conflicting files and choose correct version.",
        "when_to_use": "When a git merge or rebase produces merge conflicts that need to be resolved manually.",
    },
    {
        "skill_id": "skill_api_auth",
        "skill_name": "implement_jwt_authentication",
        "task_type": "coding",
        "risk_level": "medium",
        "quality_score": 0.88,
        "text": "Implement JWT-based authentication for REST APIs. When building API endpoints that require JSON Web Token based authentication and authorization. Generate secret key and create token signing.",
        "when_to_use": "When building API endpoints that require JSON Web Token based authentication and authorization.",
    },
    {
        "skill_id": "skill_docker_deploy",
        "skill_name": "deploy_application_with_docker",
        "task_type": "deployment",
        "risk_level": "medium",
        "quality_score": 0.82,
        "text": "Deploy applications using Docker and Docker Compose. When deploying a Python or Node.js application using Docker containers. Write Dockerfile with multi-stage build.",
        "when_to_use": "When deploying a Python or Node.js application using Docker containers and Docker Compose.",
    },
    {
        "skill_id": "skill_sql_optimize",
        "skill_name": "optimize_slow_sql_queries",
        "task_type": "optimization",
        "risk_level": "low",
        "quality_score": 0.87,
        "text": "Optimize slow SQL queries through indexing and rewriting. When database queries are running slowly and need performance optimization. Run EXPLAIN ANALYZE and add appropriate indexes.",
        "when_to_use": "When database queries are running slowly and need performance optimization through index tuning and query rewriting.",
    },
    {
        "skill_id": "skill_react_component",
        "skill_name": "create_react_component_with_tests",
        "task_type": "coding",
        "risk_level": "low",
        "quality_score": 0.80,
        "text": "Create React components with TypeScript and unit tests. When building a new React component that needs unit tests and proper type definitions. Define TypeScript interface for props.",
        "when_to_use": "When building a new React component that needs unit tests and proper TypeScript type definitions.",
    },
    {
        "skill_id": "skill_network_debug",
        "skill_name": "diagnose_network_connectivity_issues",
        "task_type": "debugging",
        "risk_level": "low",
        "quality_score": 0.83,
        "text": "Diagnose and fix network connectivity issues. When experiencing network connectivity problems such as DNS resolution failures or timeout errors. Check DNS with nslookup and test with ping.",
        "when_to_use": "When experiencing network connectivity problems such as DNS resolution failures, timeout errors, or connection refused.",
    },
    {
        "skill_id": "skill_python_caching",
        "skill_name": "implement_redis_caching_layer",
        "task_type": "coding",
        "risk_level": "low",
        "quality_score": 0.84,
        "text": "Implement Redis-based caching for Python applications. When adding a caching layer to reduce database load and improve response times. Set up Redis connection and cache decorator.",
        "when_to_use": "When adding a caching layer to a Python web application to reduce database load and improve response times.",
    },
    {
        "skill_id": "skill_error_logging",
        "skill_name": "setup_structured_error_logging",
        "task_type": "coding",
        "risk_level": "low",
        "quality_score": 0.81,
        "text": "Set up structured error logging with log levels and formatters. When implementing logging for a Python application that needs structured output for monitoring and debugging.",
        "when_to_use": "When implementing logging for a Python application that needs structured output for monitoring and debugging.",
    },
    {
        "skill_id": "skill_ci_pipeline",
        "skill_name": "configure_github_actions_ci",
        "task_type": "deployment",
        "risk_level": "medium",
        "quality_score": 0.79,
        "text": "Configure GitHub Actions CI/CD pipeline with automated testing and deployment. When setting up continuous integration for a repository with automated test runs and deployment stages.",
        "when_to_use": "When setting up continuous integration for a repository with automated test runs and deployment stages.",
    },
]


# ---------------------------------------------------------------------------
# Test queries with expected relevant skill IDs
# ---------------------------------------------------------------------------

BENCHMARK_QUERIES = [
    # --- Exact keyword overlap (all methods should succeed) ---
    ("encoding", {"skill_wsl_encoding"}, "exact_keyword"),
    ("merge conflict", {"skill_git_merge"}, "exact_keyword"),
    ("JWT", {"skill_api_auth"}, "exact_keyword"),
    ("Docker", {"skill_docker_deploy"}, "exact_keyword"),
    ("SQL query", {"skill_sql_optimize"}, "exact_keyword"),
    ("React component", {"skill_react_component"}, "exact_keyword"),
    ("Redis cache", {"skill_python_caching"}, "exact_keyword"),

    # --- Paraphrase / semantic overlap (keyword may fail) ---
    ("Unicode filename garbled on Windows Subsystem for Linux", {"skill_wsl_encoding"}, "paraphrase"),
    ("How to handle conflicting changes from two branches", {"skill_git_merge"}, "paraphrase"),
    ("Add token-based login security to my REST service", {"skill_api_auth"}, "paraphrase"),
    ("Make my database queries faster, they are timing out", {"skill_sql_optimize"}, "paraphrase"),
    ("Containerize my Python web app for production deployment", {"skill_docker_deploy"}, "paraphrase"),
    ("My React button component needs proper types and tests", {"skill_react_component"}, "paraphrase"),
    ("Cannot reach the API server, connection times out", {"skill_network_debug"}, "paraphrase"),
    ("Speed up API responses by caching frequent queries", {"skill_python_caching"}, "paraphrase"),
    ("Add monitoring logs with structured format for debugging", {"skill_error_logging"}, "paraphrase"),
    ("Set up automated test pipeline on every commit push", {"skill_ci_pipeline"}, "paraphrase"),

    # --- Cross-domain noise queries ---
    ("Deploy machine learning model to Kubernetes cluster", {"skill_docker_deploy"}, "cross_domain"),
    ("Fix memory leak in Python asyncio application", set(), "no_match"),

    # --- Chinese query ---
    ("修复WSL中文路径编码乱码问题", {"skill_wsl_encoding"}, "chinese"),
    ("数据库查询很慢需要优化", {"skill_sql_optimize"}, "chinese"),
]


# ---------------------------------------------------------------------------
# Retrieval method wrappers
# ---------------------------------------------------------------------------

def _keyword_retrieve(retriever: EmbeddingRetriever, query: str, top_k: int = 5) -> set[str]:
    """Retrieve using keyword overlap."""
    results = retriever.retrieve(query, [s["text"] for s in SKILL_CORPUS], top_k=top_k, method="keyword")
    return {SKILL_CORPUS[r["index"]]["skill_id"] for r in results}


def _tfidf_retrieve(retriever: EmbeddingRetriever, query: str, top_k: int = 5) -> set[str]:
    """Retrieve using TF-IDF + cosine similarity."""
    results = retriever.retrieve(query, [s["text"] for s in SKILL_CORPUS], top_k=top_k, method="tfidf")
    return {SKILL_CORPUS[r["index"]]["skill_id"] for r in results}


def _embedding_retrieve(retriever: EmbeddingRetriever, query: str, top_k: int = 5) -> set[str]:
    """Retrieve using sentence-transformers embeddings."""
    results = retriever.retrieve(query, [s["text"] for s in SKILL_CORPUS], top_k=top_k, method="embedding")
    return {SKILL_CORPUS[r["index"]]["skill_id"] for r in results}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall(retrieved: set[str], relevant: set[str]) -> float:
    """Compute recall = |retrieved & relevant| / |relevant|."""
    if not relevant:
        return 1.0  # vacuously true
    return len(retrieved & relevant) / len(relevant)


def precision(retrieved: set[str], relevant: set[str]) -> float:
    """Compute precision = |retrieved & relevant| / |retrieved|."""
    if not retrieved:
        return 0.0 if relevant else 1.0
    return len(retrieved & relevant) / len(retrieved)


# ---------------------------------------------------------------------------
# Benchmark Tests
# ---------------------------------------------------------------------------

class TestRetrievalBenchmark:
    """
    Benchmark comparing keyword, TF-IDF, and embedding retrieval
    across exact-match, paraphrase, cross-domain, and Chinese queries.
    """

    @pytest.fixture(autouse=True)
    def setup_retriever(self):
        """Initialize the retriever."""
        self.retriever = EmbeddingRetriever()
        self.corpus = [s["text"] for s in SKILL_CORPUS]

    # ------------------------------------------------------------------ #
    # Aggregate benchmark                                                 #
    # ------------------------------------------------------------------ #

    def test_full_benchmark(self):
        """
        Run the full benchmark: compute recall@5 and precision@5 for all
        three methods across all query categories.
        """
        categories = ["exact_keyword", "paraphrase", "cross_domain", "no_match", "chinese"]
        methods = ["keyword", "tfidf"]
        if _EMBEDDING_AVAILABLE:
            methods.append("embedding")

        results_by_method: dict[str, dict[str, list[float]]] = {
            m: {cat: [] for cat in categories} for m in methods
        }
        precision_by_method: dict[str, dict[str, list[float]]] = {
            m: {cat: [] for cat in categories} for m in methods
        }

        for query, expected, category in BENCHMARK_QUERIES:
            kw = _keyword_retrieve(self.retriever, query)
            tf = _tfidf_retrieve(self.retriever, query)

            results_by_method["keyword"][category].append(recall(kw, expected))
            results_by_method["tfidf"][category].append(recall(tf, expected))
            precision_by_method["keyword"][category].append(precision(kw, expected))
            precision_by_method["tfidf"][category].append(precision(tf, expected))

            if _EMBEDDING_AVAILABLE:
                emb = _embedding_retrieve(self.retriever, query)
                results_by_method["embedding"][category].append(recall(emb, expected))
                precision_by_method["embedding"][category].append(precision(emb, expected))

        # Print benchmark table
        print("\n" + "=" * 80)
        print("RETRIEVAL BENCHMARK: Recall@5")
        print("=" * 80)
        header = f"{'Category':<20} {'Keyword':>10} {'TF-IDF':>10}"
        if _EMBEDDING_AVAILABLE:
            header += f" {'Embedding':>10}"
        print(header)
        print("-" * 80)

        overall_kw, overall_tf, overall_emb = [], [], []
        for cat in categories:
            kw_vals = results_by_method["keyword"][cat]
            tf_vals = results_by_method["tfidf"][cat]
            kw_avg = sum(kw_vals) / len(kw_vals) if kw_vals else 0
            tf_avg = sum(tf_vals) / len(tf_vals) if tf_vals else 0
            overall_kw.extend(kw_vals)
            overall_tf.extend(tf_vals)

            row = f"{cat:<20} {kw_avg:>10.3f} {tf_avg:>10.3f}"
            if _EMBEDDING_AVAILABLE:
                emb_vals = results_by_method["embedding"][cat]
                emb_avg = sum(emb_vals) / len(emb_vals) if emb_vals else 0
                overall_emb.extend(emb_vals)
                row += f" {emb_avg:>10.3f}"
            print(row)

        print("-" * 80)
        kw_macro = sum(overall_kw) / len(overall_kw) if overall_kw else 0
        tf_macro = sum(overall_tf) / len(overall_tf) if overall_tf else 0
        row = f"{'OVERALL':<20} {kw_macro:>10.3f} {tf_macro:>10.3f}"
        if _EMBEDDING_AVAILABLE:
            emb_macro = sum(overall_emb) / len(overall_emb) if overall_emb else 0
            row += f" {emb_macro:>10.3f}"
        print(row)
        print("=" * 80)

        # Print precision table
        print("\n" + "=" * 80)
        print("RETRIEVAL BENCHMARK: Precision@5")
        print("=" * 80)
        print(header)
        print("-" * 80)

        overall_kw_p, overall_tf_p, overall_emb_p = [], [], []
        for cat in categories:
            kw_vals = precision_by_method["keyword"][cat]
            tf_vals = precision_by_method["tfidf"][cat]
            kw_avg = sum(kw_vals) / len(kw_vals) if kw_vals else 0
            tf_avg = sum(tf_vals) / len(tf_vals) if tf_vals else 0
            overall_kw_p.extend(kw_vals)
            overall_tf_p.extend(tf_vals)

            row = f"{cat:<20} {kw_avg:>10.3f} {tf_avg:>10.3f}"
            if _EMBEDDING_AVAILABLE:
                emb_vals = precision_by_method["embedding"][cat]
                emb_avg = sum(emb_vals) / len(emb_vals) if emb_vals else 0
                overall_emb_p.extend(emb_vals)
                row += f" {emb_avg:>10.3f}"
            print(row)

        print("-" * 80)
        kw_macro_p = sum(overall_kw_p) / len(overall_kw_p) if overall_kw_p else 0
        tf_macro_p = sum(overall_tf_p) / len(overall_tf_p) if overall_tf_p else 0
        row = f"{'OVERALL':<20} {kw_macro_p:>10.3f} {tf_macro_p:>10.3f}"
        if _EMBEDDING_AVAILABLE:
            emb_macro_p = sum(overall_emb_p) / len(overall_emb_p) if overall_emb_p else 0
            row += f" {emb_macro_p:>10.3f}"
        print(row)
        print("=" * 80)

    # ------------------------------------------------------------------ #
    # Key assertions                                                      #
    # ------------------------------------------------------------------ #

    def test_embedding_recall_dominates_tfidf(self):
        """
        Embedding retrieval should have recall >= TF-IDF across all queries.
        This is the core claim of the V1.3 upgrade.
        """
        if not _EMBEDDING_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        tf_recalls = []
        emb_recalls = []

        for query, expected, _cat in BENCHMARK_QUERIES:
            tf = _tfidf_retrieve(self.retriever, query)
            emb = _embedding_retrieve(self.retriever, query)
            tf_recalls.append(recall(tf, expected))
            emb_recalls.append(recall(emb, expected))

        avg_tf = sum(tf_recalls) / len(tf_recalls)
        avg_emb = sum(emb_recalls) / len(emb_recalls)

        assert avg_emb >= avg_tf, (
            f"Embedding recall ({avg_emb:.3f}) should be >= TF-IDF recall ({avg_tf:.3f})"
        )

    def test_tfidf_recall_dominates_keyword(self):
        """
        TF-IDF retrieval should have recall >= keyword across all queries.
        """
        kw_recalls = []
        tf_recalls = []

        for query, expected, _cat in BENCHMARK_QUERIES:
            kw = _keyword_retrieve(self.retriever, query)
            tf = _tfidf_retrieve(self.retriever, query)
            kw_recalls.append(recall(kw, expected))
            tf_recalls.append(recall(tf, expected))

        avg_kw = sum(kw_recalls) / len(kw_recalls)
        avg_tf = sum(tf_recalls) / len(tf_recalls)

        assert avg_tf >= avg_kw, (
            f"TF-IDF recall ({avg_tf:.3f}) should be >= keyword recall ({avg_kw:.3f})"
        )

    def test_embedding_paraphrase_recall_better_than_keyword(self):
        """
        On paraphrase queries specifically, embedding should be
        significantly better than keyword retrieval.
        """
        if not _EMBEDDING_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        paraphrase_cases = [
            (q, exp) for q, exp, cat in BENCHMARK_QUERIES if cat == "paraphrase"
        ]

        kw_recalls = []
        emb_recalls = []

        for query, expected in paraphrase_cases:
            kw = _keyword_retrieve(self.retriever, query)
            emb = _embedding_retrieve(self.retriever, query)
            kw_recalls.append(recall(kw, expected))
            emb_recalls.append(recall(emb, expected))

        avg_kw = sum(kw_recalls) / len(kw_recalls)
        avg_emb = sum(emb_recalls) / len(emb_recalls)

        print("\n--- Paraphrase Query Recall ---")
        print(f"  Keyword  avg recall: {avg_kw:.3f}")
        print(f"  Embedding avg recall: {avg_emb:.3f}")

        # Embedding should be strictly better on paraphrases
        assert avg_emb > avg_kw, (
            f"Embedding paraphrase recall ({avg_emb:.3f}) should exceed "
            f"keyword paraphrase recall ({avg_kw:.3f})"
        )

    def test_embedding_chinese_queries(self):
        """
        Embedding retrieval should handle Chinese queries and find
        the correct skills.
        """
        if not _EMBEDDING_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        chinese_cases = [
            (q, exp) for q, exp, cat in BENCHMARK_QUERIES if cat == "chinese"
        ]

        for query, expected in chinese_cases:
            emb = _embedding_retrieve(self.retriever, query)
            r = recall(emb, expected)
            assert r > 0.0, (
                f"Embedding should find relevant skill for Chinese query: '{query}'"
            )

    def test_keyword_exact_match_perfect_recall(self):
        """
        Keyword retrieval should have perfect recall on exact-match queries.
        """
        exact_cases = [
            (q, exp) for q, exp, cat in BENCHMARK_QUERIES if cat == "exact_keyword"
        ]

        for query, expected in exact_cases:
            kw = _keyword_retrieve(self.retriever, query)
            r = recall(kw, expected)
            assert r == 1.0, (
                f"Keyword should have perfect recall for exact match: '{query}'"
            )

    def test_all_methods_handle_empty_corpus(self):
        """All methods should return empty results for an empty corpus."""
        results_kw = self.retriever.retrieve("test", [], method="keyword")
        results_tf = self.retriever.retrieve("test", [], method="tfidf")
        assert results_kw == []
        assert results_tf == []

    def test_all_methods_return_sorted_results(self):
        """All methods should return results sorted by score descending."""
        query = "fix encoding issue"
        for method in self.retriever.available_methods:
            results = self.retriever.retrieve(query, self.corpus, method=method)
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True), (
                f"{method} results not sorted by score descending"
            )

    def test_all_methods_score_range(self):
        """All methods should return scores in [0, 1]."""
        query = "fix encoding issue"
        for method in self.retriever.available_methods:
            results = self.retriever.retrieve(query, self.corpus, method=method)
            for r in results:
                assert 0.0 <= r["score"] <= 1.0, (
                    f"{method} score {r['score']} out of range for result {r['index']}"
                )

    def test_all_methods_report_method_field(self):
        """All methods should set the 'method' field in results."""
        query = "fix encoding issue"
        for method in self.retriever.available_methods:
            results = self.retriever.retrieve(query, self.corpus, method=method)
            for r in results:
                assert "method" in r
                assert r["method"] == method

    # ------------------------------------------------------------------ #
    # Per-query detailed benchmark                                        #
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        ("query", "expected", "category"),
        BENCHMARK_QUERIES,
        ids=[f"{t[2]}_{t[0][:40]}" for t in BENCHMARK_QUERIES],
    )
    def test_embedding_recall_per_query(self, query, expected, category):
        """Embedding retrieval recall@5 for each individual query."""
        if not _EMBEDDING_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        results = _embedding_retrieve(self.retriever, query)
        r = recall(results, expected)

        if expected and category != "no_match":
            assert r > 0.0, (
                f"Embedding recall=0 for '{category}': query='{query[:50]}' "
                f"expected={expected} got={results}"
            )

    @pytest.mark.parametrize(
        ("query", "expected", "category"),
        BENCHMARK_QUERIES,
        ids=[f"{t[2]}_{t[0][:40]}" for t in BENCHMARK_QUERIES],
    )
    def test_tfidf_recall_per_query(self, query, expected, category):
        """TF-IDF retrieval recall@5 for each individual query."""
        results = _tfidf_retrieve(self.retriever, query)
        r = recall(results, expected)

        if expected and category != "no_match":
            assert r > 0.0 or category == "paraphrase", (
                f"TF-IDF recall=0 for '{category}': query='{query[:50]}' "
                f"expected={expected} got={results}"
            )


# ---------------------------------------------------------------------------
# EmbeddingRetriever unit tests
# ---------------------------------------------------------------------------

class TestEmbeddingRetrieverUnit:
    """Unit tests for the EmbeddingRetriever class."""

    def test_initialization(self):
        """EmbeddingRetriever can be initialized."""
        retriever = EmbeddingRetriever()
        assert retriever is not None
        assert retriever.is_semantic == _EMBEDDING_AVAILABLE

    def test_available_methods(self):
        """available_methods returns correct list."""
        retriever = EmbeddingRetriever()
        methods = retriever.available_methods
        assert "tfidf" in methods
        assert "keyword" in methods
        if _EMBEDDING_AVAILABLE:
            assert "embedding" in methods
            assert methods[0] == "embedding"

    def test_force_method(self):
        """Forcing a specific method works."""
        retriever = EmbeddingRetriever()
        corpus = ["fix encoding issue", "resolve merge conflicts"]
        results = retriever.retrieve("encoding", corpus, method="keyword")
        assert all(r["method"] == "keyword" for r in results)

    def test_retrieve_with_metadata(self):
        """retrieve_with_metadata attaches entry dicts to results."""
        retriever = EmbeddingRetriever()
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

    def test_encode_corpus_returns_embeddings(self):
        """encode_corpus returns embeddings when available."""
        retriever = EmbeddingRetriever()
        corpus = [s["text"] for s in SKILL_CORPUS[:3]]
        embeddings = retriever.encode_corpus(corpus)
        if _EMBEDDING_AVAILABLE:
            assert embeddings is not None
            assert len(embeddings) == 3
        else:
            assert embeddings is None

    def test_cache_invalidation(self):
        """Cache is invalidated when corpus changes."""
        retriever = EmbeddingRetriever()
        if not retriever.is_semantic:
            pytest.skip("Embeddings not available")
        corpus_a = ["text one", "text two"]
        corpus_b = ["text three", "text four"]

        retriever.encode_corpus(corpus_a)
        hash_a = retriever._corpus_hash

        retriever.encode_corpus(corpus_b)
        hash_b = retriever._corpus_hash

        assert hash_a != hash_b

    def test_clear_cache(self):
        """clear_cache empties the cache."""
        retriever = EmbeddingRetriever()
        retriever.encode_corpus(["test"])
        if not retriever.is_semantic:
            pytest.skip("Embeddings not available")
        assert len(retriever._corpus_cache) > 0
        retriever.clear_cache()
        assert len(retriever._corpus_cache) == 0


# ---------------------------------------------------------------------------
# TF-IDF unit tests (duplicated from test_retrieval_comparison.py for
# self-contained benchmark)
# ---------------------------------------------------------------------------

class TestTfidfUnit:
    """Unit tests for TF-IDF components."""

    def test_tokenize_english(self):
        tokens = _tokenize("Fix WSL Chinese path encoding issue")
        assert "fix" in tokens
        assert "wsl" in tokens
        assert "encoding" in tokens

    def test_tokenize_chinese(self):
        tokens = _tokenize("修复WSL中文路径编码问题")
        assert "wsl" in tokens
        assert "编码" in tokens

    def test_cosine_sim_identical(self):
        vec = {"a": 1.0, "b": 2.0, "c": 3.0}
        assert _cosine_sim_sparse(vec, vec) == pytest.approx(1.0)

    def test_cosine_sim_orthogonal(self):
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert _cosine_sim_sparse(vec_a, vec_b) == 0.0

    def test_idf_rare_terms_higher_weight(self):
        documents = [
            ["common", "rare", "unique"],
            ["common", "another"],
            ["common", "third"],
        ]
        idf = _compute_idf(documents)
        assert idf["rare"] > idf["common"]
