"""LLM-as-judge scoring for answer accuracy."""
from __future__ import annotations

import json
import statistics

import anthropic  # type: ignore[reportMissingImports]

from benchmark.models import ScoreResult


class LLMJudge:
    """Score agent answers against ground truth using an LLM judge."""

    def __init__(self, model: str):
        self._client = anthropic.Anthropic()
        self._model = model

    def score_answer(
        self,
        question: str,
        reference_answer: str,
        key_facts: list[str],
        agent_answer: str,
    ) -> ScoreResult:
        """Score an agent answer. Runs judge 3 times, takes median."""
        judge_scores: list[dict[str, float]] = []

        for _ in range(3):
            score = self._call_judge(question, reference_answer, key_facts, agent_answer)
            if score:
                judge_scores.append(score)

        if not judge_scores:
            return ScoreResult()

        correctness = statistics.median(s["correctness"] for s in judge_scores)
        completeness = statistics.median(s["completeness"] for s in judge_scores)
        no_hallucination = statistics.median(s["no_hallucination"] for s in judge_scores)
        overall = 0.4 * correctness + 0.4 * completeness + 0.2 * no_hallucination

        key_fact_score = self._score_key_facts(question, key_facts, agent_answer)

        final_accuracy = (overall + key_fact_score) / 2

        return ScoreResult(
            llm_judge_correctness=round(correctness, 3),
            llm_judge_completeness=round(completeness, 3),
            llm_judge_no_hallucination=round(no_hallucination, 3),
            llm_judge_overall=round(overall, 3),
            key_fact_score=round(key_fact_score, 3),
            final_accuracy=round(final_accuracy, 3),
        )

    def _call_judge(
        self,
        question: str,
        reference_answer: str,
        key_facts: list[str],
        agent_answer: str,
    ) -> dict[str, float] | None:
        """Single judge call. Returns scores or None on failure."""
        key_facts_text = "\n".join(f"- {f}" for f in key_facts)

        prompt = f"""You are evaluating an AI assistant's answer against a reference answer.

Question: {question}
Reference answer: {reference_answer}
Key facts that must be present:
{key_facts_text}
Assistant's answer: {agent_answer}

Score on these dimensions (0.0 to 1.0 each):
1. Factual correctness: Are all stated facts correct? (0 = major errors, 1 = all correct)
2. Completeness: Are all key facts from the reference covered? (0 = none, 1 = all)
3. No hallucination: Does the answer avoid stating things not in the source? (0 = significant hallucination, 1 = none)

Respond with ONLY valid JSON:
{{"correctness": X, "completeness": X, "no_hallucination": X}}"""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=256,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            return json.loads(text)
        except Exception:
            return None

    def _score_key_facts(
        self,
        question: str,
        key_facts: list[str],
        agent_answer: str,
    ) -> float:
        """Check which key facts appear in the answer. Returns ratio."""
        if not key_facts:
            return 1.0

        facts_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(key_facts))

        prompt = f"""Question: {question}

Agent's answer: {agent_answer}

For each fact below, does the agent's answer contain or convey this fact? Reply with ONLY a JSON list of booleans.

Facts:
{facts_text}

Example response for 3 facts: [true, false, true]"""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=128,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            results = json.loads(text)
            if isinstance(results, list):
                return sum(1 for r in results if r) / len(key_facts)
        except Exception:  # noqa: S110
            return 0.0
        return 0.0
