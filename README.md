# AgentLib

Agentic Knowledge Navigation System — enables AI agents to efficiently navigate large knowledge spaces through structured metadata layers.

## Overview

AgentLib provides a three-layer navigation pattern:
- **L0 (Catalog):** What exists? Lightweight metadata (~50 tokens/book)
- **L1 (Manifest):** What's inside? Chapter structure, summaries, concepts (~200-500 tokens/book)
- **L2 (Chunks):** Actual content. Self-contained text segments (~300-500 tokens each)
- **Ls (Search):** Concept search shortcut — skip L0/L1 when you know what you need

## Installation

```bash
# As a Claude Code plugin
/plugin marketplace add barkain/agentlib
/plugin install agentlib
```

## Usage

### 1. Ingest a book
```bash
/agentlib-ingest-book ~/books/owasp-guide.pdf
```

### 2. Query naturally
The agent discovers and uses AgentLib tools automatically:
```
"What does OWASP say about token rotation?"
"What refresh token strategy does the guide recommend?"
```

## Architecture

```
Parse → Chunk → Summarise → Index → Serialise
```

- **Parse:** PyMuPDF (PDF) or ebooklib (EPUB) extract text with structure
- **Chunk:** Semantic paragraph merging, 300-500 tokens, never crossing section boundaries
- **Summarise:** Claude Haiku generates chapter summaries + key concepts (1 call/chapter)
- **Index:** Concept extraction maps searchable terms to specific chunks (1 call/book)
- **Serialise:** JSON metadata + markdown chunk files to persistent storage

## MCP Tools

| Tool | Layer | Description |
|------|-------|-------------|
| `browse_library` | L0 | List all books with metadata |
| `open_book` | L1 | Get chapter/section structure for a book |
| `read_chunks` | L2 | Read specific chunk content (max 10/call) |
| `search_concepts` | Ls | Find concepts across the library |

## Development

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Start MCP server directly
uv run python server.py
```

## Data Storage

All preprocessed data lives under `$AGENTLIB_DATA` (or `~/.agentlib/library`):

```
library/books/
├── catalog.json
└── {book-id}/
    ├── manifest.json
    └── chunks/
        ├── ch01-s01-001.md
        └── ch01-s01-002.md
```

## License

MIT
