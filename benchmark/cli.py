"""CLI entry points for the benchmark suite."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np  # type: ignore[reportMissingImports]

from benchmark.config import load_config, BenchmarkConfig
from benchmark.models import load_questions, load_ground_truths, Trace

logger = logging.getLogger("benchmark")


def _create_tool_provider(condition: str, config: BenchmarkConfig, book_id: str):  # type: ignore[no-untyped-def]
    """Create the appropriate tool provider for a condition."""
    if condition == "baseline":
        from benchmark.tools.baseline import BaselineToolProvider
        return BaselineToolProvider(config.corpus_dir, book_id, config.baseline_max_pages)
    if condition == "flat_index":
        from benchmark.tools.flat_index import FlatIndexToolProvider
        return FlatIndexToolProvider(config.corpus_dir, book_id, config.baseline_max_pages)
    if condition == "agentlib":
        from benchmark.tools.agentlib import AgentLibToolProvider
        return AgentLibToolProvider(config.agentlib_data_dir, book_id)
    msg = f"Unknown condition: {condition}"
    raise ValueError(msg)


def _load_prompt(condition: str) -> str:
    """Load system prompt for a condition."""
    prompts_dir = Path(__file__).parent / "prompts"
    path = prompts_dir / f"{condition}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def cmd_run(args: argparse.Namespace) -> None:
    """Run benchmark executions."""
    from benchmark.executor import AgentExecutor, estimate_cost

    config = load_config(args.config)
    if args.trials:
        config.trials = args.trials

    questions = load_questions(config.questions_dir, book_id=args.book_id)
    if args.question_id:
        questions = [q for q in questions if q.id == args.question_id]

    if not questions:
        logger.error("No questions found")
        sys.exit(1)

    conditions = (
        [args.condition] if args.condition != "all"
        else ["baseline", "flat_index", "agentlib"]
    )

    traces_dir = config.results_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    cumulative_cost = 0.0

    logger.info(
        "Starting benchmark: %d questions x %d conditions x %d trials",
        len(questions), len(conditions), config.trials,
    )

    for trial in range(config.trials):
        # Shuffle questions with seeded RNG for reproducibility
        shuffled = list(questions)
        rng = np.random.default_rng(trial)
        rng.shuffle(shuffled)

        for q in shuffled:
            for cond in conditions:
                trace_path = traces_dir / f"{q.id}_{cond}_t{trial}.json"
                if trace_path.exists() and not args.dry_run:
                    logger.info("  Skip (exists): %s %s trial=%d", q.id, cond, trial)
                    continue

                if args.dry_run:
                    logger.info("  [DRY RUN] %s %s trial=%d", q.id, cond, trial)
                    continue

                logger.info("  Running: %s %s trial=%d", q.id, cond, trial)

                provider = _create_tool_provider(cond, config, q.book_id)
                system_prompt = _load_prompt(cond)
                executor = AgentExecutor(
                    model=config.model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    max_tool_calls=config.max_tool_calls,
                    tool_provider=provider,
                    system_prompt=system_prompt,
                )

                trace = executor.run(q)
                trace.save(trace_path)

                cost = estimate_cost(trace)
                cumulative_cost += cost
                logger.info(
                    "    Done: %d calls, %d tokens, $%.4f (cumul: $%.2f)",
                    trace.metrics.total_tool_calls,
                    trace.metrics.cumulative_input_tokens,
                    cost, cumulative_cost,
                )

                if config.budget_limit_usd and cumulative_cost > config.budget_limit_usd:
                    logger.warning("Budget limit reached: $%.2f", cumulative_cost)
                    return

    logger.info("Benchmark complete. Total cost: $%.2f", cumulative_cost)


def cmd_score(args: argparse.Namespace) -> None:
    """Score existing traces with LLM judge."""
    from benchmark.scoring.concept_hits import classify_trace as classify_concept_hits
    from benchmark.scoring.judge import LLMJudge
    from benchmark.scoring.wrong_reads import ReadClassifier

    config = load_config(args.config)
    traces_dir = Path(args.trace_dir) if args.trace_dir else config.results_dir / "traces"
    ground_truths = load_ground_truths(config.ground_truth_dir)

    judge = LLMJudge(config.scoring_model)
    classifier = ReadClassifier(config.scoring_model)

    trace_files = sorted(traces_dir.glob("*.json"))
    logger.info("Scoring %d traces", len(trace_files))

    for path in trace_files:
        trace = Trace.load(path)

        if trace.scoring and not args.rescore:
            logger.info("  Skip (scored): %s", path.name)
            continue

        logger.info("  Scoring: %s", path.name)

        # Score accuracy
        gt = ground_truths.get(trace.question_id)
        if gt:
            trace.scoring = judge.score_answer(
                question=trace.question_text,
                reference_answer=gt.reference_answer,
                key_facts=gt.key_facts,
                agent_answer=trace.final_answer,
            )
        else:
            logger.warning("    No ground truth for %s", trace.question_id)

        # Classify reads
        classifier.classify_trace(trace)

        # Classify concept search hits/misses
        classify_concept_hits(trace)

        # Save back
        trace.save(path)

    logger.info("Scoring complete")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze scored traces and generate report."""
    from benchmark.analysis.report import generate_summary, check_success_criteria, save_report

    config = load_config(args.config)
    traces_dir = Path(args.trace_dir) if args.trace_dir else config.results_dir / "traces"
    output_dir = Path(args.output) if args.output else config.results_dir / "summary"

    trace_files = sorted(traces_dir.glob("*.json"))
    traces = [Trace.load(p) for p in trace_files]
    logger.info("Analyzing %d traces", len(traces))

    summary = generate_summary(traces)
    criteria = check_success_criteria(summary)
    summary["success_criteria"] = criteria

    save_report(summary, output_dir)

    # Print summary to console
    print("\n=== AgentLib Benchmark Results ===\n")  # noqa: T201
    for cond, cond_stats in summary.get("overall", {}).items():
        print(  # noqa: T201
            f"{cond:15s}: {cond_stats['median_tokens']:>8,.0f} tok | "
            f"{cond_stats['median_calls']:>4.1f} calls | acc={cond_stats['mean_accuracy']:.3f}"
        )

    print("\nToken reduction vs baseline:")  # noqa: T201
    for key, val in summary.get("token_reduction", {}).items():
        print(f"  {key}: {val['median_token_reduction']:.1%}")  # noqa: T201

    print("\nSuccess criteria:")  # noqa: T201
    for name, c in criteria.items():
        status = "PASS" if c.get("met") else "FAIL"
        print(f"  [{status}] {name}")  # noqa: T201

    print(f"\nReport saved to: {output_dir}")  # noqa: T201


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="AgentLib Benchmark Suite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = subparsers.add_parser("run", help="Run benchmark executions")
    run_p.add_argument("--config", default="benchmark/config.yaml")
    run_p.add_argument(
        "--condition", choices=["baseline", "flat_index", "agentlib", "all"], default="all",
    )
    run_p.add_argument("--book-id", help="Run for single book")
    run_p.add_argument("--question-id", help="Run single question")
    run_p.add_argument("--trials", type=int, help="Override trial count")
    run_p.add_argument("--dry-run", action="store_true", help="Print plan without calling API")

    # score
    score_p = subparsers.add_parser("score", help="Score traces with LLM judge")
    score_p.add_argument("--config", default="benchmark/config.yaml")
    score_p.add_argument("--trace-dir", help="Override trace directory")
    score_p.add_argument("--rescore", action="store_true", help="Re-score already-scored traces")

    # analyze
    analyze_p = subparsers.add_parser("analyze", help="Analyze and report")
    analyze_p.add_argument("--config", default="benchmark/config.yaml")
    analyze_p.add_argument("--trace-dir", help="Override trace directory")
    analyze_p.add_argument("--output", help="Output directory for report")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.command == "run":
        cmd_run(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    main()
