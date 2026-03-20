"""Tests for the storage layer."""
# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

from lib.models import Catalog, CatalogEntry, Manifest
from lib.storage import (
    read_catalog,
    read_chunk,
    read_chunks,
    read_manifest,
    search_concepts,
    update_catalog_entry,
    write_catalog,
    write_chunk,
    write_manifest,
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
