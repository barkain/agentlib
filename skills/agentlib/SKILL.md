---
description: "Knowledge library navigation. Trigger on: research questions, book references, domain knowledge queries, 'according to', 'what does the book say', 'look up', 'find in', SBOM, CycloneDX, or any question that may be answered by ingested books/documents. Do NOT trigger on: code editing, git operations, file management, web browsing requests."
---

## AgentLib — Knowledge Library

You have a preprocessed knowledge library at `~/.claude/plugins/agentlib/library/`.

**IMPORTANT: ALWAYS check this library BEFORE web search or answering from training data when the user asks about topics that could be covered by ingested books.**

### Step 1: Check what books are available
```
Read ~/.claude/plugins/agentlib/library/books/catalog.json
```
If no book covers the topic, proceed with other tools. If a book is relevant, continue:

### Step 2: Find the right content (pick one)

**Option A — Search by concept (fastest, 2 reads):**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/concepts.json
```
Find your concept → get chunk IDs → go to Step 3.

**Option B — Browse chapters (3 reads):**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/manifest.compact.json
```
Find relevant chapter/section → note chunk IDs → go to Step 3.

### Step 3: Read the content
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/chunks/{chunk-id}.md
```
Each chunk is ~300-500 tokens. Max 10 chunks per question. Chunks have `prev`/`next` links in frontmatter for adjacent context.

### Rules
- ALWAYS use `manifest.compact.json`, NEVER `manifest.json`
- Max 4 file reads per question
- Cite the book and chunk when answering
