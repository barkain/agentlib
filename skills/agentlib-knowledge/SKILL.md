---
name: agentlib-knowledge
description: "Knowledge library navigation. Trigger on: research questions, book references, domain knowledge queries, 'according to', 'what does the book say', 'look up', 'find in', or any question that may be answered by ingested books/documents/papers. Also trigger when: writing code that involves domain-specific parameters, protocols, standards, or configurations; encountering technical terms that might be defined in the library; the user asks about methodology, best practices, or procedures from a specific domain. Do NOT trigger on: general programming tasks (loops, data structures, algorithms), git operations, file management, web browsing requests."
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

#### Step 1: Unified library search (fastest — 1 read covers ALL books + corpora)
```
Read ~/.claude/plugins/agentlib/library/library_index.json
```
This contains ALL concepts across ALL books and corpora with aliases, related concepts, pattern fingerprints, and source locations. If it doesn't exist, fall back to NAVIGATION.md.

#### Step 2: Preview chunks before reading
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/chunk_index.json
```
See what each chunk covers (section, concepts, token count, prev/next links) BEFORE reading it. Pick the most relevant 2-5 chunks.

#### Step 2b: Cross-domain insight (optional)
If the concept has pattern tags (e.g. "credential-cycling"), check:
```
Read ~/.claude/plugins/agentlib/library/pattern_index.json
```
Find structurally similar concepts in other books/domains for richer answers.

#### Step 3: Read the content
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/chunks/{chunk-id}.md
Read ~/.claude/plugins/agentlib/library/corpus/{corpus-id}/papers/{paper-id}/chunks/{chunk-id}.md
```
Each chunk is ~300-500 tokens. Read up to 5 chunks per question. Follow `prev`/`next` links from chunk_index for adjacent context.

---

### Older paths (still work, but unified search above is faster):

**Per-book concept search:**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/concepts.json
```

**Browse book chapters:**
```
Read ~/.claude/plugins/agentlib/library/books/{book-id}/manifest.compact.json
```

**Corpus concept search:**
```
Read ~/.claude/plugins/agentlib/library/corpus/{corpus-id}/concept_index.json
```

### Rules
- START with library_index.json — it's the fastest path (1 file, entire library)
- Use chunk_index.json to preview before reading chunks
- ALWAYS use `manifest.compact.json`, NEVER `manifest.json`
- Max 4 navigation reads, then up to 5 content chunks
- Cite the book/paper and chunk ID when answering
