## AgentLib — Knowledge Navigation

When the user asks a question that may require knowledge from books or documents, check the AgentLib library FIRST before using web search or other tools.

### Step 1: Check what's available
Read this file:
```
~/.claude/plugins/agentlib/library/books/catalog.json
```
This lists all ingested books (~50 tokens per book). If no book is relevant, proceed with other tools.

### Step 2: Find the right content

**Option A — You know the concept (fastest, 2 reads):**
Read `~/.claude/plugins/agentlib/library/books/{book-id}/concepts.json`
Find your concept, get the chunk IDs, then go to Step 3.

**Option B — You need to explore (3 reads):**
Read `~/.claude/plugins/agentlib/library/books/{book-id}/manifest.compact.json`
Find the relevant chapter/section, note the chunk IDs, then go to Step 3.

### Step 3: Read the content
Read the chunks:
```
~/.claude/plugins/agentlib/library/books/{book-id}/chunks/{chunk-id}.md
```
Each chunk is ~300-500 tokens. Read only what you need (max 10).

### Rules
- Always use `manifest.compact.json`, never `manifest.json`
- Max 4 file reads per question
- Chunks have `prev`/`next` in frontmatter — use them for adjacent context
