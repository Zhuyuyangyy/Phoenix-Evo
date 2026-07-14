"""
Retrieval method adapters for the benchmark.

Every adapter takes (query_text, corpus_texts) and returns a full ranking of
corpus indices with scores. The adapters call the SAME implementations used
by the production runtime (runtime.semantic_retriever / runtime.tfidf_utils),
so benchmark numbers measure the code that actually ships.

Methods:
    embedding -- sentence-transformers all-MiniLM-L6-v2 (runtime.semantic_retriever).
                 Skipped automatically (with a recorded reason) when the model
                 or the sentence-transformers package is unavailable.
    tfidf     -- TF-IDF + cosine similarity (runtime.tfidf_utils, the V1.1 path)
    bm25      -- Okapi BM25 over the same tokenizer (standard lexical baseline)
    keyword   -- Jaccard word overlap (the legacy pre-V1.1 path)
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable

from runtime.tfidf_utils import _compute_idf, _cosine_sim, _tfidf_vector, _tokenize

# A ranking is a list of (corpus_index, score) sorted by score descending.
Ranking = list[tuple[int, float]]
RetrievalFn = Callable[[str, list[str]], Ranking]


# ---------------------------------------------------------------------------
# embedding (production path, optional)
# ---------------------------------------------------------------------------

def probe_embedding_method() -> tuple[RetrievalFn | None, str]:
    """
    Try to construct the embedding retrieval function.

    Returns (fn, "") on success or (None, reason) when unavailable, so the
    runner can record exactly why the embedding column is missing instead of
    silently falling back to another method.
    """
    try:
        from runtime.semantic_retriever import _EMBEDDING_AVAILABLE, SemanticRetriever
    except ImportError as exc:
        return None, f"runtime.semantic_retriever import failed: {exc}"
    if not _EMBEDDING_AVAILABLE:
        return None, "sentence-transformers package not installed"

    retriever = SemanticRetriever()
    try:
        # Force model load + a real encode so failures surface here, not mid-run.
        probe = retriever.retrieve("probe query", ["probe document"], top_k=1)
    except Exception as exc:  # model download/load failure
        return None, f"embedding model unavailable: {type(exc).__name__}: {exc}"
    if not probe or probe[0]["method"] != "sentence_embedding":
        from runtime import semantic_retriever as sr
        reason = getattr(sr, "_EMBEDDING_UNAVAILABLE_REASON", "") or (
            f"retriever fell back to {probe[0]['method'] if probe else 'nothing'}"
        )
        return None, reason

    corpus_cache: dict[tuple[str, ...], object] = {}

    def embedding_rank(query: str, corpus_texts: list[str]) -> Ranking:
        key = tuple(corpus_texts)
        if key not in corpus_cache:
            corpus_cache[key] = retriever.encode_corpus(list(corpus_texts))
        results = retriever._retrieve_embedding(
            query, list(corpus_texts), corpus_cache[key],
            top_k=len(corpus_texts), score_threshold=-1.0,
        )
        return [(r["index"], float(r["score"])) for r in results]

    return embedding_rank, ""


# ---------------------------------------------------------------------------
# tfidf (production fallback path)
# ---------------------------------------------------------------------------

def tfidf_rank(query: str, corpus_texts: list[str]) -> Ranking:
    """TF-IDF + cosine, identical math to SemanticRetriever._retrieve_tfidf."""
    query_tokens = _tokenize(query)
    corpus_tokens = [_tokenize(t) for t in corpus_texts]
    idf = _compute_idf([query_tokens] + corpus_tokens)
    query_vec = _tfidf_vector(query_tokens, idf)
    scores = []
    for i, tokens in enumerate(corpus_tokens):
        scores.append((i, _cosine_sim(query_vec, _tfidf_vector(tokens, idf))))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


# ---------------------------------------------------------------------------
# bm25 (standard lexical baseline; same tokenizer as tfidf for fairness)
# ---------------------------------------------------------------------------

class _BM25Index:
    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = corpus_tokens
        self.doc_len = [len(t) for t in corpus_tokens]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if corpus_tokens else 0.0
        self.doc_tf = [Counter(t) for t in corpus_tokens]
        n_docs = len(corpus_tokens)
        df: Counter[str] = Counter()
        for tf in self.doc_tf:
            df.update(tf.keys())
        self.idf = {
            term: math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)
            for term, freq in df.items()
        }

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        tf = self.doc_tf[doc_idx]
        dl = self.doc_len[doc_idx]
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            idf = self.idf.get(term, 0.0)
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0))
            score += idf * freq * (self.k1 + 1) / denom
        return score


_bm25_cache: dict[tuple[str, ...], _BM25Index] = {}


def bm25_rank(query: str, corpus_texts: list[str]) -> Ranking:
    key = tuple(corpus_texts)
    if key not in _bm25_cache:
        _bm25_cache[key] = _BM25Index([_tokenize(t) for t in corpus_texts])
    index = _bm25_cache[key]
    query_tokens = _tokenize(query)
    # Normalize BM25 scores into [0, 1] per query so that the threshold
    # sensitivity sweep can compare methods on a common scale.
    raw = [(i, index.score(query_tokens, i)) for i in range(len(corpus_texts))]
    max_score = max((s for _, s in raw), default=0.0)
    if max_score > 0:
        raw = [(i, s / max_score) for i, s in raw]
    raw.sort(key=lambda x: x[1], reverse=True)
    return raw


# ---------------------------------------------------------------------------
# keyword (legacy Jaccard path)
# ---------------------------------------------------------------------------

def keyword_rank(query: str, corpus_texts: list[str]) -> Ranking:
    """Jaccard word overlap, identical math to SemanticRetriever._retrieve_keyword."""
    import re
    query_words = set(re.findall(r"[\w一-鿿]{2,}", query.lower()))
    scores = []
    for i, text in enumerate(corpus_texts):
        text_words = set(re.findall(r"[\w一-鿿]{2,}", text.lower()))
        overlap = (
            len(query_words & text_words) / max(len(query_words | text_words), 1)
            if text_words else 0.0
        )
        scores.append((i, overlap))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def available_methods() -> tuple[dict[str, RetrievalFn], dict[str, str]]:
    """
    Return ({method_name: fn}, {method_name: unavailable_reason}).

    Methods that cannot run in the current environment appear only in the
    second dict, with the concrete reason recorded for the report.
    """
    methods: dict[str, RetrievalFn] = {}
    unavailable: dict[str, str] = {}

    embedding_fn, reason = probe_embedding_method()
    if embedding_fn is not None:
        methods["embedding"] = embedding_fn
    else:
        unavailable["embedding"] = reason

    methods["tfidf"] = tfidf_rank
    methods["bm25"] = bm25_rank
    methods["keyword"] = keyword_rank
    return methods, unavailable
