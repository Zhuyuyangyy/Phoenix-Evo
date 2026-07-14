"""
Ranking metrics and statistical utilities for the retrieval benchmark.

Pure standard library (math + random) so the benchmark runs in any
environment. All statistics are deterministic given the seed.

Metrics (per query, then averaged over queries):
    precision_at_k  -- fraction of top-k results that are relevant (grade >= 1)
    recall_at_k     -- fraction of all relevant skills found in top-k
    mrr             -- 1 / rank of the first relevant result
    ndcg_at_k       -- graded nDCG with log2 discounting

Statistics:
    bootstrap_ci        -- percentile bootstrap CI over per-query scores
    paired_permutation  -- sign-flip permutation test on per-query deltas
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def precision_at_k(ranked_ids: Sequence[str], qrels: dict[str, int], k: int) -> float:
    top = ranked_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for sid in top if qrels.get(sid, 0) >= 1)
    return hits / k


def recall_at_k(ranked_ids: Sequence[str], qrels: dict[str, int], k: int) -> float:
    relevant = {sid for sid, g in qrels.items() if g >= 1}
    if not relevant:
        return 0.0
    found = sum(1 for sid in ranked_ids[:k] if sid in relevant)
    return found / len(relevant)


def mrr(ranked_ids: Sequence[str], qrels: dict[str, int]) -> float:
    for rank, sid in enumerate(ranked_ids, start=1):
        if qrels.get(sid, 0) >= 1:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], qrels: dict[str, int], k: int) -> float:
    def dcg(grades: Sequence[int]) -> float:
        return sum(
            (2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades)
        )

    actual = dcg([qrels.get(sid, 0) for sid in ranked_ids[:k]])
    ideal_grades = sorted(qrels.values(), reverse=True)[:k]
    ideal = dcg(ideal_grades)
    return actual / ideal if ideal > 0 else 0.0


def per_query_metrics(
    ranked_ids: Sequence[str], qrels: dict[str, int], ks: Sequence[int] = (1, 3, 5),
) -> dict[str, float]:
    out: dict[str, float] = {"mrr": mrr(ranked_ids, qrels)}
    for k in ks:
        out[f"precision@{k}"] = precision_at_k(ranked_ids, qrels, k)
        out[f"recall@{k}"] = recall_at_k(ranked_ids, qrels, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, qrels, k)
    return out


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bootstrap_ci(
    values: Sequence[float],
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean of `values`."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_idx = int(alpha * n_resamples)
    hi_idx = min(int((1.0 - alpha) * n_resamples), n_resamples - 1)
    return (means[lo_idx], means[hi_idx])


def paired_permutation_test(
    values_a: Sequence[float],
    values_b: Sequence[float],
    n_resamples: int = 10_000,
    seed: int = 42,
) -> float:
    """
    Two-sided sign-flip permutation test for paired per-query scores.

    Returns the p-value for H0: mean(values_a - values_b) == 0.
    """
    if len(values_a) != len(values_b):
        raise ValueError("paired test requires equal-length score lists")
    deltas = [a - b for a, b in zip(values_a, values_b, strict=True)]
    observed = abs(sum(deltas) / len(deltas))
    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_resamples):
        flipped = [d if rng.random() < 0.5 else -d for d in deltas]
        if abs(sum(flipped) / len(flipped)) >= observed - 1e-12:
            extreme += 1
    return extreme / n_resamples
