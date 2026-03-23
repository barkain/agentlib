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


# ---------------------------------------------------------------------------
# Corpus models (scientific paper collections)
# ---------------------------------------------------------------------------

@dataclass
class PaperMetadata:
    """Extracted metadata for a single paper."""
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    filename: str = ""
    page_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperMetadata:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> PaperMetadata:
        return cls.from_dict(json.loads(text))


@dataclass
class ClusterEntry:
    """One topic cluster in the corpus catalog."""
    id: str
    description: str = ""
    paper_count: int = 0
    date_range: list[str] = field(default_factory=list)
    top_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CorpusCatalog:
    """L0a -- Corpus catalog with topic clusters."""
    corpus_id: str
    corpus_title: str = ""
    paper_count: int = 0
    clusters: list[ClusterEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "corpus_title": self.corpus_title,
            "paper_count": self.paper_count,
            "clusters": [c.to_dict() for c in self.clusters],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorpusCatalog:
        clusters = [ClusterEntry.from_dict(c) for c in data.get("clusters", [])]
        return cls(
            corpus_id=data["corpus_id"],
            corpus_title=data.get("corpus_title", ""),
            paper_count=data.get("paper_count", 0),
            clusters=clusters,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> CorpusCatalog:
        return cls.from_dict(json.loads(text))


@dataclass
class PaperEntry:
    """One paper in a cluster listing (L0b)."""
    id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    keywords: list[str] = field(default_factory=list)
    abstract: str = ""
    section_count: int = 0
    chunk_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CitationContext:
    """A reference to another paper in the corpus."""
    cites: str = ""
    context: str = ""
    relationship: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CitationContext:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PaperManifest:
    """L1 -- Paper manifest (~400-800 tokens)."""
    paper_id: str
    sections: list[SectionInfo] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    citation_context: list[CitationContext] = field(default_factory=list)
    methodology_params: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "sections": [asdict(s) for s in self.sections],
            "key_findings": self.key_findings,
            "citation_context": [c.to_dict() for c in self.citation_context],
            "methodology_params": self.methodology_params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperManifest:
        sections = [SectionInfo(**s) for s in data.get("sections", [])]
        citations = [CitationContext.from_dict(c) for c in data.get("citation_context", [])]
        return cls(
            paper_id=data["paper_id"],
            sections=sections,
            key_findings=data.get("key_findings", []),
            citation_context=citations,
            methodology_params=data.get("methodology_params", {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> PaperManifest:
        return cls.from_dict(json.loads(text))


@dataclass
class CorpusConceptEntry:
    """A concept mapped across papers."""
    papers: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorpusConceptEntry:
        return cls(
            papers=data.get("papers", []),
            sections=data.get("sections", {}),
            note=data.get("note", ""),
        )


@dataclass
class CorpusConceptIndex:
    """Ls -- Cross-paper concept index."""
    corpus_id: str
    concepts: dict[str, CorpusConceptEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "concepts": {k: v.to_dict() for k, v in self.concepts.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorpusConceptIndex:
        concepts = {
            k: CorpusConceptEntry.from_dict(v)
            for k, v in data.get("concepts", {}).items()
        }
        return cls(corpus_id=data["corpus_id"], concepts=concepts)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> CorpusConceptIndex:
        return cls.from_dict(json.loads(text))
