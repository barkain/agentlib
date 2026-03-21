"""Statistical analysis: Wilcoxon signed-rank test, Cliff's delta, bootstrap CIs."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np  # type: ignore[reportMissingImports]
from scipy import stats as sp_stats  # type: ignore[reportMissingImports]


def wilcoxon_test(
    condition_a: list[float],
    condition_b: list[float],
    bonferroni_n: int = 5,
) -> dict:
    """Paired Wilcoxon signed-rank test.

    Args:
        condition_a: Values for condition A (paired by index).
        condition_b: Values for condition B (paired by index).
        bonferroni_n: Number of tests for Bonferroni correction.

    Returns:
        Dict with statistic, p_value, significant, threshold.
    """
    # Filter zero differences (Wilcoxon can't handle them)
    nonzero = [(a, b) for a, b in zip(condition_a, condition_b) if a != b]
    if len(nonzero) < 3:
        return {"statistic": 0.0, "p_value": 1.0, "significant": False, "threshold": 0.01 / bonferroni_n}

    a_nz = [x[0] for x in nonzero]
    b_nz = [x[1] for x in nonzero]
    stat, p = sp_stats.wilcoxon(a_nz, b_nz)
    threshold = 0.01 / bonferroni_n
    return {
        "statistic": float(stat),
        "p_value": float(p),
        "significant": p < threshold,
        "threshold": threshold,
    }


def cliffs_delta(condition_a: list[float], condition_b: list[float]) -> dict:
    """Cliff's delta effect size (non-parametric).

    Returns:
        Dict with delta value and interpretation.
    """
    n_a = len(condition_a)
    n_b = len(condition_b)
    if n_a == 0 or n_b == 0:
        return {"delta": 0.0, "interpretation": "negligible"}

    dominance = 0
    for a in condition_a:
        for b in condition_b:
            if a > b:
                dominance += 1
            elif a < b:
                dominance -= 1

    d = dominance / (n_a * n_b)
    abs_d = abs(d)

    if abs_d < 0.147:
        interp = "negligible"
    elif abs_d < 0.33:
        interp = "small"
    elif abs_d < 0.474:
        interp = "medium"
    else:
        interp = "large"

    return {"delta": round(d, 4), "interpretation": interp}


def bootstrap_ci(
    data: list[float],
    stat_fn: Callable = np.median,
    n_resamples: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap confidence interval for a statistic.

    Args:
        data: Sample data.
        stat_fn: Statistic function (default: median).
        n_resamples: Number of bootstrap resamples.
        ci: Confidence level.
        seed: Random seed for reproducibility.

    Returns:
        (lower, upper) bounds of CI.
    """
    rng = np.random.default_rng(seed)
    arr = np.array(data)
    n = len(arr)

    if n == 0:
        return (0.0, 0.0)

    boot_stats = np.array([
        stat_fn(rng.choice(arr, size=n, replace=True))
        for _ in range(n_resamples)
    ])

    alpha = (1 - ci) / 2
    lower = float(np.percentile(boot_stats, alpha * 100))
    upper = float(np.percentile(boot_stats, (1 - alpha) * 100))
    return (round(lower, 4), round(upper, 4))


def compute_paired_analysis(
    results: dict[str, dict[str, list[float]]],
    conditions: list[str] | None = None,
) -> dict:
    """Run all pairwise comparisons across conditions.

    Args:
        results: Nested dict of metric_name -> condition_name -> list of values.
                 Values must be paired by index (same question ordering).
        conditions: Condition names to compare. Default: all found in data.

    Returns:
        Dict with pairwise comparison results per metric.
    """
    if conditions is None:
        conditions = sorted({c for metric_data in results.values() for c in metric_data})

    output: dict = {}

    for metric_name, metric_data in results.items():
        metric_output: dict = {}
        for i, cond_a in enumerate(conditions):
            for cond_b in conditions[i + 1:]:
                if cond_a not in metric_data or cond_b not in metric_data:
                    continue
                vals_a = metric_data[cond_a]
                vals_b = metric_data[cond_b]
                if len(vals_a) != len(vals_b):
                    continue

                pair_key = f"{cond_a}_vs_{cond_b}"
                metric_output[pair_key] = {
                    "wilcoxon": wilcoxon_test(vals_a, vals_b),
                    "cliffs_delta": cliffs_delta(vals_a, vals_b),
                    "median_a": round(float(np.median(vals_a)), 4),
                    "median_b": round(float(np.median(vals_b)), 4),
                    "median_diff": round(float(np.median(vals_a)) - float(np.median(vals_b)), 4),
                }

        output[metric_name] = metric_output

    return output
