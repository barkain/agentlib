"""Filesystem I/O layer for AgentLib data storage."""
from __future__ import annotations

import os
import re
from pathlib import Path

from lib.models import Catalog, CatalogEntry, Manifest

# Strict regex for path component validation: alphanumeric, hyphens, underscores, dots
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _validate_path_component(value: str, name: str = "id") -> None:
    """Validate that a string is safe to use as a path component.

    Rejects path separators, '..', absolute paths, and anything that
    doesn't match a conservative alphanumeric pattern.
    """
    if not value:
        raise ValueError(f"{name} must not be empty")
    if not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r}. "
            "Must start with alphanumeric and contain only alphanumeric, hyphen, underscore, or dot."
        )
    if ".." in value:
        raise ValueError(f"{name} must not contain '..'")


def _safe_join(root: Path, *parts: str) -> Path:
    """Join path components and verify the result stays under root."""
    for part in parts:
        _validate_path_component(part, name="path component")
    result = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if not str(result).startswith(str(root_resolved) + os.sep) and result != root_resolved:
        raise ValueError(f"Path escapes root directory: {result}")
    return result


def _data_root() -> Path:
    """Resolve the data root directory."""
    env = os.environ.get("AGENTLIB_DATA")
    if env:
        return Path(env)
    return Path.home() / ".agentlib" / "library"


def _books_root() -> Path:
    return _data_root() / "books"


# ---------------------------------------------------------------------------
# Catalog (L0)
# ---------------------------------------------------------------------------

def read_catalog() -> Catalog:
    """Read the library catalog. Returns empty catalog if not found."""
    path = _books_root() / "catalog.json"
    if not path.exists():
        return Catalog()
    return Catalog.from_json(path.read_text(encoding="utf-8"))


def write_catalog(catalog: Catalog) -> Path:
    """Write the library catalog to disk."""
    path = _books_root() / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.to_json(), encoding="utf-8")
    return path


def update_catalog_entry(entry: CatalogEntry) -> Catalog:
    """Add or update a single book in the catalog."""
    catalog = read_catalog()
    for i, existing in enumerate(catalog.books):
        if existing.id == entry.id:
            catalog.books[i] = entry
            write_catalog(catalog)
            return catalog
    catalog.books.append(entry)
    write_catalog(catalog)
    return catalog


# ---------------------------------------------------------------------------
# Manifest (L1)
# ---------------------------------------------------------------------------

def read_manifest(book_id: str) -> Manifest | None:
    """Read a book manifest. Returns None if not found."""
    _validate_path_component(book_id, "book_id")
    path = _safe_join(_books_root(), book_id, "manifest.json")
    if not path.exists():
        return None
    return Manifest.from_json(path.read_text(encoding="utf-8"))


def write_manifest(manifest: Manifest) -> Path:
    """Write a book manifest to disk."""
    _validate_path_component(manifest.book_id, "book_id")
    path = _safe_join(_books_root(), manifest.book_id, "manifest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json(), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Chunks (L2)
# ---------------------------------------------------------------------------

def _chunk_dir(book_id: str) -> Path:
    _validate_path_component(book_id, "book_id")
    return _safe_join(_books_root(), book_id, "chunks")


def read_chunk(book_id: str, chunk_id: str) -> str | None:
    """Read a single chunk file. Returns None if not found."""
    _validate_path_component(book_id, "book_id")
    _validate_path_component(chunk_id, "chunk_id")
    path = _safe_join(_books_root(), book_id, "chunks", f"{chunk_id}.md")
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def read_chunks(book_id: str, chunk_ids: list[str]) -> dict[str, str | None]:
    """Read multiple chunks. Returns dict of chunk_id -> content (None if missing)."""
    _validate_path_component(book_id, "book_id")
    return {cid: read_chunk(book_id, cid) for cid in chunk_ids}


def write_chunk(book_id: str, chunk_id: str, content: str) -> Path:
    """Write a single chunk file to disk."""
    _validate_path_component(book_id, "book_id")
    _validate_path_component(chunk_id, "chunk_id")
    chunk_dir = _chunk_dir(book_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    path = _safe_join(_books_root(), book_id, "chunks", f"{chunk_id}.md")
    path.write_text(content, encoding="utf-8")
    return path


def list_chunks(book_id: str) -> list[str]:
    """List all chunk IDs for a book."""
    _validate_path_component(book_id, "book_id")
    chunk_dir = _chunk_dir(book_id)
    if not chunk_dir.exists():
        return []
    return sorted(p.stem for p in chunk_dir.glob("*.md"))


def book_exists(book_id: str) -> bool:
    """Check if a book directory exists."""
    _validate_path_component(book_id, "book_id")
    return _safe_join(_books_root(), book_id).is_dir()


def book_dir(book_id: str) -> Path:
    """Return the path to a book's directory."""
    _validate_path_component(book_id, "book_id")
    return _safe_join(_books_root(), book_id)


# ---------------------------------------------------------------------------
# Concept search (Ls)
# ---------------------------------------------------------------------------

def search_concepts(query: str, book_id: str | None = None) -> dict[str, list[dict]]:
    """Search concept index across books. Substring match on concept names.

    Returns dict of concept_name -> list of {ch, sec, chunks} entries.
    If book_id is specified, search only that book.
    """
    results: dict[str, list[dict]] = {}
    query_lower = query.lower()

    if book_id:
        book_ids = [book_id]
    else:
        catalog = read_catalog()
        book_ids = [b.id for b in catalog.books]

    for bid in book_ids:
        manifest = read_manifest(bid)
        if manifest is None:
            continue
        for concept, entries in manifest.concept_index.items():
            if query_lower in concept.lower():
                key = f"{bid}:{concept}"
                results[key] = [
                    {"ch": e.ch, "sec": e.sec, "chunks": e.chunks}
                    for e in entries
                ]

    return results
