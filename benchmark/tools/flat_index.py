"""Condition B: Flat index — enriched list_files with chapter descriptions + same read_file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.tools.base import ToolResult, estimate_tokens
from benchmark.tools.baseline import BaselineToolProvider, READ_FILE_SCHEMA


ENRICHED_LIST_FILES_SCHEMA: dict[str, Any] = {
    "name": "list_files",
    "description": "List all documents with detailed chapter index including titles, page ranges, descriptions, and token estimates.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


class FlatIndexToolProvider:
    """Flat index: enriched list_files + same read_file as baseline."""

    def __init__(self, corpus_dir: Path, book_id: str, max_pages: int = 10):
        self._baseline = BaselineToolProvider(corpus_dir, book_id, max_pages)
        self._index_path = corpus_dir / "flat_index" / book_id / "index.json"
        self._index: dict[str, Any] = {}
        if self._index_path.exists():
            self._index = json.loads(self._index_path.read_text(encoding="utf-8"))

    @property
    def condition_name(self) -> str:
        return "flat_index"

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        return [ENRICHED_LIST_FILES_SCHEMA, READ_FILE_SCHEMA]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name == "list_files":
            return self._list_files_enriched()
        elif tool_name == "read_file":
            return self._baseline._read_file(
                filename=arguments["filename"],
                start_page=arguments["start_page"],
                end_page=arguments["end_page"],
            )
        raise ValueError(f"Unknown tool: {tool_name}")

    def _list_files_enriched(self) -> ToolResult:
        """Return file listing with chapter-level descriptions and token estimates."""
        content = json.dumps(self._index, indent=2)
        return ToolResult(content=content, token_estimate=estimate_tokens(content))
