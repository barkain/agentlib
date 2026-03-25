"""Report generation: aggregate traces into summary statistics."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmark.analysis.stats import bootstrap_ci, compute_paired_analysis
from benchmark.models import Trace


def _group_traces(
    traces: list[Trace],
) -> dict[str, dict[str, list[Trace]]]:
    """Group traces by (question_id, condition). Returns question_id -> condition -> traces."""
    groups: dict[str, dict[str, list[Trace]]] = defaultdict(lambda: defaultdict(list))
    for t in traces:
        groups[t.question_id][t.condition].append(t)
    return dict(groups)


def _median_metric(traces: list[Trace], metric: str) -> float:
    """Get median of a metric across traces."""
    values = [getattr(t.metrics, metric) for t in traces]
    return statistics.median(values) if values else 0.0


def _median_accuracy(traces: list[Trace]) -> float:
    """Get median final_accuracy across traces."""
    values = [t.scoring.final_accuracy for t in traces if t.scoring]
    return statistics.median(values) if values else 0.0


def generate_summary(traces: list[Trace]) -> dict[str, Any]:
    """Aggregate all scored traces into a summary report."""
    grouped = _group_traces(traces)

    conditions = sorted({t.condition for t in traces})
    categories = sorted({t.question_category for t in traces})
    books = sorted({t.book_id for t in traces})

    # Build paired metric arrays: for each question, take median across trials
    metric_arrays: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    question_ids = sorted(grouped.keys())
    for qid in question_ids:
        cond_traces = grouped[qid]
        for cond in conditions:
            if cond in cond_traces:
                ts = cond_traces[cond]
                metric_arrays["cumulative_input_tokens"][cond].append(_median_metric(ts, "cumulative_input_tokens"))
                metric_arrays["total_tool_calls"][cond].append(_median_metric(ts, "total_tool_calls"))
                metric_arrays["wrong_reads"][cond].append(_median_metric(ts, "wrong_reads"))
                metric_arrays["redundant_reads"][cond].append(_median_metric(ts, "redundant_reads"))
                metric_arrays["concept_search_hits"][cond].append(_median_metric(ts, "concept_search_hits"))
                metric_arrays["concept_search_misses"][cond].append(_median_metric(ts, "concept_search_misses"))
                metric_arrays["accuracy"][cond].append(_median_accuracy(ts))

    # Overall statistics
    overall: dict[str, Any] = {}
    for cond in conditions:
        tokens = metric_arrays["cumulative_input_tokens"].get(cond, [])
        calls = metric_arrays["total_tool_calls"].get(cond, [])
        accuracy = metric_arrays["accuracy"].get(cond, [])
        wrong = metric_arrays["wrong_reads"].get(cond, [])
        redundant = metric_arrays["redundant_reads"].get(cond, [])
        concept_hits = metric_arrays["concept_search_hits"].get(cond, [])
        concept_misses = metric_arrays["concept_search_misses"].get(cond, [])
        total_searches = sum(concept_hits) + sum(concept_misses)
        hit_rate = sum(concept_hits) / total_searches if total_searches > 0 else 0.0

        overall[cond] = {
            "median_tokens": round(statistics.median(tokens), 1) if tokens else 0,
            "median_calls": round(statistics.median(calls), 1) if calls else 0,
            "mean_accuracy": round(statistics.mean(accuracy), 3) if accuracy else 0,
            "mean_wrong_reads": round(statistics.mean(wrong), 2) if wrong else 0,
            "mean_redundant_reads": round(statistics.mean(redundant), 2) if redundant else 0,
            "concept_search_hit_rate": round(hit_rate, 3),
            "concept_search_total": int(total_searches),
        }

    # Token reduction calculations
    reductions: dict[str, Any] = {}
    baseline_tokens = metric_arrays["cumulative_input_tokens"].get("baseline", [])
    for cond in conditions:
        if cond == "baseline":
            continue
        cond_tokens = metric_arrays["cumulative_input_tokens"].get(cond, [])
        if baseline_tokens and cond_tokens and len(baseline_tokens) == len(cond_tokens):
            ratios = [1 - (c / b) if b > 0 else 0 for b, c in zip(baseline_tokens, cond_tokens)]
            median_reduction = statistics.median(ratios)
            ci = bootstrap_ci(ratios)
            reductions[f"vs_{cond}"] = {
                "median_token_reduction": round(median_reduction, 3),
                "ci_95": [round(ci[0], 3), round(ci[1], 3)],
            }

    # Pairwise statistical tests
    pairwise = compute_paired_analysis(dict(metric_arrays), conditions)

    # By-category breakdown
    by_category: dict[str, Any] = {}
    for cat in categories:
        cat_traces = [t for t in traces if t.question_category == cat]
        cat_grouped = _group_traces(cat_traces)
        cat_stats: dict[str, Any] = {}
        for cond in conditions:
            cond_tokens = []
            for qid in sorted(cat_grouped.keys()):
                if cond in cat_grouped[qid]:
                    cond_tokens.append(_median_metric(cat_grouped[qid][cond], "cumulative_input_tokens"))
            cat_stats[cond] = {
                "median_tokens": round(statistics.median(cond_tokens), 1) if cond_tokens else 0,
                "count": len(cond_tokens),
            }
        by_category[cat] = cat_stats

    # By-book breakdown
    by_book: dict[str, Any] = {}
    for book in books:
        book_traces = [t for t in traces if t.book_id == book]
        book_grouped = _group_traces(book_traces)
        book_stats: dict[str, Any] = {}
        for cond in conditions:
            cond_tokens = []
            for qid in sorted(book_grouped.keys()):
                if cond in book_grouped[qid]:
                    cond_tokens.append(_median_metric(book_grouped[qid][cond], "cumulative_input_tokens"))
            book_stats[cond] = {
                "median_tokens": round(statistics.median(cond_tokens), 1) if cond_tokens else 0,
                "count": len(cond_tokens),
            }
        by_book[book] = book_stats

    return {
        "metadata": {
            "total_traces": len(traces),
            "conditions": conditions,
            "question_count": len(question_ids),
            "categories": categories,
            "books": books,
        },
        "overall": overall,
        "token_reduction": reductions,
        "pairwise_tests": pairwise,
        "by_category": by_category,
        "by_book": by_book,
    }


def check_success_criteria(summary: dict[str, Any]) -> dict[str, Any]:
    """Check results against success/failure thresholds."""
    criteria: dict[str, Any] = {}

    # Token reduction vs baseline >= 50%
    agentlib_reduction = summary.get("token_reduction", {}).get("vs_agentlib", {})
    if agentlib_reduction:
        val = agentlib_reduction.get("median_token_reduction", 0)
        criteria["token_reduction_vs_baseline"] = {
            "value": val,
            "threshold": 0.50,
            "met": val >= 0.50,
        }

    # Token reduction vs flat_index >= 20%
    flat_tokens = summary.get("overall", {}).get("flat_index", {}).get("median_tokens", 0)
    agentlib_tokens = summary.get("overall", {}).get("agentlib", {}).get("median_tokens", 0)
    if flat_tokens > 0:
        reduction_vs_flat = 1 - (agentlib_tokens / flat_tokens)
        criteria["token_reduction_vs_flat_index"] = {
            "value": round(reduction_vs_flat, 3),
            "threshold": 0.20,
            "met": reduction_vs_flat >= 0.20,
        }

    # Accuracy not degraded
    baseline_acc = summary.get("overall", {}).get("baseline", {}).get("mean_accuracy", 0)
    agentlib_acc = summary.get("overall", {}).get("agentlib", {}).get("mean_accuracy", 0)
    criteria["accuracy_not_degraded"] = {
        "baseline": baseline_acc,
        "agentlib": agentlib_acc,
        "met": agentlib_acc >= baseline_acc - 0.03,
    }

    return criteria


def save_report(summary: dict[str, Any], output_dir: Path) -> None:
    """Save summary as JSON and markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = output_dir / "report.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Markdown
    md_path = output_dir / "report.md"
    md_lines = ["# AgentLib Benchmark Report\n"]

    md_lines.append("## Overall Results\n")
    md_lines.append("| Condition | Median Tokens | Median Calls | Accuracy | Wrong Reads | Ls Hit Rate |")
    md_lines.append("|-----------|--------------|-------------|----------|-------------|-------------|")
    for cond, stats in summary.get("overall", {}).items():
        hit_rate = stats.get("concept_search_hit_rate", 0)
        total = stats.get("concept_search_total", 0)
        hit_str = f"{hit_rate:.0%} ({total})" if total > 0 else "n/a"
        md_lines.append(
            f"| {cond} | {stats['median_tokens']:,.0f} | {stats['median_calls']:.1f} | "
            f"{stats['mean_accuracy']:.3f} | {stats['mean_wrong_reads']:.2f} | {hit_str} |"
        )

    if summary.get("token_reduction"):
        md_lines.append("\n## Token Reduction vs Baseline\n")
        for key, val in summary["token_reduction"].items():
            md_lines.append(f"- **{key}**: {val['median_token_reduction']:.1%} (95% CI: {val['ci_95']})")

    md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
