"""Condition A: Raw file access — list_files + read_file (blind navigation)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.tools.base import ToolResult, estimate_tokens


LIST_FILES_SCHEMA: dict[str, Any] = {
    "name": "list_files",
    "description": "List all documents in the library with their page counts.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

READ_FILE_SCHEMA: dict[str, Any] = {
    "name": "read_file",
    "description": "Read pages from a document. Returns the raw text content of the specified page range.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The document filename (from list_files).",
            },
            "start_page": {
                "type": "integer",
                "description": "First page to read (1-indexed).",
            },
            "end_page": {
                "type": "integer",
                "description": "Last page to read (inclusive). Max 10 pages per call.",
            },
        },
        "required": ["filename", "start_page", "end_page"],
    },
}


class BaselineToolProvider:
    """Raw file access. Two tools: list_files, read_file."""

    def __init__(self, corpus_dir: Path, book_id: str, max_pages: int = 10):
        self._pages_dir = corpus_dir / "baseline" / book_id
        self._max_pages = max_pages
        self._page_files: list[Path] = []
        self._load_pages()

    def _load_pages(self) -> None:
        """Load sorted list of page text files."""
        if self._pages_dir.exists():
            self._page_files = sorted(self._pages_dir.glob("page_*.txt"))

    @property
    def condition_name(self) -> str:
        return "baseline"

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        return [LIST_FILES_SCHEMA, READ_FILE_SCHEMA]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name == "list_files":
            return self._list_files()
        elif tool_name == "read_file":
            return self._read_file(
                filename=arguments["filename"],
                start_page=arguments["start_page"],
                end_page=arguments["end_page"],
            )
        raise ValueError(f"Unknown tool: {tool_name}")

    def _list_files(self) -> ToolResult:
        """List available documents with page counts."""
        book_id = self._pages_dir.name
        total_pages = len(self._page_files)
        total_size_kb = sum(p.stat().st_size for p in self._page_files) // 1024 if self._page_files else 0
        result = json.dumps([{
            "filename": book_id,
            "page_count": total_pages,
            "file_size_kb": total_size_kb,
        }], indent=2)
        return ToolResult(content=result, token_estimate=estimate_tokens(result))

    def _read_file(self, filename: str, start_page: int, end_page: int) -> ToolResult:
        """Read pages from a document. Clamps to max_pages."""
        # Clamp range
        end_page = min(end_page, start_page + self._max_pages - 1)
        end_page = min(end_page, len(self._page_files))
        start_page = max(1, start_page)

        if start_page > len(self._page_files):
            content = json.dumps({"error": f"Start page {start_page} exceeds document length ({len(self._page_files)} pages)"})
            return ToolResult(content=content, token_estimate=estimate_tokens(content))

        parts: list[str] = []
        for page_num in range(start_page, end_page + 1):
            page_file = self._pages_dir / f"page_{page_num:03d}.txt"
            if page_file.exists():
                text = page_file.read_text(encoding="utf-8")
                parts.append(f"--- Page {page_num} ---\n{text}")
            else:
                parts.append(f"--- Page {page_num} ---\n[Page not available]")

        content = "\n\n".join(parts)
        return ToolResult(content=content, token_estimate=estimate_tokens(content))
