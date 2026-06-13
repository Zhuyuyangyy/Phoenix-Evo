# -*- coding: utf-8 -*-
"""
EmbeddingRetriever: Production-grade semantic retrieval engine
V1.3 -- Phoenix-Evo Runtime Embedding Retriever

Responsibilities:
  - Use sentence-transformers to encode queries and corpus into dense vectors
  - Compute cosine similarity in embedding space for true semantic matching
  - Provide a 3-tier fallback chain: Embedding -> TF-IDF -> Keyword
  - Cache corpus embeddings for efficient repeated queries
  - Support batch encoding with configurable batch_size
  - Provide unified retrieve() API compatible with skill_retriever.py

Key improvements over semantic_retriever.py (V1.2):
  1. Lazy model loading with thread-safe singleton
  2. Corpus embedding cache with hash-based invalidation
  3. Configurable batch_size for memory-constrained environments
  4. Explicit retrieval_method field in results (embedding / tfidf / keyword)
  5. RetrievalBenchmark support via method_forced parameter

Usage:
    from runtime.embedding_retriever import EmbeddingRetriever
    retriever = EmbeddingRetriever()
    results = retriever.retrieve("fix encoding issue", corpus_texts, top_k=5)

    # Force a specific method for benchmarking
    results = retriever.retrieve("fix encoding", corpus, method="tfidf")
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from collections import Counter
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Try to load sentence-transformers
# ---------------------------------------------------------------------------

_EMBEDDING_AVAILABLE = False
_MODEL_NAME = "all-MiniLM-L6-v2"
_embedding_model = None
_model_lock = threading.Lock()

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    def _get_model(model_name: str = _MODEL_NAME) -> SentenceTransformer:
        """Thread-safe lazy loading of the sentence-transformers model."""
        global _embedding_model
        if _embedding_model is None:
            with _model_lock:
                if _embedding_model is None:
                    _embedding_model = SentenceTransformer(model_name)
        return _embedding_model

    _EMBEDDING_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Text tokenization (shared with skill_retriever.py)
# ---------------------------------------------------------------------------

_CHINESE_CHAR_RE = re.compile(r'[一-鿿]')
_ENGLISH_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')
_MIN_TOKEN_LEN = 2

_JIEBA_AVAILABLE = False
try:
    import jieba as _jieba
    _jieba.setLogLevel(20)
    _JIEBA_AVAILABLE = True
except ImportError:
    pass


def _tokenize_chinese(text: str) -> list[str]:
    """Segment Chinese text into word-level tokens."""
    if _JIEBA_AVAILABLE:
        return [w for w in _jieba.lcut(text) if w.strip()]
    chars = _CHINESE_CHAR_RE.findall(text)
    if not chars:
        return []
    tokens = list(chars)
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    return tokens


def _tokenize(text: str) -> list[str]:
    """Split text into word tokens for TF-IDF."""
    tokens: list[str] = []
    tokens.extend(_tokenize_chinese(text))
    for t in _ENGLISH_TOKEN_RE.findall(text):
        tl = t.lower()
        if len(tl) >= _MIN_TOKEN_LEN:
            tokens.append(tl)
    return tokens


def _tokenize_to_set(text: str) -> set[str]:
    """Return deduplicated token set."""
    return set(_tokenize(text))


# ---------------------------------------------------------------------------
# TF-IDF implementation
# ---------------------------------------------------------------------------

def _compute_idf(documents: list[list[str]]) -> dict[str, float]:
    """Compute smoothed IDF for each term across a corpus."""
    N = len(documents)
    doc_freq: Counter = Counter()
    for doc in documents:
        for term in set(doc):
            doc_freq[term] += 1
    return {
        term: math.log((N + 1) / (df + 1)) + 1
        for term, df in doc_freq.items()
    }


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Convert a token list to a sparse TF-IDF vector (dict)."""
    if not tokens:
        return {}
    tf: Counter = Counter(tokens)
    total = max(sum(tf.values()), 1)
    return {
        term: (count / total) * idf[term]
        for term, count in tf.items()
        if term in idf
    }


def _cosine_sim_sparse(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# EmbeddingRetriever
# ---------------------------------------------------------------------------

RetrievalMethod = Literal["embedding", "tfidf", "keyword"]


class EmbeddingRetriever:
    """
    Production-grade semantic retrieval engine with 3-tier fallback.

    Retrieval chain:
      1. Embedding: sentence-transformers all-MiniLM-L6-v2 + cosine similarity
      2. TF-IDF:    bag-of-words TF-IDF + cosine similarity
      3. Keyword:   Jaccard word overlap (last resort)

    The retriever caches corpus embeddings for efficiency in repeated queries.
    Corpus cache is invalidated when the corpus content changes (hash-based).

    Usage:
        retriever = EmbeddingRetriever()
        corpus = ["fix WSL encoding", "resolve merge conflicts", "deploy with Docker"]
        results = retriever.retrieve("Unicode filename garbled", corpus, top_k=2)
    """

    def __init__(
        self,
        model_name: str = _MODEL_NAME,
        batch_size: int = 64,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self._corpus_cache: dict[str, Any] = {}   # text -> embedding
        self._corpus_hash: str = ""                 # hash of last encoded corpus

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def is_semantic(self) -> bool:
        """Whether true semantic embeddings are available."""
        return _EMBEDDING_AVAILABLE

    @property
    def available_methods(self) -> list[str]:
        """List of available retrieval methods in priority order."""
        methods: list[str] = []
        if _EMBEDDING_AVAILABLE:
            methods.append("embedding")
        methods.append("tfidf")
        methods.append("keyword")
        return methods

    def retrieve(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int = 5,
        score_threshold: float = 0.0,
        method: RetrievalMethod | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the top-k most similar texts from the corpus.

        Args:
            query: The query text.
            corpus_texts: List of corpus text strings.
            top_k: Number of results to return.
            score_threshold: Minimum similarity score to include.
            method: Force a specific retrieval method (for benchmarking).
                    If None, uses the automatic fallback chain.

        Returns:
            List of dicts with keys: index, text, score, method.
            Sorted by score descending.
        """
        if not corpus_texts:
            return []

        # Force a specific method if requested
        if method == "embedding":
            if not _EMBEDDING_AVAILABLE:
                raise RuntimeError(
                    "sentence-transformers not installed; cannot use embedding method"
                )
            return self._retrieve_embedding(query, corpus_texts, top_k, score_threshold)
        elif method == "tfidf":
            return self._retrieve_tfidf(query, corpus_texts, top_k, score_threshold)
        elif method == "keyword":
            return self._retrieve_keyword(query, corpus_texts, top_k)

        # Automatic fallback chain
        if _EMBEDDING_AVAILABLE:
            return self._retrieve_embedding(query, corpus_texts, top_k, score_threshold)
        else:
            return self._retrieve_tfidf(query, corpus_texts, top_k, score_threshold)

    def encode_corpus(self, texts: list[str]) -> Any:
        """
        Encode a corpus of texts into dense embeddings. Results are cached.

        Args:
            texts: List of text strings.

        Returns:
            numpy array of shape (len(texts), embedding_dim), or None.
        """
        if not _EMBEDDING_AVAILABLE:
            return None

        corpus_hash = self._hash_corpus(texts)
        if corpus_hash == self._corpus_hash and self._corpus_cache:
            # Return cached embeddings in order
            return np.array([self._corpus_cache[t] for t in texts])

        model = _get_model(self.model_name)
        embeddings = model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
            batch_size=self.batch_size,
        )

        # Update cache
        self._corpus_cache = {}
        for text, emb in zip(texts, embeddings):
            self._corpus_cache[text] = emb
        self._corpus_hash = corpus_hash

        return embeddings

    def retrieve_with_metadata(
        self,
        query: str,
        entries: list[dict[str, Any]],
        text_builder: callable,
        top_k: int = 5,
        score_threshold: float = 0.0,
        method: RetrievalMethod | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve entries with metadata, using a text_builder to convert
        each entry into a searchable text representation.

        Args:
            query: The query text.
            entries: List of entry dicts.
            text_builder: Function(entry) -> str that builds searchable text.
            top_k: Number of results to return.
            score_threshold: Minimum similarity score.
            method: Force a specific retrieval method.

        Returns:
            List of dicts with keys: entry, score, method, index.
        """
        corpus_texts = [text_builder(e) for e in entries]
        results = self.retrieve(
            query, corpus_texts, top_k=top_k,
            score_threshold=score_threshold, method=method,
        )
        for r in results:
            r["entry"] = entries[r["index"]]
        return results

    # ------------------------------------------------------------------ #
    # Internal: Embedding retrieval                                       #
    # ------------------------------------------------------------------ #

    def _retrieve_embedding(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        """Retrieve using sentence-transformers embeddings."""
        model = _get_model(self.model_name)

        # Encode query
        query_vec = model.encode(
            [query], show_progress_bar=False, normalize_embeddings=True,
        )[0]

        # Encode corpus (uses cache if available)
        corpus_vecs = self.encode_corpus(corpus_texts)

        # Compute similarities via dot product (embeddings are already normalized)
        scores = np.dot(corpus_vecs, query_vec).tolist()

        # Rank and filter
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:top_k]:
            if score >= score_threshold:
                results.append({
                    "index": idx,
                    "text": corpus_texts[idx],
                    "score": round(float(score), 4),
                    "method": "embedding",
                })
        return results

    # ------------------------------------------------------------------ #
    # Internal: TF-IDF retrieval                                          #
    # ------------------------------------------------------------------ #

    def _retrieve_tfidf(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        """Retrieve using TF-IDF + cosine similarity."""
        query_tokens = _tokenize(query)
        corpus_tokens = [_tokenize(t) for t in corpus_texts]

        all_tokens = [query_tokens] + corpus_tokens
        idf = _compute_idf(all_tokens)
        query_vec = _tfidf_vector(query_tokens, idf)

        scores = []
        for i, tokens in enumerate(corpus_tokens):
            skill_vec = _tfidf_vector(tokens, idf)
            sim = _cosine_sim_sparse(query_vec, skill_vec)
            scores.append((i, sim))

        ranked = sorted(scores, key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:top_k]:
            if score >= score_threshold:
                results.append({
                    "index": idx,
                    "text": corpus_texts[idx],
                    "score": round(score, 4),
                    "method": "tfidf",
                })
        return results

    # ------------------------------------------------------------------ #
    # Internal: Keyword retrieval (last resort)                           #
    # ------------------------------------------------------------------ #

    def _retrieve_keyword(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Retrieve using Jaccard word overlap (last resort fallback)."""
        query_words = set(re.findall(r'[\w一-鿿]{2,}', query.lower()))
        results = []
        for i, text in enumerate(corpus_texts):
            text_words = set(re.findall(r'[\w一-鿿]{2,}', text.lower()))
            if not text_words:
                continue
            overlap = len(query_words & text_words) / max(len(query_words | text_words), 1)
            if overlap > 0:
                results.append({
                    "index": i,
                    "text": text,
                    "score": round(overlap, 4),
                    "method": "keyword",
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------ #
    # Utilities                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash_corpus(texts: list[str]) -> str:
        """Compute a hash of the corpus for cache invalidation."""
        h = hashlib.md5()
        for t in texts:
            h.update(t.encode("utf-8", errors="replace"))
        return h.hexdigest()

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._corpus_cache.clear()
        self._corpus_hash = ""


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def embedding_search(
    query: str,
    corpus: list[str],
    top_k: int = 5,
    method: RetrievalMethod | None = None,
) -> list[dict[str, Any]]:
    """
    One-shot semantic search using EmbeddingRetriever.

    Args:
        query: Search query.
        corpus: List of texts to search.
        top_k: Number of results.
        method: Force a specific retrieval method.

    Returns:
        List of {index, text, score, method} dicts.
    """
    retriever = EmbeddingRetriever()
    return retriever.retrieve(query, corpus, top_k=top_k, method=method)
