"""Shared data models for the benchmark suite."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class QuestionDef:
    """A single benchmark question."""
    id: str
    book_id: str
    category: str  # pinpoint | structural | cross_reference | exploratory | needle_in_haystack
    text: str
    difficulty: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestionDef:
        return cls(**data)


@dataclass
class GroundTruth:
    """Reference answer for scoring."""
    question_id: str
    reference_answer: str
    key_facts: list[str] = field(default_factory=list)
    source_location: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundTruth:
        return cls(**data)


@dataclass
class ToolCallRecord:
    """Record of a single tool invocation."""
    tool_name: str
    arguments: dict[str, Any]
    result_content: str
    result_tokens: int = 0
    result_relevant: bool | None = None  # Filled post-hoc

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallRecord:
        return cls(**data)


@dataclass
class Turn:
    """One assistant turn (may contain multiple tool calls)."""
    turn_number: int
    role: str = "assistant"
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    text_response: str | None = None
    api_input_tokens: int = 0
    api_output_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Turn:
        tool_calls = [ToolCallRecord.from_dict(tc) for tc in data.pop("tool_calls", [])]
        return cls(tool_calls=tool_calls, **data)


@dataclass
class TraceMetrics:
    """Computed metrics from a trace."""
    total_tool_calls: int = 0
    cumulative_input_tokens: int = 0
    total_output_tokens: int = 0
    wrong_reads: int = 0
    redundant_reads: int = 0
    wall_clock_seconds: float = 0.0
    concept_search_hits: int = 0
    concept_search_misses: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceMetrics:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ScoreResult:
    """Output of the scoring pipeline."""
    llm_judge_correctness: float = 0.0
    llm_judge_completeness: float = 0.0
    llm_judge_no_hallucination: float = 0.0
    llm_judge_overall: float = 0.0
    key_fact_score: float = 0.0
    final_accuracy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreResult:
        return cls(**data)


@dataclass
class Trace:
    """Complete record of one benchmark execution."""
    run_id: str
    condition: str  # "baseline" | "flat_index" | "agentlib"
    book_id: str
    question_id: str
    question_category: str
    question_text: str
    model: str
    temperature: float
    timestamp_start: str
    timestamp_end: str
    turns: list[Turn] = field(default_factory=list)
    final_answer: str = ""
    metrics: TraceMetrics = field(default_factory=TraceMetrics)
    scoring: ScoreResult | None = None
    exceeded_limit: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = {
            "run_id": self.run_id,
            "condition": self.condition,
            "book_id": self.book_id,
            "question_id": self.question_id,
            "question_category": self.question_category,
            "question_text": self.question_text,
            "model": self.model,
            "temperature": self.temperature,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "turns": [t.to_dict() for t in self.turns],
            "final_answer": self.final_answer,
            "metrics": self.metrics.to_dict(),
            "scoring": self.scoring.to_dict() if self.scoring else None,
            "exceeded_limit": self.exceeded_limit,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        turns = [Turn.from_dict(t) for t in data.pop("turns", [])]
        metrics = TraceMetrics.from_dict(data.pop("metrics", {}))
        scoring_data = data.pop("scoring", None)
        scoring = ScoreResult.from_dict(scoring_data) if scoring_data else None
        return cls(turns=turns, metrics=metrics, scoring=scoring, **data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Trace:
        return cls.from_dict(json.loads(text))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Trace:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def load_questions(questions_dir: Path, book_id: str | None = None) -> list[QuestionDef]:
    """Load questions from JSON files in the questions directory."""
    questions_dir = Path(questions_dir)
    questions: list[QuestionDef] = []
    for path in sorted(questions_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if book_id and data.get("book_id") != book_id:
            continue
        for q in data.get("questions", []):
            q["book_id"] = data["book_id"]
            questions.append(QuestionDef.from_dict(q))
    return questions


def load_ground_truths(gt_dir: Path) -> dict[str, GroundTruth]:
    """Load ground truths, keyed by question_id."""
    gt_dir = Path(gt_dir)
    truths: dict[str, GroundTruth] = {}
    for path in sorted(gt_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for gt in data.get("answers", []):
            truths[gt["question_id"]] = GroundTruth.from_dict(gt)
    return truths
