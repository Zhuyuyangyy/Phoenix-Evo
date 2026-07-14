"""
Score-threshold sensitivity analysis (addresses SCI Review Round 4, P2).

The production retriever currently uses `score_threshold=0.0`, which means
the top-ranked skill is injected even when nothing in the corpus is relevant
(e.g. out-of-scope tasks). This analysis sweeps the acceptance threshold and
measures, for each retrieval method, the real trade-off between:

    accept_precision -- of the top-5 results with score >= t on judged
                        queries, what fraction are relevant (grade >= 1)?
    accept_recall    -- of all relevant skills for judged queries, what
                        fraction are retrieved in top-5 with score >= t?
    f1               -- harmonic mean of the two
    negative_fpr     -- fraction of negative (no-relevant-skill) queries
                        whose top-1 score still clears the threshold,
                        i.e. an irrelevant skill would be injected

Usage:
    python -m experiments.retrieval_benchmark.sensitivity \
        [--out-dir experiments/results]

Outputs:
    <out-dir>/threshold_sensitivity_results.json
    <out-dir>/threshold_sensitivity_report.md
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from experiments.retrieval_benchmark import dataset
from experiments.retrieval_benchmark.dataset import SKILLS, searchable_text
from experiments.retrieval_benchmark.methods import available_methods

THRESHOLDS = [round(0.05 * i, 2) for i in range(19)]  # 0.00 .. 0.90
TOP_K = 5


def run(out_dir: Path) -> dict:
    corpus_texts = [searchable_text(s) for s in SKILLS]
    skill_ids = [s.skill_id for s in SKILLS]
    methods, unavailable = available_methods()

    judged = dataset.judged_queries()
    negatives = dataset.negative_queries()

    per_method: dict[str, list[dict]] = {}
    for name, fn in methods.items():
        # Rank once per query; sweep thresholds over the fixed rankings.
        judged_rankings = []
        for q in judged:
            ranking = fn(q.text, corpus_texts)[:TOP_K]
            judged_rankings.append((q, [(skill_ids[i], s) for i, s in ranking]))
        negative_top1 = []
        for q in negatives:
            ranking = fn(q.text, corpus_texts)
            negative_top1.append(ranking[0][1] if ranking else 0.0)

        rows = []
        total_relevant = sum(
            sum(1 for g in q.qrels.values() if g >= 1) for q in judged
        )
        for t in THRESHOLDS:
            accepted = 0
            accepted_relevant = 0
            recalled_relevant = 0
            for q, ranked in judged_rankings:
                for sid, score in ranked:
                    if score >= t:
                        accepted += 1
                        if q.qrels.get(sid, 0) >= 1:
                            accepted_relevant += 1
                            recalled_relevant += 1
            precision = accepted_relevant / accepted if accepted else 0.0
            recall = recalled_relevant / total_relevant if total_relevant else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if precision + recall > 0 else 0.0)
            fpr = sum(1 for s in negative_top1 if s >= t) / len(negative_top1)
            rows.append({
                "threshold": t,
                "accept_precision": round(precision, 4),
                "accept_recall": round(recall, 4),
                "f1": round(f1, 4),
                "negative_fpr": round(fpr, 4),
                "n_accepted": accepted,
            })
        per_method[name] = rows

    # Recommended threshold per method: best F1 among thresholds with
    # negative FPR <= 0.25 (at most 3 of 12 negatives leak through).
    # Methods where no threshold meets the cap get no recommendation:
    # per-query normalized scores (e.g. BM25 max-normalization) cannot
    # reject out-of-scope queries by absolute thresholding.
    recommendations = {}
    for name, rows in per_method.items():
        capped = [r for r in rows if r["negative_fpr"] <= 0.25]
        if capped:
            best = max(capped, key=lambda r: r["f1"])
            recommendations[name] = {
                "recommended_threshold": best["threshold"],
                "f1": best["f1"],
                "negative_fpr": best["negative_fpr"],
                "note": "best F1 subject to negative FPR <= 0.25",
            }
        else:
            recommendations[name] = {
                "recommended_threshold": None,
                "note": (
                    "no viable threshold: scores are normalized per query, so "
                    "absolute thresholding cannot reject out-of-scope queries"
                ),
            }

    results = {
        "analysis": "score-threshold-sensitivity-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "measurement": "real",
            "note": "Sweep over real rankings; no simulation.",
        },
        "config": {"top_k": TOP_K, "thresholds": THRESHOLDS,
                   "fpr_cap_for_recommendation": 0.25},
        "methods_run": sorted(methods.keys()),
        "methods_unavailable": unavailable,
        "current_production_default": 0.0,
        "recommendations": recommendations,
        "per_method": per_method,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "threshold_sensitivity_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    report_path = out_dir / "threshold_sensitivity_report.md"
    report_path.write_text(render_report(results))
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")
    return results


def render_report(results: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Score-Threshold Sensitivity Analysis (Real Measurements)")
    add("")
    add(f"Generated: {results['generated_at']}")
    add("")
    add("The production retriever ships with `score_threshold=0.0` (accept "
        "everything). This sweep quantifies the trade-off and gives an "
        "empirically justified operating point per method, answering the "
        "SCI Round 4 P2 finding that thresholds lacked justification.")
    add("")
    if results["methods_unavailable"]:
        for name, reason in results["methods_unavailable"].items():
            add(f"> method `{name}` not run here: {reason}")
        add("")
    add("## Recommended operating points")
    add("")
    add("| Method | recommended threshold | F1 at threshold | negative FPR | current default |")
    add("|---|---|---|---|---|")
    for name, rec in results["recommendations"].items():
        if rec["recommended_threshold"] is None:
            add(f"| {name} | n/a ({rec['note']}) | -- | -- | 0.00 |")
        else:
            add(f"| {name} | {rec['recommended_threshold']:.2f} | {rec['f1']:.3f} | "
                f"{rec['negative_fpr']:.3f} | 0.00 |")
    add("")
    add("Selection rule: best F1 subject to negative FPR <= 0.25.")
    add("")
    for name in results["methods_run"]:
        add(f"## Sweep: {name}")
        add("")
        add("| threshold | accept precision | accept recall | F1 | negative FPR | accepted results |")
        add("|---|---|---|---|---|---|")
        for row in results["per_method"][name]:
            add(f"| {row['threshold']:.2f} | {row['accept_precision']:.3f} | "
                f"{row['accept_recall']:.3f} | {row['f1']:.3f} | "
                f"{row['negative_fpr']:.3f} | {row['n_accepted']} |")
        add("")
    add("## Interpretation")
    add("")
    add("- At threshold 0.0 (the current default) every negative query leaks an "
        "irrelevant skill into the agent context (negative FPR = 1.0 whenever "
        "any score is positive).")
    add("- Raising the threshold trades recall on judged queries for a sharp "
        "reduction in false injections on out-of-scope queries.")
    add("- BM25 scores are normalized per query to [0, 1] (max-normalization), "
        "so its thresholds are relative; TF-IDF/keyword/embedding scores are "
        "absolute similarities.")
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="experiments/results", type=Path)
    args = parser.parse_args()
    run(args.out_dir)


if __name__ == "__main__":
    main()
