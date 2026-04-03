"""Tests for the storage layer."""
# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

from lib.models import (
    Catalog,
    CatalogEntry,
    ChunkIndex,
    ChunkIndexEntry,
    ConceptEntry,
    LibraryConceptEntry,
    LibraryConceptSource,
    LibraryIndex,
    Manifest,
    PatternEntry,
    PatternIndex,
)
from lib.storage import (
    read_catalog,
    read_chunk,
    read_chunk_index,
    read_chunks,
    read_library_index,
    read_manifest,
    read_pattern_index,
    search_concepts,
    update_catalog_entry,
    write_catalog,
    write_chunk,
    write_chunk_index,
    write_library_index,
    write_manifest,
    write_pattern_index,
    list_chunks,
    book_exists,
)


class TestCatalog:
    def test_read_empty_catalog(self, tmp_data_dir: Path) -> None:
        catalog = read_catalog()
        assert catalog.books == []

    def test_write_and_read_catalog(self, tmp_data_dir: Path, sample_catalog_entry: CatalogEntry) -> None:
        catalog = Catalog(books=[sample_catalog_entry])
        write_catalog(catalog)

        loaded = read_catalog()
        assert len(loaded.books) == 1
        assert loaded.books[0].id == "test-book"
        assert loaded.books[0].title == "Test Book"

    def test_update_catalog_entry_add(self, tmp_data_dir: Path, sample_catalog_entry: CatalogEntry) -> None:
        catalog = update_catalog_entry(sample_catalog_entry)
        assert len(catalog.books) == 1
        assert catalog.books[0].id == "test-book"

    def test_update_catalog_entry_replace(self, tmp_data_dir: Path, sample_catalog_entry: CatalogEntry) -> None:
        update_catalog_entry(sample_catalog_entry)

        updated = CatalogEntry(id="test-book", title="Updated Title")
        catalog = update_catalog_entry(updated)
        assert len(catalog.books) == 1
        assert catalog.books[0].title == "Updated Title"


class TestManifest:
    def test_read_nonexistent(self, tmp_data_dir: Path) -> None:
        assert read_manifest("nonexistent") is None

    def test_write_and_read(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        write_manifest(sample_manifest)

        loaded = read_manifest("test-book")
        assert loaded is not None
        assert loaded.book_id == "test-book"
        assert len(loaded.chapters) == 2
        assert loaded.chapters[0].title == "Introduction"
        assert "unit testing" in loaded.concept_index


class TestChunks:
    def test_read_nonexistent(self, tmp_data_dir: Path) -> None:
        assert read_chunk("test-book", "ch01-001") is None

    def test_write_and_read(self, tmp_data_dir: Path, sample_chunk_content: str) -> None:
        write_chunk("test-book", "ch01-s01-001", sample_chunk_content)

        content = read_chunk("test-book", "ch01-s01-001")
        assert content is not None
        assert "chunk_id: ch01-s01-001" in content

    def test_read_multiple(self, tmp_data_dir: Path) -> None:
        write_chunk("test-book", "ch01-001", "Chunk 1")
        write_chunk("test-book", "ch01-002", "Chunk 2")

        result = read_chunks("test-book", ["ch01-001", "ch01-002", "ch01-999"])
        assert result["ch01-001"] == "Chunk 1"
        assert result["ch01-002"] == "Chunk 2"
        assert result["ch01-999"] is None

    def test_list_chunks(self, tmp_data_dir: Path) -> None:
        write_chunk("test-book", "ch01-001", "A")
        write_chunk("test-book", "ch01-002", "B")

        chunks = list_chunks("test-book")
        assert chunks == ["ch01-001", "ch01-002"]

    def test_list_chunks_empty(self, tmp_data_dir: Path) -> None:
        assert list_chunks("nonexistent") == []

    def test_book_exists(self, tmp_data_dir: Path) -> None:
        assert not book_exists("test-book")
        write_chunk("test-book", "ch01-001", "content")
        assert book_exists("test-book")


class TestSearchConcepts:
    def test_search_finds_match(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        write_manifest(sample_manifest)
        update_catalog_entry(CatalogEntry(id="test-book", title="Test"))

        results = search_concepts("unit testing")
        assert len(results) > 0
        assert any("unit testing" in k for k in results)

    def test_search_case_insensitive(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        write_manifest(sample_manifest)
        update_catalog_entry(CatalogEntry(id="test-book", title="Test"))

        results = search_concepts("MOCKING")
        assert len(results) > 0

    def test_search_no_match(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        write_manifest(sample_manifest)
        update_catalog_entry(CatalogEntry(id="test-book", title="Test"))

        results = search_concepts("nonexistent concept xyz")
        assert len(results) == 0

    def test_search_specific_book(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        write_manifest(sample_manifest)

        results = search_concepts("mocking", book_id="test-book")
        assert len(results) > 0

    def test_search_by_alias(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        """Searching 'RAG' should find 'retrieval augmented generation' via alias."""
        write_manifest(sample_manifest)
        update_catalog_entry(CatalogEntry(id="test-book", title="Test"))

        results = search_concepts("RAG")
        assert len(results) > 0
        assert any("retrieval augmented generation" in k for k in results)

    def test_backward_compat_no_aliases(self, tmp_data_dir: Path) -> None:
        """Manifests without aliases field should deserialize cleanly."""
        manifest = Manifest(
            book_id="old-book",
            chapters=[],
            concept_index={
                "testing": [ConceptEntry(ch="ch01", sec="ch01-s01", chunks=["ch01-s01-001"])],
            },
        )
        write_manifest(manifest)
        loaded = read_manifest("old-book")
        assert loaded is not None
        assert loaded.concept_index["testing"][0].aliases == []
        assert loaded.concept_index["testing"][0].patterns == []


class TestChunkIndex:
    def test_write_and_read(self, tmp_data_dir: Path) -> None:
        chunk_index = ChunkIndex(
            book_id="test-book",
            chunks={
                "ch01-s01-001": ChunkIndexEntry(
                    section="Intro > Getting Started",
                    concepts=["unit testing"],
                    tokens=420,
                    prev=None,
                    next="ch01-s01-002",
                ),
                "ch01-s01-002": ChunkIndexEntry(
                    section="Intro > Getting Started",
                    concepts=["fixtures"],
                    tokens=380,
                    prev="ch01-s01-001",
                    next=None,
                ),
            },
        )
        write_chunk_index("test-book", chunk_index)

        loaded = read_chunk_index("test-book")
        assert loaded is not None
        assert len(loaded.chunks) == 2
        assert loaded.chunks["ch01-s01-001"].next == "ch01-s01-002"
        assert loaded.chunks["ch01-s01-002"].prev == "ch01-s01-001"
        assert loaded.chunks["ch01-s01-001"].concepts == ["unit testing"]
        assert loaded.chunks["ch01-s01-001"].tokens == 420

    def test_read_nonexistent(self, tmp_data_dir: Path) -> None:
        assert read_chunk_index("nonexistent") is None


class TestLibraryIndex:
    def test_read_empty(self, tmp_data_dir: Path) -> None:
        lib_index = read_library_index()
        assert lib_index.concepts == {}

    def test_write_and_read(self, tmp_data_dir: Path) -> None:
        lib_index = LibraryIndex(concepts={
            "OAuth 2.0": LibraryConceptEntry(
                sources=[
                    LibraryConceptSource(source="book:api-security", chunks=["ch03-s01-001"]),
                    LibraryConceptSource(source="book:web-auth", chunks=["ch07-s02-004"]),
                ],
                aliases=["OAuth", "OAuth2"],
                related=["JWT", "access tokens"],
                patterns=["credential-cycling", "time-bounded-trust"],
            ),
        })
        write_library_index(lib_index)

        loaded = read_library_index()
        assert "OAuth 2.0" in loaded.concepts
        entry = loaded.concepts["OAuth 2.0"]
        assert len(entry.sources) == 2
        assert entry.sources[0].source == "book:api-security"
        assert entry.aliases == ["OAuth", "OAuth2"]
        assert entry.related == ["JWT", "access tokens"]
        assert entry.patterns == ["credential-cycling", "time-bounded-trust"]


class TestPatternIndex:
    def test_read_empty(self, tmp_data_dir: Path) -> None:
        pat_index = read_pattern_index()
        assert pat_index.patterns == {}

    def test_write_and_read(self, tmp_data_dir: Path) -> None:
        pat_index = PatternIndex(patterns={
            "credential-cycling": [
                PatternEntry(concept="OAuth 2.0", source="book:api-security", chunks=["ch03-001"]),
                PatternEntry(concept="TLS cert renewal", source="book:tls-guide", chunks=["ch08-003"]),
            ],
        })
        write_pattern_index(pat_index)

        loaded = read_pattern_index()
        assert "credential-cycling" in loaded.patterns
        entries = loaded.patterns["credential-cycling"]
        assert len(entries) == 2
        assert entries[0].concept == "OAuth 2.0"
        assert entries[1].source == "book:tls-guide"


