"""Concept search hit-rate classification."""
from __future__ import annotations

import json

from benchmark.models import Trace


def count_concept_search_hits(trace: Trace) -> tuple[int, int]:
    """Count (hits, misses) for search_concepts calls in a trace.

    A hit is a search_concepts call that returned at least one result.
    A miss is one that returned an empty result set.
    """
    hits = 0
    misses = 0
    for turn in trace.turns:
        for tc in turn.tool_calls:
            if tc.tool_name != "search_concepts":
                continue
            try:
                result = json.loads(tc.result_content)
            except (json.JSONDecodeError, TypeError):
                continue
            # Filter out metadata keys (e.g., "_truncated")
            concept_results = {k: v for k, v in result.items() if not k.startswith("_")}
            if concept_results:
                hits += 1
            else:
                misses += 1
    return hits, misses


def classify_trace(trace: Trace) -> tuple[int, int]:
    """Classify a trace and update its metrics in-place. Returns (hits, misses)."""
    hits, misses = count_concept_search_hits(trace)
    trace.metrics.concept_search_hits = hits
    trace.metrics.concept_search_misses = misses
    return hits, misses
