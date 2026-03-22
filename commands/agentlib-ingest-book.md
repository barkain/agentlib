---
description: Ingest a book (PDF or EPUB) into the AgentLib library
argument-hint: "<path-to-pdf-or-epub> [--book-id <id>]"
---

Ingest the specified book into the AgentLib library.

Parse the arguments from `$ARGUMENTS` (raw string). The first positional arg is the file path; an optional `--book-id <id>` flag may follow.

Run the ingestion pipeline:
```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python preprocessing/books.py $ARGUMENTS
```

This will:
1. Parse the PDF/EPUB to extract chapter/section structure
2. Chunk the content into 300-500 token segments
3. Summarise each chapter using the configured LLM provider
4. Build a concept index for fast search
5. Write manifest and update the library catalog

After ingestion, the book is available in the library. The agent navigates it via the `agentlib:knowledge` skill by reading catalog.json, manifest.compact.json, concepts.json, and chunks/*.md
