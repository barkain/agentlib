---
name: agentlib-knowledge
description: "Knowledge library navigation. Trigger on: research questions, book references, domain knowledge queries, 'according to', 'what does the book say', 'look up', 'find in', or any question that may be answered by ingested books/documents/papers. Do NOT trigger on: code editing, git operations, file management, web browsing requests."
---

## AgentLib — Knowledge Library

**This skill activates automatically** for research/knowledge questions. Users can also invoke it explicitly with `/agentlib-knowledge <question>` to always consult the library.

You have a preprocessed knowledge library at `~/.claude/plugins/agentlib/library/`.

**IMPORTANT: ALWAYS check this library BEFORE web search or answering from training data when the user asks about topics that could be covered by ingested books or paper corpora.**

**You MUST delegate this research to the `library-researcher` agent using the Agent tool.** Do NOT read library files directly — spawn the agent with the user's question and let it handle all navigation and reading. This keeps your main context clean.

When spawning the agent, include the **absolute library path** in the prompt (expand `~` to the full home directory). Example:
> Research the following question using the library at /Users/nadavbarkai/.claude/plugins/agentlib/library/
> Question: {user's question}

The agent will return a synthesized answer with citations.

If the Agent tool is unavailable, fall back to the manual steps below.

### Manual fallback (only if agent delegation fails)

#### Step 1: Check what's available
```
Read ~/.claude/plugins/agentlib/library/NAVIGATION.md
```
This lists ALL books AND paper corpora. Check BOTH sections — if a book OR corpus covers the topic, continue with the appropriate path below. Only proceed with other tools if nothing is relevant.

---

### Path A: Books

**Find content (pick one):**

**A1 — Search by concept (fastest, 2 reads):**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/concepts.json
```
Find your concept → get chunk IDs → go to Step 3.

**A2 — Browse chapters (3 reads):**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/manifest.compact.json
```
Find relevant chapter/section → note chunk IDs → go to Step 3.

---

### Path B: Corpora (scientific papers)

**B1 — Search by concept across all papers (fastest, 1 read):**
```
Read ~/.claude/plugins/agentlib/library/corpus/{corpus-id}/concept_index.json
```
Find your concept → get paper IDs and chunk IDs → go to Step 3.

**B2 — Browse by topic cluster (2-3 reads):**
1. `corpus_catalog.json` — see topic clusters
2. `clusters/{cluster-id}.json` — see papers with abstracts
3. Pick papers → read `papers/{paper-id}/manifest.compact.json`

---

### Step 3: Read the content
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/chunks/{chunk-id}.md
Read ~/.claude/plugins/agentlib/library/corpus/{corpus-id}/papers/{paper-id}/chunks/{chunk-id}.md
```
Each chunk is ~300-500 tokens. Read up to 5 chunks per question. Chunks have `prev`/`next` links for adjacent context.

### Rules
- ALWAYS use `manifest.compact.json`, NEVER `manifest.json`
- Max 4 navigation reads, then up to 5 content chunks
- Cite the book/paper and chunk ID when answering
