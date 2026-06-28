"""
TF-IDF utility functions for text similarity computation.

Extracted from runtime.skill_retriever to break the circular import chain:
  runtime/__init__.py → runtime.skill_retriever → core.skill_registry → core/__init__.py → core.skill_retriever → runtime.skill_retriever

This module depends ONLY on Python standard library (math, re, collections)
and optionally jieba. No imports from core or other runtime modules.
"""

import math
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Text preprocessing for TF-IDF (Chinese/English mixed tokenization)
# ---------------------------------------------------------------------------

_CHINESE_CHAR_RE = re.compile(r'[一-鿿]')
_ENGLISH_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')
# Keep tokens with at least 2 characters to reduce noise
_MIN_TOKEN_LEN = 2

# Try to load jieba for Chinese word segmentation; fall back to char + bigram
_JIEBA_AVAILABLE = False
try:
    import jieba as _jieba
    _jieba.setLogLevel(20)  # suppress jieba's INFO logging
    _JIEBA_AVAILABLE = True
except ImportError:
    pass


def _tokenize_chinese_segment(text: str) -> list[str]:
    """
    Segment Chinese text into word-level tokens.

    Strategy:
    - If jieba is available, use jieba.cut() for word segmentation.
    - Otherwise, use character-level tokens + bigrams as fallback.

    Args:
        text: A string containing Chinese characters.

    Returns:
        List of Chinese word/char/bigram tokens.
    """
    if _JIEBA_AVAILABLE:
        # jieba.lcut returns a list of segmented words
        return [w for w in _jieba.lcut(text) if w.strip()]
    # Fallback: character-level + bigrams
    chars = _CHINESE_CHAR_RE.findall(text)
    if not chars:
        return []
    # Single characters
    tokens = list(chars)
    # Bigrams (pairs of adjacent characters)
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    return tokens


def _tokenize(text: str) -> list[str]:
    """
    Split text into word tokens for TF-IDF.

    Chinese text:
    - If jieba is available: word-level segmentation (e.g. "编码" -> ["编码"])
    - Otherwise: character-level + bigrams (e.g. "编码" -> ["编", "码", "编码"])

    English/numbers: split by word boundaries, lowercased.
    Filters tokens shorter than _MIN_TOKEN_LEN (except CJK tokens).

    Returns a flat list of tokens (preserves duplicates for TF counting).
    """
    tokens: list[str] = []
    # Chinese segmentation
    tokens.extend(_tokenize_chinese_segment(text))
    # English tokens: lowercase, filter short ones
    for t in _ENGLISH_TOKEN_RE.findall(text):
        tl = t.lower()
        if len(tl) >= _MIN_TOKEN_LEN:
            tokens.append(tl)
    return tokens


def _tokenize_to_set(text: str) -> set[str]:
    """Return deduplicated token set (for overlap calculations)."""
    return set(_tokenize(text))


def _compute_idf(documents: list[list[str]]) -> dict[str, float]:
    """
    Compute IDF weight for each term across a corpus.

    IDF(t) = ln((N + 1) / (df(t) + 1)) + 1    (smoothed)
    """
    N = len(documents)
    doc_freq: Counter = Counter()
    for doc in documents:
        for term in set(doc):
            doc_freq[term] += 1
    idf: dict[str, float] = {}
    for term in doc_freq:
        idf[term] = math.log((N + 1) / (doc_freq[term] + 1)) + 1
    return idf


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Convert a token list to a sparse TF-IDF vector (dict)."""
    if not tokens:
        return {}
    tf: Counter = Counter(tokens)
    total = max(sum(tf.values()), 1)
    vec: dict[str, float] = {}
    for term, count in tf.items():
        if term in idf:
            vec[term] = (count / total) * idf[term]
    return vec


def _cosine_sim(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    common_keys = set(vec_a) & set(vec_b)
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Legacy helper (kept for retrieve_by_keyword backward compatibility)
# ---------------------------------------------------------------------------

def _word_split(text: str) -> set[str]:
    """
    Split text into word tokens (set).
    - Chinese characters: each CJK char = one token
    - English/numbers: split by word boundaries
    - Returns lowercase tokens as a set.
    """
    return _tokenize_to_set(text)
