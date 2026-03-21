"""Wrong-read and redundant-read classification."""
from __future__ import annotations

import anthropic  # type: ignore[reportMissingImports]

from benchmark.models import Trace, ToolCallRecord


# Tools that return actual content (not just metadata)
CONTENT_TOOLS = {"read_file", "read_chunks"}


class ReadClassifier:
    """Classify tool calls as wrong reads or redundant reads."""

    def __init__(self, model: str):
        self._client = anthropic.Anthropic()
        self._model = model

    def classify_trace(self, trace: Trace) -> tuple[int, int]:
        """Classify all reads in a trace. Returns (wrong_reads, redundant_reads).

        Also updates result_relevant on each ToolCallRecord in-place.
        """
        wrong_reads = 0
        redundant_reads = 0
        seen_content: list[str] = []

        for turn in trace.turns:
            for tc in turn.tool_calls:
                if tc.tool_name not in CONTENT_TOOLS:
                    tc.result_relevant = True
                    continue

                # Check redundancy (algorithmic — no LLM needed)
                if self._is_redundant(tc, seen_content):
                    redundant_reads += 1

                seen_content.append(tc.result_content)

                # Check relevance (LLM judge)
                is_relevant = self._is_relevant(
                    trace.question_text,
                    trace.final_answer,
                    tc.result_content,
                )
                tc.result_relevant = is_relevant
                if not is_relevant:
                    wrong_reads += 1

        trace.metrics.wrong_reads = wrong_reads
        trace.metrics.redundant_reads = redundant_reads
        return wrong_reads, redundant_reads

    def _is_redundant(self, tc: ToolCallRecord, prior_content: list[str]) -> bool:
        """Check if this tool call's content substantially overlaps with prior reads."""
        if not prior_content:
            return False

        # For chunk-based tools: check if same chunk ID was read before
        if tc.tool_name == "read_chunks":
            chunk_ids = tc.arguments.get("chunk_ids", [])
            for prior in prior_content:
                for cid in chunk_ids:
                    if cid in prior:
                        return True

        # For page-based tools: check if same pages were read
        if tc.tool_name == "read_file":
            current_content = tc.result_content
            for prior in prior_content:
                # If >80% of current content appears in a prior result
                if len(current_content) > 50:
                    overlap = sum(
                        1 for line in current_content.split("\n")
                        if line.strip() and line.strip() in prior
                    )
                    total_lines = max(1, len([l for l in current_content.split("\n") if l.strip()]))
                    if overlap / total_lines > 0.8:
                        return True

        return False

    def _is_relevant(self, question: str, final_answer: str, content: str) -> bool:
        """Use LLM to judge if retrieved content was relevant to the answer."""
        # Truncate content for the judge
        content_preview = content[:500] + ("..." if len(content) > 500 else "")

        prompt = f"""Question: {question}
Final answer given: {final_answer}

Content retrieved by a tool call:
{content_preview}

Was this retrieved content relevant to answering the question? Answer ONLY "yes" or "no"."""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text.strip().lower()
            return answer.startswith("yes")
        except Exception:
            return True  # Default to relevant on error
