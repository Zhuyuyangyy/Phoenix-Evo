"""
Phoenix-Evo Real Retrieval Benchmark
====================================

A labeled skill-retrieval benchmark with graded relevance judgments.
All numbers produced by this package are REAL MEASUREMENTS of the
retrieval implementations in `runtime/` -- nothing is simulated.

Modules:
    dataset      -- 40-skill corpus + 60 annotated queries (graded qrels)
    methods      -- retrieval method adapters (embedding / tfidf / bm25 / keyword)
    metrics      -- P@k, R@k, MRR, nDCG@k, bootstrap CIs, permutation tests
    run_benchmark -- CLI runner producing JSON results + markdown report
    sensitivity  -- score-threshold sensitivity sweep (accept/reject analysis)

Reproduce:
    python -m experiments.retrieval_benchmark.run_benchmark
    python -m experiments.retrieval_benchmark.sensitivity
"""
