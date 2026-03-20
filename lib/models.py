"""Data models for AgentLib knowledge navigation system."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ChunkMeta:
    """YAML frontmatter metadata for a chunk file."""
    chunk_id: str
    source_id: str
    section: str
    prev: str | None = None
    next: str | None = None
    related: list[str] = field(default_factory=list)
    token_count: int = 0


@dataclass
class CatalogEntry:
    """L0 catalog entry — one per book (~50 tokens)."""
    id: str
    title: str
    domain_tags: list[str] = field(default_factory=list)
    summary: str = ""
    chapter_count: int = 0
    total_chunks: int = 0


@dataclass
class Catalog:
    """L0 — Library catalog (all books)."""
    books: list[CatalogEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"books": [asdict(b) for b in self.books]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        return cls(books=[CatalogEntry(**b) for b in data.get("books", [])])

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Catalog:
        return cls.from_dict(json.loads(text))


@dataclass
class SectionInfo:
    """Section within a chapter in the manifest."""
    id: str
    title: str
    summary: str = ""
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ChapterInfo:
    """Chapter in the manifest."""
    id: str
    title: str
    summary: str = ""
    key_concepts: list[str] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)


@dataclass
class ConceptEntry:
    """Single concept in the concept index."""
    ch: str
    sec: str
    chunks: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    """L1 — Book manifest (~200-500 tokens)."""
    book_id: str
    chapters: list[ChapterInfo] = field(default_factory=list)
    concept_index: dict[str, list[ConceptEntry]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"book_id": self.book_id}
        result["chapters"] = []
        for ch in self.chapters:
            ch_dict: dict[str, Any] = {
                "id": ch.id,
                "title": ch.title,
                "summary": ch.summary,
                "key_concepts": ch.key_concepts,
                "sections": [asdict(s) for s in ch.sections],
            }
            result["chapters"].append(ch_dict)
        result["concept_index"] = {
            k: [asdict(e) for e in v] for k, v in self.concept_index.items()
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        chapters = []
        for ch_data in data.get("chapters", []):
            sections = [SectionInfo(**s) for s in ch_data.get("sections", [])]
            chapters.append(ChapterInfo(
                id=ch_data["id"],
                title=ch_data["title"],
                summary=ch_data.get("summary", ""),
                key_concepts=ch_data.get("key_concepts", []),
                sections=sections,
            ))
        concept_index = {
            k: [ConceptEntry(**e) for e in v]
            for k, v in data.get("concept_index", {}).items()
        }
        return cls(
            book_id=data["book_id"],
            chapters=chapters,
            concept_index=concept_index,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Manifest:
        return cls.from_dict(json.loads(text))


@dataclass
class ParsedSection:
    """Output of the parser — a section of parsed text."""
    chapter_id: str
    chapter_title: str
    section_id: str
    section_title: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
