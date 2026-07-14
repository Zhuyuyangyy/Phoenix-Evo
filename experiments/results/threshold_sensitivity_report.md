# Score-Threshold Sensitivity Analysis (Real Measurements)

Generated: 2026-07-14T11:51:23.094251+00:00

The production retriever ships with `score_threshold=0.0` (accept everything). This sweep quantifies the trade-off and gives an empirically justified operating point per method, answering the SCI Round 4 P2 finding that thresholds lacked justification.

> method `embedding` not run here: model load/encode failed: 403 Forbidden

## Recommended operating points

| Method | recommended threshold | F1 at threshold | negative FPR | current default |
|---|---|---|---|---|
| tfidf | 0.15 | 0.504 | 0.167 | 0.00 |
| bm25 | n/a (no viable threshold: scores are normalized per query, so absolute thresholding cannot reject out-of-scope queries) | -- | -- | 0.00 |
| keyword | 0.10 | 0.472 | 0.000 | 0.00 |

Selection rule: best F1 subject to negative FPR <= 0.25.

## Sweep: bm25

| threshold | accept precision | accept recall | F1 | negative FPR | accepted results |
|---|---|---|---|---|---|
| 0.00 | 0.250 | 0.698 | 0.368 | 1.000 | 240 |
| 0.05 | 0.282 | 0.698 | 0.401 | 0.917 | 213 |
| 0.10 | 0.291 | 0.698 | 0.411 | 0.917 | 206 |
| 0.15 | 0.305 | 0.698 | 0.424 | 0.917 | 197 |
| 0.20 | 0.326 | 0.686 | 0.442 | 0.917 | 181 |
| 0.25 | 0.335 | 0.663 | 0.445 | 0.917 | 170 |
| 0.30 | 0.351 | 0.616 | 0.447 | 0.917 | 151 |
| 0.35 | 0.369 | 0.605 | 0.458 | 0.917 | 141 |
| 0.40 | 0.381 | 0.593 | 0.464 | 0.917 | 134 |
| 0.45 | 0.383 | 0.570 | 0.458 | 0.917 | 128 |
| 0.50 | 0.387 | 0.558 | 0.457 | 0.917 | 124 |
| 0.55 | 0.405 | 0.546 | 0.465 | 0.917 | 116 |
| 0.60 | 0.411 | 0.535 | 0.465 | 0.917 | 112 |
| 0.65 | 0.455 | 0.523 | 0.486 | 0.917 | 99 |
| 0.70 | 0.483 | 0.512 | 0.497 | 0.917 | 91 |
| 0.75 | 0.537 | 0.512 | 0.524 | 0.917 | 82 |
| 0.80 | 0.560 | 0.488 | 0.522 | 0.917 | 75 |
| 0.85 | 0.597 | 0.465 | 0.523 | 0.917 | 67 |
| 0.90 | 0.610 | 0.419 | 0.497 | 0.917 | 59 |

## Sweep: keyword

| threshold | accept precision | accept recall | F1 | negative FPR | accepted results |
|---|---|---|---|---|---|
| 0.00 | 0.229 | 0.639 | 0.337 | 1.000 | 240 |
| 0.05 | 0.357 | 0.535 | 0.428 | 0.250 | 129 |
| 0.10 | 0.732 | 0.349 | 0.472 | 0.000 | 41 |
| 0.15 | 0.889 | 0.186 | 0.308 | 0.000 | 18 |
| 0.20 | 1.000 | 0.116 | 0.208 | 0.000 | 10 |
| 0.25 | 1.000 | 0.070 | 0.130 | 0.000 | 6 |
| 0.30 | 1.000 | 0.023 | 0.045 | 0.000 | 2 |
| 0.35 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.40 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.45 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.50 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.55 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.60 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.65 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.70 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.75 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.80 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.85 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.90 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |

## Sweep: tfidf

| threshold | accept precision | accept recall | F1 | negative FPR | accepted results |
|---|---|---|---|---|---|
| 0.00 | 0.233 | 0.651 | 0.344 | 1.000 | 240 |
| 0.05 | 0.317 | 0.593 | 0.413 | 0.750 | 161 |
| 0.10 | 0.517 | 0.523 | 0.520 | 0.583 | 87 |
| 0.15 | 0.780 | 0.372 | 0.504 | 0.167 | 41 |
| 0.20 | 0.955 | 0.244 | 0.389 | 0.000 | 22 |
| 0.25 | 0.944 | 0.198 | 0.327 | 0.000 | 18 |
| 0.30 | 0.929 | 0.151 | 0.260 | 0.000 | 14 |
| 0.35 | 1.000 | 0.151 | 0.263 | 0.000 | 13 |
| 0.40 | 1.000 | 0.151 | 0.263 | 0.000 | 13 |
| 0.45 | 1.000 | 0.128 | 0.227 | 0.000 | 11 |
| 0.50 | 1.000 | 0.128 | 0.227 | 0.000 | 11 |
| 0.55 | 1.000 | 0.093 | 0.170 | 0.000 | 8 |
| 0.60 | 1.000 | 0.081 | 0.150 | 0.000 | 7 |
| 0.65 | 1.000 | 0.070 | 0.130 | 0.000 | 6 |
| 0.70 | 1.000 | 0.058 | 0.110 | 0.000 | 5 |
| 0.75 | 1.000 | 0.046 | 0.089 | 0.000 | 4 |
| 0.80 | 1.000 | 0.012 | 0.023 | 0.000 | 1 |
| 0.85 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| 0.90 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |

## Interpretation

- At threshold 0.0 (the current default) every negative query leaks an irrelevant skill into the agent context (negative FPR = 1.0 whenever any score is positive).
- Raising the threshold trades recall on judged queries for a sharp reduction in false injections on out-of-scope queries.
- BM25 scores are normalized per query to [0, 1] (max-normalization), so its thresholds are relative; TF-IDF/keyword/embedding scores are absolute similarities.
