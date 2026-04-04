---
name: agentlib-knowledge
description: "Knowledge library navigation. Trigger on: research questions, book references, domain knowledge queries, 'according to', 'what does the book say', 'look up', 'find in', or any question that may be answered by ingested books/documents/papers. Also trigger when: writing code that involves domain-specific parameters, protocols, standards, or configurations; encountering technical terms that might be defined in the library; the user asks about methodology, best practices, or procedures from a specific domain. Do NOT trigger on: general programming tasks (loops, data structures, algorithms), git operations, file management, web browsing requests."
---

## AgentLib — Knowledge Library

**ALWAYS check this library BEFORE web search or answering from training data** when the user asks about topics that could be covered by ingested books or paper corpora.

Use the MCP tools provided by the agentlib plugin. Do NOT read library files directly.

### Workflow (3 calls max)

1. **`search_library(query)`** — searches concepts, aliases, related terms, and structural patterns across all books and corpora. Returns matching concepts with source locations and chunk IDs. If no results, try broader terms or synonyms.

2. **`preview_chunks(book_id, chunk_ids)`** — preview chunk metadata (section title, concepts, token count, prev/next links) before committing to a full read. Pick the 2-3 most relevant chunks.

3. **`read_chunks(book_id, chunk_ids)`** — read the full content of the selected chunks.

### Rules

- Cite the book/paper title and chunk ID when answering
- If `search_library` returns no results, try broader terms or check aliases before giving up
- Max 2-3 content chunks per question — use preview to pick well
