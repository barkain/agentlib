"""Filesystem I/O layer for AgentLib data storage."""
from __future__ import annotations

import os
import re
from pathlib import Path

from lib.models import (
    Catalog,
    CatalogEntry,
    CorpusCatalog,
    CorpusConceptIndex,
    Manifest,
    PaperManifest,
    PaperMetadata,
)

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
    """Resolve the data root directory.

    Falls back to ``~/.claude/plugins/agentlib/library`` when ``AGENTLIB_DATA``
    is unset, empty, or not an absolute path.
    """
    env = os.environ.get("AGENTLIB_DATA", "").strip()
    if env and Path(env).is_absolute():
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "agentlib" / "library"


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
    """Search concept index across books. Substring match on concept names and aliases.

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
            match = query_lower in concept.lower()
            # Check aliases on entries
            if not match:
                for entry in entries:
                    for alias in getattr(entry, "aliases", []):
                        if query_lower in alias.lower():
                            match = True
                            break
                    if match:
                        break
            if match:
                key = f"{bid}:{concept}"
                results[key] = [
                    {"ch": e.ch, "sec": e.sec, "chunks": e.chunks}
                    for e in entries
                ]

    return results


# ---------------------------------------------------------------------------
# Zero-server mode: compact files for file-based navigation
# ---------------------------------------------------------------------------

def write_compact_manifest(manifest: Manifest) -> Path:
    """Write a compact manifest optimized for agent navigation (~500-2k tokens)."""
    import json

    _validate_path_component(manifest.book_id, "book_id")
    compact: dict = {
        "book_id": manifest.book_id,
        "chapters": [],
        "concepts": sorted(manifest.concept_index.keys()),
    }
    for ch in manifest.chapters:
        compact["chapters"].append({
            "id": ch.id,
            "title": ch.title,
            "summary": ch.summary[:100] + "..." if len(ch.summary) > 100 else ch.summary,
            "concepts": ch.key_concepts[:3],
            "sections": [
                {"id": s.id, "title": s.title, "chunks": len(s.chunk_ids)}
                for s in ch.sections
            ],
        })

    path = _safe_join(_books_root(), manifest.book_id, "manifest.compact.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(compact, indent=2), encoding="utf-8")
    return path


def write_concept_index(book_id: str, concept_index: dict) -> Path:
    """Write a flat concept -> chunk_ids lookup file."""
    import json

    _validate_path_component(book_id, "book_id")
    flat: dict[str, list[str]] = {}
    for concept, entries in concept_index.items():
        chunk_ids: list[str] = []
        for entry in entries:
            # Duck-type: callers pass ConceptEntry objects (with .chunks attr)
            # or dicts (from deserialized JSON). Normalizing callers is out of
            # scope for this PR.
            if hasattr(entry, "chunks"):
                chunk_ids.extend(entry.chunks)
            elif isinstance(entry, dict):
                chunk_ids.extend(entry.get("chunks", []))
        flat[concept] = chunk_ids

    # Filter out concepts with no chunks
    flat = {k: v for k, v in flat.items() if v}

    path = _safe_join(_books_root(), book_id, "concepts.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(flat, indent=2), encoding="utf-8")
    return path


def write_navigation_md() -> Path:
    """Write NAVIGATION.md in the library root with current library listing."""
    import json as _json  # noqa: F811 — local import to avoid top-level json dep

    catalog = read_catalog()
    book_lines = []
    for b in catalog.books:
        book_lines.append(
            f"- **{b.title}** (`{b.id}`) -- {b.chapter_count} chapters, "
            f"{b.total_chunks} chunks"
        )

    books_section = "\n".join(book_lines) if book_lines else "_No books ingested yet._"

    # Build corpus section
    corpus_lines: list[str] = []
    corpus_root = _corpus_root()
    if corpus_root.exists():
        for cdir in sorted(corpus_root.iterdir()):
            cat_path = cdir / "corpus_catalog.json"
            if cat_path.exists():
                try:
                    cat_data = _json.loads(cat_path.read_text(encoding="utf-8"))
                    title = cat_data.get("corpus_title", cdir.name)
                    pc = cat_data.get("paper_count", 0)
                    nc = len(cat_data.get("clusters", []))
                    corpus_lines.append(
                        f"- **{title}** (`{cdir.name}`) -- {pc} papers, {nc} clusters\n"
                        f"  Navigate: `corpus/{cdir.name}/corpus_catalog.json`"
                    )
                except (ValueError, OSError):
                    pass

    corpus_section = "\n".join(corpus_lines) if corpus_lines else "_No corpora ingested yet._"

    content = (
        "# AgentLib Library\n"
        "\n"
        "This directory contains preprocessed books and paper corpora for efficient navigation.\n"
        "Read this file to understand the structure, then navigate using standard file tools.\n"
        "\n"
        "## How to navigate\n"
        "\n"
        "### Books -- Quick path (know what you need):\n"
        "1. Read `books/{book-id}/concepts.json` -- find chunk IDs for your concept\n"
        "2. Read `books/{book-id}/chunks/{chunk-id}.md` -- get the content\n"
        "\n"
        "### Books -- Exploration path (browsing):\n"
        "1. Read `books/catalog.json` -- see all available books (~50 tokens/book)\n"
        "2. Read `books/{book-id}/manifest.compact.json` -- see chapters, summaries, concepts (~500-2k tokens)\n"
        "3. Read `books/{book-id}/chunks/{chunk-id}.md` -- get specific content (~300-500 tokens)\n"
        "\n"
        "### Corpora -- Paper collections:\n"
        "1. Read `corpus/{corpus-id}/corpus_catalog.json` -- see topic clusters\n"
        "2. Read `corpus/{corpus-id}/clusters/{cluster-id}.json` -- see papers with abstracts\n"
        "3. Read `corpus/{corpus-id}/papers/{paper-id}/manifest.compact.json` -- paper structure\n"
        "4. Read `corpus/{corpus-id}/papers/{paper-id}/chunks/{chunk-id}.md` -- paper content\n"
        "5. Read `corpus/{corpus-id}/concept_index.json` -- cross-paper concept search\n"
        "\n"
        "## Token budget\n"
        "- catalog.json: ~50 tokens per book\n"
        "- manifest.compact.json: ~500-2000 tokens per book\n"
        "- Each chunk: ~300-500 tokens\n"
        "- concepts.json: ~200-500 tokens\n"
        "- corpus_catalog.json: ~500-800 tokens\n"
        "- concept_index.json: ~500-1500 tokens\n"
        "\n"
        "## Rules\n"
        "- NEVER read the full manifest.json -- use manifest.compact.json instead\n"
        "- NEVER read all chunks -- use concepts.json or manifest to find the right ones\n"
        "- Max 10 chunks per question -- if you need more, refine your search\n"
        "\n"
        "## Current library\n"
        "\n"
        "### Books\n"
        f"{books_section}\n"
        "\n"
        "### Corpora\n"
        f"{corpus_section}\n"
    )

    path = _data_root() / "NAVIGATION.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Corpus storage (scientific paper collections)
# ---------------------------------------------------------------------------

def _corpus_root() -> Path:
    return _data_root() / "corpus"


def _corpus_dir(corpus_id: str) -> Path:
    _validate_path_component(corpus_id, "corpus_id")
    return _safe_join(_corpus_root(), corpus_id)


def corpus_exists(corpus_id: str) -> bool:
    """Check if a corpus directory exists."""
    _validate_path_component(corpus_id, "corpus_id")
    return _corpus_dir(corpus_id).is_dir()


def list_corpus_papers(corpus_id: str) -> list[str]:
    """List all paper IDs in a corpus."""
    papers_dir = _safe_join(_corpus_dir(corpus_id), "papers")
    if not papers_dir.exists():
        return []
    return sorted(d.name for d in papers_dir.iterdir() if d.is_dir())


# --- L0a: Corpus Catalog ---

def read_corpus_catalog(corpus_id: str) -> CorpusCatalog | None:
    """Read corpus_catalog.json. Returns None if not found."""
    path = _safe_join(_corpus_dir(corpus_id), "corpus_catalog.json")
    if not path.exists():
        return None
    return CorpusCatalog.from_json(path.read_text(encoding="utf-8"))


def write_corpus_catalog(catalog: CorpusCatalog) -> Path:
    """Write corpus_catalog.json to disk."""
    import json
    path = _safe_join(_corpus_dir(catalog.corpus_id), "corpus_catalog.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog.to_dict(), indent=2), encoding="utf-8")
    return path


# --- L0b: Cluster Paper Lists ---

def write_cluster_list(corpus_id: str, cluster_id: str, papers_data: list[dict]) -> Path:
    """Write clusters/{cluster_id}.json."""
    import json
    _validate_path_component(cluster_id, "cluster_id")
    path = _safe_join(_corpus_dir(corpus_id), "clusters", f"{cluster_id}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"cluster_id": cluster_id, "papers": papers_data}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# --- Paper Metadata ---

def read_paper_metadata(corpus_id: str, paper_id: str) -> PaperMetadata | None:
    """Read papers/{paper_id}/paper.json."""
    _validate_path_component(paper_id, "paper_id")
    path = _safe_join(_corpus_dir(corpus_id), "papers", paper_id, "paper.json")
    if not path.exists():
        return None
    return PaperMetadata.from_json(path.read_text(encoding="utf-8"))


def find_paper_by_filename(corpus_id: str, filename: str) -> PaperMetadata | None:
    """Find cached paper metadata by original filename."""
    papers_dir = _safe_join(_corpus_dir(corpus_id), "papers")
    if not papers_dir.exists():
        return None
    for paper_dir in papers_dir.iterdir():
        if paper_dir.is_dir():
            meta = read_paper_metadata(corpus_id, paper_dir.name)
            if meta and meta.filename == filename:
                return meta
    return None


def write_paper_metadata(corpus_id: str, metadata: PaperMetadata) -> Path:
    """Write papers/{paper_id}/paper.json."""
    import json
    _validate_path_component(metadata.paper_id, "paper_id")
    path = _safe_join(
        _corpus_dir(corpus_id), "papers", metadata.paper_id, "paper.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
    return path


# --- Paper Manifest (L1) ---

def read_paper_manifest(corpus_id: str, paper_id: str) -> PaperManifest | None:
    """Read papers/{paper_id}/manifest.compact.json."""
    _validate_path_component(paper_id, "paper_id")
    path = _safe_join(
        _corpus_dir(corpus_id), "papers", paper_id, "manifest.compact.json",
    )
    if not path.exists():
        return None
    return PaperManifest.from_json(path.read_text(encoding="utf-8"))


def write_paper_manifest(corpus_id: str, manifest: PaperManifest) -> Path:
    """Write papers/{paper_id}/manifest.compact.json."""
    import json
    _validate_path_component(manifest.paper_id, "paper_id")
    path = _safe_join(
        _corpus_dir(corpus_id), "papers", manifest.paper_id, "manifest.compact.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return path


# --- Paper Chunks (L2) ---

def write_paper_chunk(corpus_id: str, paper_id: str, chunk_id: str, content: str) -> Path:
    """Write papers/{paper_id}/chunks/{chunk_id}.md."""
    _validate_path_component(paper_id, "paper_id")
    _validate_path_component(chunk_id, "chunk_id")
    path = _safe_join(
        _corpus_dir(corpus_id), "papers", paper_id, "chunks", f"{chunk_id}.md",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_paper_chunk(corpus_id: str, paper_id: str, chunk_id: str) -> str | None:
    """Read papers/{paper_id}/chunks/{chunk_id}.md."""
    _validate_path_component(paper_id, "paper_id")
    _validate_path_component(chunk_id, "chunk_id")
    path = _safe_join(
        _corpus_dir(corpus_id), "papers", paper_id, "chunks", f"{chunk_id}.md",
    )
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def list_paper_chunks(corpus_id: str, paper_id: str) -> list[str]:
    """List all chunk IDs for a paper."""
    _validate_path_component(paper_id, "paper_id")
    chunks_dir = _safe_join(
        _corpus_dir(corpus_id), "papers", paper_id, "chunks",
    )
    if not chunks_dir.exists():
        return []
    return sorted(p.stem for p in chunks_dir.glob("*.md"))


# --- Corpus Concept Index (Ls) ---

def read_corpus_concept_index(corpus_id: str) -> CorpusConceptIndex | None:
    """Read concept_index.json."""
    path = _safe_join(_corpus_dir(corpus_id), "concept_index.json")
    if not path.exists():
        return None
    return CorpusConceptIndex.from_json(path.read_text(encoding="utf-8"))


def write_corpus_concept_index(corpus_id: str, index: CorpusConceptIndex) -> Path:
    """Write concept_index.json."""
    import json
    path = _safe_join(_corpus_dir(corpus_id), "concept_index.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")
    return path
