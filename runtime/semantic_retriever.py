# -*- coding: utf-8 -*-
"""
semantic_retriever: Sentence-embedding-based semantic retrieval
V1.2 -- Phoenix-Evo Runtime Semantic Retriever

Responsibilities:
  - Use sentence-transformers to encode skill descriptions and queries
  - Compute cosine similarity in embedding space for semantic matching
  - Fall back to TF-IDF when sentence-transformers is unavailable
  - Provide a unified retrieve() API compatible with skill_retriever.py

Upgrade rationale (Q2 SCI Review Finding #1):
  TF-IDF is a bag-of-words model that cannot capture semantic similarity
  between paraphrased concepts. For example, "fix encoding issue" and
  "resolve Unicode garbled text" share no keywords but are semantically
  equivalent. Sentence embeddings (e.g., all-MiniLM-L6-v2) map both to
  nearby points in vector space, enabling true semantic retrieval.

Usage:
    from runtime.semantic_retriever import SemanticRetriever
    retriever = SemanticRetriever()
    results = retriever.retrieve("fix encoding issue", corpus_texts, top_k=5)
"""

from __future__ import annotations

import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Try to load sentence-transformers; fall back to TF-IDF if unavailable
# ---------------------------------------------------------------------------

_EMBEDDING_AVAILABLE = False
_embedding_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    def _load_model() -> SentenceTransformer:
        global _embedding_model
        if _embedding_model is None:
            _embedding_model = SentenceTransformer(_MODEL_NAME)
        return _embedding_model

    _EMBEDDING_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Fallback: TF-IDF (imported from existing implementation)
# ---------------------------------------------------------------------------

try:
    from .skill_retriever import (
        _tokenize, _compute_idf, _tfidf_vector, _cosine_sim,
    )
    _TFIDF_AVAILABLE = True
except ImportError:
    _TFIDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Core semantic retrieval functions
# ---------------------------------------------------------------------------

def encode_texts(texts: list[str]) -> Any:
    """
    Encode a list of texts into dense vector embeddings.

    Args:
        texts: List of text strings to encode.

    Returns:
        numpy array of shape (len(texts), embedding_dim) if sentence-transformers
        is available, otherwise None.

    Raises:
        RuntimeError: If neither sentence-transformers nor TF-IDF is available.
    """
    if _EMBEDDING_AVAILABLE:
        model = _load_model()
        return model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return None


def cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    """
    Compute cosine similarity between two embedding vectors.

    Args:
        vec_a: First embedding vector (numpy array or list).
        vec_b: Second embedding vector (numpy array or list).

    Returns:
        Cosine similarity score in [0.0, 1.0].
    """
    if _EMBEDDING_AVAILABLE:
        import numpy as np
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    return 0.0


def batch_cosine_similarity(query_vec: Any, corpus_vecs: Any) -> list[float]:
    """
    Compute cosine similarity between a query vector and multiple corpus vectors.

    Args:
        query_vec: Query embedding vector (1D numpy array).
        corpus_vecs: Corpus embedding matrix (2D numpy array, shape [n, dim]).

    Returns:
        List of similarity scores, one per corpus vector.
    """
    if _EMBEDDING_AVAILABLE:
        import numpy as np
        q = np.array(query_vec, dtype=np.float32).reshape(1, -1)
        c = np.array(corpus_vecs, dtype=np.float32)
        # Normalize
        q_norm = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-8)
        c_norm = c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-8)
        sims = np.dot(c_norm, q_norm.T).flatten()
        return [float(s) for s in sims]
    return [0.0] * len(corpus_vecs)


# ---------------------------------------------------------------------------
# SemanticRetriever: unified retrieval API
# ---------------------------------------------------------------------------

class SemanticRetriever:
    """
    Semantic retrieval engine using sentence embeddings.

    Retrieval strategy:
      1. Primary: sentence-transformers embedding + cosine similarity
      2. Fallback: TF-IDF + cosine similarity (when embeddings unavailable)

    The retriever caches corpus embeddings for efficiency in repeated queries.

    Usage:
        retriever = SemanticRetriever()
        corpus = ["fix WSL encoding", "resolve merge conflicts", "deploy with Docker"]
        corpus_vecs = retriever.encode_corpus(corpus)
        results = retriever.retrieve("Unicode filename garbled", corpus, corpus_vecs, top_k=2)
    """

    def __init__(self, model_name: str = _MODEL_NAME):
        self.model_name = model_name
        self._corpus_cache: dict[str, Any] = {}  # text -> embedding

    @property
    def is_semantic(self) -> bool:
        """Whether true semantic embeddings are available."""
        return _EMBEDDING_AVAILABLE

    def encode_corpus(self, texts: list[str]) -> Any:
        """
        Encode a corpus of texts into embeddings. Results are cached.

        Args:
            texts: List of text strings.

        Returns:
            numpy array of embeddings, or None if falling back to TF-IDF.
        """
        if _EMBEDDING_AVAILABLE:
            model = _load_model()
            embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            # Cache
            for text, emb in zip(texts, embeddings):
                self._corpus_cache[text] = emb
            return embeddings
        return None

    def retrieve(
        self,
        query: str,
        corpus_texts: list[str],
        corpus_vecs: Any = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the top-k most semantically similar texts from the corpus.

        Args:
            query: The query text.
            corpus_texts: List of corpus text strings.
            corpus_vecs: Pre-computed corpus embeddings (optional; computed if None).
            top_k: Number of results to return.
            score_threshold: Minimum similarity score to include.

        Returns:
            List of dicts with keys: index, text, score, method.
            Sorted by score descending.
        """
        if not corpus_texts:
            return []

        if _EMBEDDING_AVAILABLE:
            return self._retrieve_embedding(query, corpus_texts, corpus_vecs, top_k, score_threshold)
        elif _TFIDF_AVAILABLE:
            return self._retrieve_tfidf(query, corpus_texts, top_k, score_threshold)
        else:
            return self._retrieve_keyword(query, corpus_texts, top_k)

    def _retrieve_embedding(
        self,
        query: str,
        corpus_texts: list[str],
        corpus_vecs: Any,
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        """Retrieve using sentence embeddings."""
        import numpy as np

        model = _load_model()

        # Encode query
        query_vec = model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]

        # Encode corpus if not provided
        if corpus_vecs is None:
            corpus_vecs = self.encode_corpus(corpus_texts)

        # Compute similarities
        scores = batch_cosine_similarity(query_vec, corpus_vecs)

        # Rank
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in ranked[:top_k]:
            if score >= score_threshold:
                results.append({
                    "index": idx,
                    "text": corpus_texts[idx],
                    "score": round(score, 4),
                    "method": "sentence_embedding",
                })
        return results

    def _retrieve_tfidf(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        """Fallback: retrieve using TF-IDF."""
        query_tokens = _tokenize(query)
        corpus_tokens = [_tokenize(t) for t in corpus_texts]

        all_tokens = [query_tokens] + corpus_tokens
        idf = _compute_idf(all_tokens)
        query_vec = _tfidf_vector(query_tokens, idf)

        scores = []
        for i, tokens in enumerate(corpus_tokens):
            skill_vec = _tfidf_vector(tokens, idf)
            sim = _cosine_sim(query_vec, skill_vec)
            scores.append((i, sim))

        ranked = sorted(scores, key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in ranked[:top_k]:
            if score >= score_threshold:
                results.append({
                    "index": idx,
                    "text": corpus_texts[idx],
                    "score": round(score, 4),
                    "method": "tfidf_fallback",
                })
        return results

    def _retrieve_keyword(
        self,
        query: str,
        corpus_texts: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Last resort: keyword overlap."""
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
                    "method": "keyword_fallback",
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def retrieve_with_metadata(
        self,
        query: str,
        entries: list[dict[str, Any]],
        text_builder: callable,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve entries with metadata, using a text_builder function
        to convert each entry into a searchable text representation.

        Args:
            query: The query text.
            entries: List of entry dicts (e.g., skill index entries).
            text_builder: Function(entry) -> str that builds searchable text.
            top_k: Number of results to return.
            score_threshold: Minimum similarity score.

        Returns:
            List of dicts with keys: entry, score, method, index.
        """
        corpus_texts = [text_builder(e) for e in entries]
        results = self.retrieve(query, corpus_texts, top_k=top_k, score_threshold=score_threshold)

        for r in results:
            r["entry"] = entries[r["index"]]

        return results


# ---------------------------------------------------------------------------
# Convenience function for quick usage
# ---------------------------------------------------------------------------

def semantic_search(
    query: str,
    corpus: list[str],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    One-shot semantic search.

    Args:
        query: Search query.
        corpus: List of texts to search.
        top_k: Number of results.

    Returns:
        List of {index, text, score, method} dicts.
    """
    retriever = SemanticRetriever()
    return retriever.retrieve(query, corpus, top_k=top_k)
