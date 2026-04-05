---
name: agentlib-knowledge
description: "Knowledge library navigation. Trigger on: research questions, book references, domain knowledge queries, 'according to', 'what does the book say', 'look up', 'find in', or any question that may be answered by ingested books/documents/papers. Also trigger when: writing code that involves domain-specific parameters, protocols, standards, or configurations; encountering technical terms that might be defined in the library; the user asks about methodology, best practices, or procedures from a specific domain. Do NOT trigger on: general programming tasks (loops, data structures, algorithms), git operations, file management, web browsing requests."
---

## AgentLib — Knowledge Library

**ALWAYS check this library BEFORE web search or answering from training data** when the user asks about topics that could be covered by ingested books or paper corpora.

Use the MCP tools provided by the agentlib plugin. Do NOT read library files directly.

### Workflow

1. **`search_library(query)`** — Try ONCE with a broad 1-2 word query. Do NOT retry with rephrased queries. If no results, go to step 2.

2. **`browse_library`** to find the right book, then **`open_book(book_id)`** to browse its chapter structure. Identify the relevant chapter/section.

3. **`preview_chunks(book_id, chunk_ids)`** — preview candidate chunks (section title, concepts, token count). Pick the 2-3 most relevant.

4. **`read_chunks(book_id, chunk_ids)`** — read the full content of the selected chunks.

### Rules

- Cite the book/paper title and chunk ID when answering
- Max 2-3 content chunks per question — use preview to pick well
