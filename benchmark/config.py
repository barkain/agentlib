"""Benchmark configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BookConfig:
    """Configuration for a single book in the corpus."""
    id: str
    raw_path: Path
    format: str  # "pdf" | "epub"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BookConfig:
        return cls(id=data["id"], raw_path=Path(data["raw"]), format=data["format"])


@dataclass
class BenchmarkConfig:
    """Top-level benchmark configuration."""
    model: str = "claude-sonnet-4-20260320"
    temperature: float = 0.0
    max_tokens: int = 4096
    max_tool_calls: int = 15
    trials: int = 3
    scoring_model: str = "claude-sonnet-4-20260320"
    corpus_dir: Path = field(default_factory=lambda: Path("benchmark/corpus"))
    questions_dir: Path = field(default_factory=lambda: Path("benchmark/questions"))
    ground_truth_dir: Path = field(default_factory=lambda: Path("benchmark/ground_truth"))
    results_dir: Path = field(default_factory=lambda: Path("benchmark/results"))
    agentlib_data_dir: Path = field(default_factory=lambda: Path("benchmark/corpus/agentlib"))
    baseline_max_pages: int = 10
    budget_limit_usd: float | None = None
    books: list[BookConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkConfig:
        books = [BookConfig.from_dict(b) for b in data.get("corpus", {}).get("books", [])]
        return cls(
            model=data.get("model", cls.model),
            temperature=data.get("temperature", cls.temperature),
            max_tokens=data.get("max_tokens", cls.max_tokens),
            max_tool_calls=data.get("max_tool_calls_per_question", cls.max_tool_calls),
            trials=data.get("trials_per_condition", cls.trials),
            scoring_model=data.get("scoring_model", cls.scoring_model),
            corpus_dir=Path(data.get("corpus", {}).get("dir", "benchmark/corpus")),
            questions_dir=Path(data.get("questions_dir", "benchmark/questions")),
            ground_truth_dir=Path(data.get("ground_truth_dir", "benchmark/ground_truth")),
            results_dir=Path(data.get("results_dir", "benchmark/results")),
            agentlib_data_dir=Path(data.get("agentlib", {}).get("data_dir", "benchmark/corpus/agentlib")),
            baseline_max_pages=data.get("baseline", {}).get("max_pages_per_read", 10),
            budget_limit_usd=data.get("ci", {}).get("budget_limit_usd"),
            books=books,
        )


def load_config(path: Path | str = "benchmark/config.yaml") -> BenchmarkConfig:
    """Load benchmark configuration from YAML file."""
    path = Path(path)
    if not path.exists():
        return BenchmarkConfig()
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return BenchmarkConfig.from_dict(data)
