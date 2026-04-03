"""AgentLib MCP server — book-domain knowledge navigation tools."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    """Load .env file from plugin data directory. Shell env takes precedence."""
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_DATA", ""),
        os.environ.get("AGENTLIB_DATA", ""),
        str(Path.home() / ".claude" / "plugins" / "agentlib"),
    ]
    for base in candidates:
        if not base:
            continue
        env_path = Path(base) / ".env"
        if env_path.exists():
            try:
                env_path.chmod(0o600)
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        if key and os.environ.get(key) is None:
                            os.environ[key] = value
            except OSError:
                pass
            return


_load_env()

import json

from fastmcp import FastMCP

from lib import storage

mcp = FastMCP("agentlib")

# ---------------------------------------------------------------------------
# Token budget constants & helpers
# ---------------------------------------------------------------------------
MAX_SUMMARY_CHARS = 80
MAX_CHAPTER_SUMMARY_CHARS = 100
MAX_CONCEPTS_PER_CHAPTER = 3
MAX_SEARCH_RESULTS = 10
MAX_MANIFEST_CHARS = 8000  # ~2000 tokens
MAX_MANIFEST_CHAPTERS = 20


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


@mcp.tool()
def browse_library() -> str:
    """List all books in the library with titles, summaries, and chapter/chunk counts."""
    catalog = storage.read_catalog()
    compact_books = []
    for b in catalog.books:
        compact_books.append({
            "id": b.id,
            "title": b.title,
            "summary": _truncate(b.summary, MAX_SUMMARY_CHARS),
            "chapters": b.chapter_count,
            "chunks": b.total_chunks,
        })
    return json.dumps({"books": compact_books})


@mcp.tool()
def open_book(book_id: str) -> str:
    """Get detailed chapter and section structure for a specific book, including summaries and concept index."""
    if not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    manifest = storage.read_manifest(book_id)
    if manifest is None:
        return json.dumps({"error": f"Manifest not found for book: {book_id}"})

    chapters = []
    for ch in manifest.chapters:
        chapters.append({
            "id": ch.id,
            "title": ch.title,
            "summary": _truncate(ch.summary, MAX_CHAPTER_SUMMARY_CHARS),
            "concepts": ch.key_concepts[:MAX_CONCEPTS_PER_CHAPTER],
            "sections": len(ch.sections),
            "chunks": sum(len(s.chunk_ids) for s in ch.sections),
        })

    compact: dict = {"book_id": manifest.book_id}

    # Truncate chapters if too many
    if len(chapters) > MAX_MANIFEST_CHAPTERS:
        compact["chapters"] = chapters[:MAX_MANIFEST_CHAPTERS]
        compact["note"] = f"Showing first {MAX_MANIFEST_CHAPTERS} of {len(chapters)} chapters"
    else:
        compact["chapters"] = chapters

    # Concept index: flat list of concept names only
    compact["concepts"] = sorted(manifest.concept_index.keys())

    result = json.dumps(compact)

    # Final safety check on total size
    if len(result) > MAX_MANIFEST_CHARS:
        # Re-truncate chapters until we fit
        while len(compact["chapters"]) > 1:
            compact["chapters"] = compact["chapters"][:len(compact["chapters"]) - 1]
            compact["note"] = f"Showing first {len(compact['chapters'])} of {len(chapters)} chapters (truncated for size)"
            result = json.dumps(compact)
            if len(result) <= MAX_MANIFEST_CHARS:
                break

    return result


@mcp.tool()
def read_chunks(book_id: str, chunk_ids: list[str]) -> str:
    """Read the full content of specific chunks by ID. Max 10 chunks per call."""
    if len(chunk_ids) > 10:
        return json.dumps({"error": "Maximum 10 chunk IDs per call."})
    chunks = storage.read_chunks(book_id, chunk_ids)
    return json.dumps(chunks, indent=2)


@mcp.tool()
def search_concepts(query: str, book_id: str | None = None) -> str:
    """Search for concepts across all books (or a specific book). Returns matching concept names with their chunk locations."""
    if book_id and not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    results = storage.search_concepts(query, book_id=book_id)

    # Flatten to concept -> chunk_ids and cap at MAX_SEARCH_RESULTS
    compact: dict = {}
    truncated = False
    for concept_key, entries in results.items():
        if len(compact) >= MAX_SEARCH_RESULTS:
            truncated = True
            break
        compact[concept_key] = [
            cid for entry in entries for cid in entry["chunks"]
        ]

    if truncated:
        compact["truncated"] = True  # type: ignore[assignment]

    return json.dumps(compact)


@mcp.tool()
def search_library(query: str) -> str:
    """Search the unified library index across ALL books and corpora. Returns matching concepts with their sources, aliases, related concepts, and pattern fingerprints."""
    lib_index = storage.read_library_index()
    query_lower = query.lower()
    results: dict = {}

    for concept, entry in lib_index.concepts.items():
        match = query_lower in concept.lower()
        if not match:
            for alias in entry.aliases:
                if query_lower in alias.lower():
                    match = True
                    break
        if not match:
            # Check related concepts for indirect match
            for related in entry.related:
                if query_lower in related.lower():
                    match = True
                    break
        if match:
            results[concept] = {
                "sources": {s.source: s.chunks for s in entry.sources},
                "aliases": entry.aliases,
                "related": entry.related,
                "patterns": entry.patterns,
            }
            if len(results) >= MAX_SEARCH_RESULTS:
                break

    return json.dumps(results)


@mcp.tool()
def explore_patterns(pattern: str) -> str:
    """Look up a pattern tag to find structurally similar concepts across the library. Use after finding a concept's patterns via search_library to discover cross-domain analogies."""
    pat_index = storage.read_pattern_index()
    pattern_lower = pattern.lower()
    results: dict = {}

    for pat_name, entries in pat_index.patterns.items():
        if pattern_lower in pat_name.lower():
            results[pat_name] = [
                {"concept": e.concept, "source": e.source, "chunks": e.chunks}
                for e in entries
            ]

    if not results:
        # List available patterns as hints
        available = sorted(pat_index.patterns.keys())[:20]
        return json.dumps({"no_match": True, "available_patterns": available})

    return json.dumps(results)


@mcp.tool()
def preview_chunks(book_id: str, chunk_ids: list[str]) -> str:
    """Preview chunk metadata (section, concepts, token count, prev/next links) WITHOUT reading full content. Use this to decide which chunks are worth reading."""
    if not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    chunk_index = storage.read_chunk_index(book_id)
    if chunk_index is None:
        return json.dumps({"error": "chunk_index.json not found — book may need re-ingestion"})

    previews: dict = {}
    for cid in chunk_ids[:20]:  # Cap at 20 previews
        if cid in chunk_index.chunks:
            previews[cid] = chunk_index.chunks[cid].to_dict()
        else:
            previews[cid] = None

    return json.dumps(previews)


if __name__ == "__main__":
    mcp.run()
