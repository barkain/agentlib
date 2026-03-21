---
name: agentlib-ingest-book
description: Ingest a book (PDF or EPUB) into the AgentLib library
argument-hint: "<path-to-pdf-or-epub> [--book-id <id>]"
arguments:
  - name: file_path
    description: Path to the PDF or EPUB file to ingest
    required: true
  - name: book_id
    description: Optional custom book identifier (default: derived from filename)
    required: false
---

Ingest the book at `$ARGUMENTS.file_path` into the AgentLib library.

Run the ingestion pipeline:
```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python preprocessing/books.py "$ARGUMENTS.file_path" ${ARGUMENTS.book_id:+--book-id "$ARGUMENTS.book_id"}
```

This will:
1. Parse the PDF/EPUB to extract chapter/section structure
2. Chunk the content into 300-500 token segments
3. Summarise each chapter using Claude Haiku
4. Build a concept index for fast search
5. Write manifest and update the library catalog

After ingestion, the book's content will be available through the AgentLib MCP tools:
- `browse_library` to see it in the catalog
- `open_book` to view its chapter structure
- `read_chunks` to access specific content
- `search_concepts` to find concepts across the library
