# Retrieval Benchmark Report (Real Measurements)

Generated: 2026-07-14T11:51:15.756343+00:00  
Git commit: `4b97074`  
Python 3.11.15, packages: {'sentence_transformers': '5.6.0', 'numpy': '2.4.6', 'torch': '2.13.0+cu130', 'jieba': 'not installed'}

> **Provenance:** every number below is a real measurement of the retrieval implementations in `runtime/` against the labeled dataset in `experiments/retrieval_benchmark/dataset.py`. Nothing is simulated.

Corpus: 40 skills. Queries: 48 judged + 12 negative. Bootstrap: 10000 resamples, seed 42.

## Methods not run in this environment

- **embedding**: model load/encode failed: 403 Forbidden

Re-run `python -m experiments.retrieval_benchmark.run_benchmark` in an environment where the method is available to fill in its column; the dataset and seeds are fixed, so all other columns will reproduce.

## Overall results (mean [95% bootstrap CI])

| Method | ndcg@5 | mrr | precision@1 | precision@3 | recall@5 | mean latency (ms) |
|---|---|---|---|---|---|---|
| bm25 | 0.713 [0.619, 0.801] | 0.788 [0.687, 0.883] | 0.708 [0.583, 0.833] | 0.389 [0.326, 0.451] | 0.698 [0.597, 0.792] | 0.07 |
| keyword | 0.683 [0.582, 0.780] | 0.761 [0.654, 0.863] | 0.688 [0.542, 0.812] | 0.340 [0.278, 0.403] | 0.653 [0.552, 0.753] | 0.38 |
| tfidf | 0.702 [0.610, 0.790] | 0.797 [0.694, 0.892] | 0.729 [0.604, 0.854] | 0.375 [0.312, 0.438] | 0.656 [0.559, 0.750] | 1.10 |

## Results by query category (nDCG@5 / MRR / P@1)

| Method | cross_domain | exact_keyword | multi_intent | paraphrase |
|---|---|---|---|---|
| bm25 | 0.718 / 0.846 / 0.800 | 0.979 / 1.000 / 1.000 | 0.725 / 0.938 / 0.875 | 0.573 / 0.594 / 0.450 |
| keyword | 0.625 / 0.739 / 0.700 | 0.975 / 1.000 / 1.000 | 0.509 / 0.674 / 0.500 | 0.636 / 0.689 / 0.600 |
| tfidf | 0.714 / 0.846 / 0.800 | 0.975 / 1.000 / 1.000 | 0.715 / 1.000 / 1.000 | 0.554 / 0.589 / 0.450 |

Query counts per category: cross_domain: 10, exact_keyword: 10, multi_intent: 8, paraphrase: 20

## Pairwise significance (paired sign-flip permutation test)

| Metric | Method A | Method B | mean A | mean B | p-value |
|---|---|---|---|---|---|
| ndcg@5 | bm25 | keyword | 0.713 | 0.683 | 0.3055 |
| mrr | bm25 | keyword | 0.788 | 0.761 | 0.4822 |
| ndcg@5 | bm25 | tfidf | 0.713 | 0.702 | 0.2617 |
| mrr | bm25 | tfidf | 0.788 | 0.797 | 1.0000 |
| ndcg@5 | keyword | tfidf | 0.683 | 0.702 | 0.5511 |
| mrr | keyword | tfidf | 0.761 | 0.797 | 0.3880 |

## Negative queries (top-1 scores, false-positive exposure)

The runtime currently uses `score_threshold=0.0`, i.e. it will inject the top-ranked skill even for queries that have no relevant skill. The scores below quantify that exposure; see the sensitivity analysis for the threshold trade-off.

| Method | mean top-1 score on negatives | max top-1 score on negatives |
|---|---|---|
| bm25 | 0.917 | 1.000 |
| keyword | 0.045 | 0.067 |
| tfidf | 0.098 | 0.162 |

## Limitations (disclosed)

- Relevance judgments are single-annotator (project author) with a second review pass; no inter-annotator agreement yet.
- The corpus contains 40 skills; scaling behavior is measured separately.
- 15 of 40 skill cards are grounded in real repository artifacts; the remaining 25 are realistic but authored for the benchmark.
