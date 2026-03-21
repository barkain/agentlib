"""Agent executor: wraps Anthropic Messages API, handles tool-call loop, captures traces."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic  # type: ignore[reportMissingImports]

from benchmark.models import (
    QuestionDef,
    ToolCallRecord,
    Trace,
    TraceMetrics,
    Turn,
)
from benchmark.tools.base import ToolProvider


class AgentExecutor:
    """Execute a single question against a tool provider and capture a trace."""

    def __init__(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        max_tool_calls: int,
        tool_provider: ToolProvider,
        system_prompt: str,
    ):
        self._client = anthropic.Anthropic()
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_tool_calls = max_tool_calls
        self._tools = tool_provider
        self._system = system_prompt

    def run(self, question: QuestionDef) -> Trace:
        """Execute a question and return a complete trace."""
        run_id = str(uuid.uuid4())
        messages: list[dict[str, Any]] = [{"role": "user", "content": question.text}]
        turns: list[Turn] = []
        total_tool_calls = 0
        exceeded_limit = False
        final_answer = ""

        t_start = time.time()
        ts_start = datetime.now(timezone.utc).isoformat()

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=self._system,
                tools=self._tools.tool_definitions,
                messages=messages,
            )

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Parse response content
            tool_calls_in_turn: list[ToolCallRecord] = []
            text_response: str | None = None
            tool_use_blocks: list[Any] = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_use_blocks.append(block)
                    try:
                        result = self._tools.call(block.name, block.input)
                        result_content = result.content
                        result_tokens = result.token_estimate
                    except Exception as e:
                        result_content = f"Error: {e}"
                        result_tokens = 10
                    tool_calls_in_turn.append(ToolCallRecord(
                        tool_name=block.name,
                        arguments=block.input,
                        result_content=result_content,
                        result_tokens=result_tokens,
                    ))
                elif block.type == "text":
                    text_response = block.text

            turn = Turn(
                turn_number=len(turns) + 1,
                role="assistant",
                tool_calls=tool_calls_in_turn,
                text_response=text_response,
                api_input_tokens=input_tokens,
                api_output_tokens=output_tokens,
            )
            turns.append(turn)

            # Build messages for next iteration
            messages.append({"role": "assistant", "content": response.content})

            if tool_calls_in_turn:
                tool_results = []
                for tc, block in zip(tool_calls_in_turn, tool_use_blocks):
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tc.result_content,
                    })
                messages.append({"role": "user", "content": tool_results})

            total_tool_calls += len(tool_calls_in_turn)

            # Check termination
            if response.stop_reason == "end_turn":
                if text_response:
                    final_answer = text_response
                break

            if total_tool_calls >= self._max_tool_calls:
                exceeded_limit = True
                # Extract any text from last turn as answer
                if text_response:
                    final_answer = text_response
                break

            if response.stop_reason == "max_tokens":
                if text_response:
                    final_answer = text_response
                break

        t_end = time.time()
        ts_end = datetime.now(timezone.utc).isoformat()

        # If no text answer was captured, check all turns
        if not final_answer:
            for turn in reversed(turns):
                if turn.text_response:
                    final_answer = turn.text_response
                    break

        metrics = TraceMetrics(
            total_tool_calls=total_tool_calls,
            cumulative_input_tokens=sum(t.api_input_tokens for t in turns),
            total_output_tokens=sum(t.api_output_tokens for t in turns),
            wrong_reads=0,
            redundant_reads=0,
            wall_clock_seconds=round(t_end - t_start, 2),
        )

        return Trace(
            run_id=run_id,
            condition=self._tools.condition_name,
            book_id=question.book_id,
            question_id=question.id,
            question_category=question.category,
            question_text=question.text,
            model=self._model,
            temperature=self._temperature,
            timestamp_start=ts_start,
            timestamp_end=ts_end,
            turns=turns,
            final_answer=final_answer,
            metrics=metrics,
            scoring=None,
            exceeded_limit=exceeded_limit,
        )


# Pricing for cost estimation (per token)
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20260320": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
}
DEFAULT_PRICING = {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}


def estimate_cost(trace: Trace) -> float:
    """Estimate USD cost from token counts."""
    rates = PRICING.get(trace.model, DEFAULT_PRICING)
    return (
        trace.metrics.cumulative_input_tokens * rates["input"]
        + trace.metrics.total_output_tokens * rates["output"]
    )
