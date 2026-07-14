"""
Retrieval benchmark runner.

Runs every available retrieval method over the labeled dataset and reports
REAL measured ranking quality. No simulation: every number in the output is
computed from an actual retrieval call against the corpus.

Usage:
    python -m experiments.retrieval_benchmark.run_benchmark \
        [--out-dir experiments/results] [--bootstrap 10000] [--seed 42]

Outputs:
    <out-dir>/retrieval_benchmark_results.json  -- full per-query results
    <out-dir>/retrieval_benchmark_report.md     -- aggregated report
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from experiments.retrieval_benchmark import dataset, metrics
from experiments.retrieval_benchmark.dataset import SKILLS, searchable_text
from experiments.retrieval_benchmark.methods import available_methods

KS = (1, 3, 5)
METRIC_NAMES = ["mrr"] + [
    f"{m}@{k}" for k in KS for m in ("precision", "recall", "ndcg")
]
# Headline metrics used for pairwise significance testing
SIGNIFICANCE_METRICS = ("ndcg@5", "mrr")


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _package_versions() -> dict[str, str]:
    versions = {}
    for pkg in ("sentence_transformers", "numpy", "torch", "jieba"):
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "installed")
        except ImportError:
            versions[pkg] = "not installed"
    return versions


def run(out_dir: Path, n_bootstrap: int, seed: int) -> dict:
    problems = dataset.validate_dataset()
    if problems:
        raise SystemExit("Dataset validation failed:\n" + "\n".join(problems))

    corpus_texts = [searchable_text(s) for s in SKILLS]
    skill_ids = [s.skill_id for s in SKILLS]
    methods, unavailable = available_methods()

    judged = dataset.judged_queries()
    negatives = dataset.negative_queries()

    per_method: dict[str, dict] = {}
    for name, fn in methods.items():
        query_rows = []
        latencies = []
        for q in judged:
            t0 = time.perf_counter()
            ranking = fn(q.text, corpus_texts)
            latencies.append(time.perf_counter() - t0)
            ranked_ids = [skill_ids[i] for i, _ in ranking]
            row = {
                "query_id": q.query_id,
                "category": q.category,
                "top5": [
                    {"skill_id": skill_ids[i], "score": round(s, 4)}
                    for i, s in ranking[:5]
                ],
                "metrics": metrics.per_query_metrics(ranked_ids, q.qrels, KS),
            }
            query_rows.append(row)

        negative_rows = []
        for q in negatives:
            ranking = fn(q.text, corpus_texts)
            top1_idx, top1_score = ranking[0] if ranking else (None, 0.0)
            negative_rows.append({
                "query_id": q.query_id,
                "top1_skill_id": skill_ids[top1_idx] if top1_idx is not None else None,
                "top1_score": round(top1_score, 4),
            })

        per_method[name] = {
            "judged_queries": query_rows,
            "negative_queries": negative_rows,
            "mean_latency_ms": round(1000 * metrics.mean(latencies), 3),
        }

    # ---- aggregate ----
    aggregates: dict[str, dict] = {}
    for name, data in per_method.items():
        agg: dict[str, dict] = {}
        for metric in METRIC_NAMES:
            values = [row["metrics"][metric] for row in data["judged_queries"]]
            lo, hi = metrics.bootstrap_ci(values, n_bootstrap, seed=seed)
            agg[metric] = {
                "mean": round(metrics.mean(values), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
            }
        by_category: dict[str, dict] = {}
        categories = sorted({row["category"] for row in data["judged_queries"]})
        for cat in categories:
            rows = [r for r in data["judged_queries"] if r["category"] == cat]
            by_category[cat] = {
                "n": len(rows),
                "ndcg@5": round(metrics.mean([r["metrics"]["ndcg@5"] for r in rows]), 4),
                "mrr": round(metrics.mean([r["metrics"]["mrr"] for r in rows]), 4),
                "precision@1": round(
                    metrics.mean([r["metrics"]["precision@1"] for r in rows]), 4),
            }
        aggregates[name] = {"overall": agg, "by_category": by_category,
                            "mean_latency_ms": data["mean_latency_ms"]}

    # ---- pairwise significance ----
    significance = []
    names = sorted(methods.keys())
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for metric in SIGNIFICANCE_METRICS:
                va = [r["metrics"][metric] for r in per_method[a]["judged_queries"]]
                vb = [r["metrics"][metric] for r in per_method[b]["judged_queries"]]
                p = metrics.paired_permutation_test(va, vb, n_bootstrap, seed=seed)
                significance.append({
                    "method_a": a, "method_b": b, "metric": metric,
                    "mean_a": round(metrics.mean(va), 4),
                    "mean_b": round(metrics.mean(vb), 4),
                    "p_value": round(p, 5),
                })

    results = {
        "benchmark": "phoenix-evo-retrieval-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": _package_versions(),
        },
        "provenance": {
            "measurement": "real",
            "note": (
                "All metrics are computed from actual retrieval calls against the "
                "40-skill corpus. Nothing in this file is simulated. Relevance "
                "judgments are single-annotator (project author) with a second "
                "review pass; see dataset.py docstring."
            ),
        },
        "config": {
            "n_skills": len(SKILLS),
            "n_queries_judged": len(judged),
            "n_queries_negative": len(negatives),
            "ks": list(KS),
            "bootstrap_resamples": n_bootstrap,
            "seed": seed,
        },
        "methods_run": sorted(methods.keys()),
        "methods_unavailable": unavailable,
        "aggregates": aggregates,
        "significance_tests": significance,
        "per_method": per_method,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "retrieval_benchmark_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    report_path = out_dir / "retrieval_benchmark_report.md"
    report_path.write_text(render_report(results))
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")
    return results


def render_report(results: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Retrieval Benchmark Report (Real Measurements)")
    add("")
    add(f"Generated: {results['generated_at']}  ")
    add(f"Git commit: `{results['git_commit']}`  ")
    add(f"Python {results['environment']['python']}, "
        f"packages: {results['environment']['packages']}")
    add("")
    add("> **Provenance:** every number below is a real measurement of the retrieval "
        "implementations in `runtime/` against the labeled dataset in "
        "`experiments/retrieval_benchmark/dataset.py`. Nothing is simulated.")
    add("")
    cfg = results["config"]
    add(f"Corpus: {cfg['n_skills']} skills. Queries: {cfg['n_queries_judged']} judged "
        f"+ {cfg['n_queries_negative']} negative. Bootstrap: "
        f"{cfg['bootstrap_resamples']} resamples, seed {cfg['seed']}.")
    add("")
    if results["methods_unavailable"]:
        add("## Methods not run in this environment")
        add("")
        for name, reason in results["methods_unavailable"].items():
            add(f"- **{name}**: {reason}")
        add("")
        add("Re-run `python -m experiments.retrieval_benchmark.run_benchmark` in an "
            "environment where the method is available to fill in its column; the "
            "dataset and seeds are fixed, so all other columns will reproduce.")
        add("")

    add("## Overall results (mean [95% bootstrap CI])")
    add("")
    methods = results["methods_run"]
    header_metrics = ["ndcg@5", "mrr", "precision@1", "precision@3", "recall@5"]
    add("| Method | " + " | ".join(header_metrics) + " | mean latency (ms) |")
    add("|---" * (len(header_metrics) + 2) + "|")
    for name in methods:
        agg = results["aggregates"][name]["overall"]
        cells = []
        for m in header_metrics:
            e = agg[m]
            cells.append(f"{e['mean']:.3f} [{e['ci95'][0]:.3f}, {e['ci95'][1]:.3f}]")
        lat = results["aggregates"][name]["mean_latency_ms"]
        add(f"| {name} | " + " | ".join(cells) + f" | {lat:.2f} |")
    add("")

    add("## Results by query category (nDCG@5 / MRR / P@1)")
    add("")
    categories = sorted(next(iter(results["aggregates"].values()))["by_category"].keys())
    add("| Method | " + " | ".join(categories) + " |")
    add("|---" * (len(categories) + 1) + "|")
    for name in methods:
        by_cat = results["aggregates"][name]["by_category"]
        cells = [
            f"{by_cat[c]['ndcg@5']:.3f} / {by_cat[c]['mrr']:.3f} / {by_cat[c]['precision@1']:.3f}"
            for c in categories
        ]
        add(f"| {name} | " + " | ".join(cells) + " |")
    add("")
    n_by_cat = next(iter(results["aggregates"].values()))["by_category"]
    add("Query counts per category: " +
        ", ".join(f"{c}: {n_by_cat[c]['n']}" for c in categories))
    add("")

    add("## Pairwise significance (paired sign-flip permutation test)")
    add("")
    add("| Metric | Method A | Method B | mean A | mean B | p-value |")
    add("|---|---|---|---|---|---|")
    for row in results["significance_tests"]:
        add(f"| {row['metric']} | {row['method_a']} | {row['method_b']} | "
            f"{row['mean_a']:.3f} | {row['mean_b']:.3f} | {row['p_value']:.4f} |")
    add("")

    add("## Negative queries (top-1 scores, false-positive exposure)")
    add("")
    add("The runtime currently uses `score_threshold=0.0`, i.e. it will inject the "
        "top-ranked skill even for queries that have no relevant skill. The scores "
        "below quantify that exposure; see the sensitivity analysis for the "
        "threshold trade-off.")
    add("")
    add("| Method | mean top-1 score on negatives | max top-1 score on negatives |")
    add("|---|---|---|")
    for name in methods:
        neg = results["per_method"][name]["negative_queries"]
        scores = [r["top1_score"] for r in neg]
        add(f"| {name} | {sum(scores) / len(scores):.3f} | {max(scores):.3f} |")
    add("")

    add("## Limitations (disclosed)")
    add("")
    add("- Relevance judgments are single-annotator (project author) with a second "
        "review pass; no inter-annotator agreement yet.")
    add("- The corpus contains 40 skills; scaling behavior is measured separately.")
    add("- 15 of 40 skill cards are grounded in real repository artifacts; the "
        "remaining 25 are realistic but authored for the benchmark.")
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="experiments/results", type=Path)
    parser.add_argument("--bootstrap", default=10_000, type=int)
    parser.add_argument("--seed", default=42, type=int)
    args = parser.parse_args()
    run(args.out_dir, args.bootstrap, args.seed)


if __name__ == "__main__":
    main()
