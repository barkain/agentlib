"""Concept search hit-rate classification."""
from __future__ import annotations

import json

from benchmark.models import Trace

# Keys in search_concepts results that are not actual concept matches
_NON_RESULT_KEYS = {"error", "truncated", "_truncated"}


def count_concept_search_hits(trace: Trace) -> tuple[int, int]:
    """Count (hits, misses) for search_concepts calls in a trace.

    A hit is a search_concepts call that returned at least one concept result.
    A miss is one that returned no results, an error, or a non-JSON response.
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
                misses += 1
                continue
            if not isinstance(result, dict):
                misses += 1
                continue
            # Filter out metadata/error keys
            concept_results = {
                k: v for k, v in result.items()
                if k not in _NON_RESULT_KEYS and not k.startswith("_")
            }
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
