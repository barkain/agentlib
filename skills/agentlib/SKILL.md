## AgentLib — Knowledge Navigation

When answering questions that require domain knowledge beyond your training data, use AgentLib tools.

### Books
1. `search_concepts(q)` → `read_chunks(ids)` [2 calls, ~3-4k tokens]
2. Or: `browse_library()` → `open_book(id)` → `read_chunks(ids)` [3 calls, ~5-8k tokens]
3. Budget: max 4 calls

### Navigation Strategy

**Start cheap, go deep only when needed:**

- **If you know what concept you need:** Start with `search_concepts(query)`. This is the fastest path — it returns chunk IDs directly. Then `read_chunks` to get the content. (2 calls)

- **If you need to explore:** Start with `browse_library()` to see what's available (~50 tok/book). Pick a book, then `open_book(id)` to see its chapter structure, summaries, and concept index (~1.5-2k tokens for a 20-chapter book). Use the manifest to decide which chunks to read. (3 calls)

- **Never read chunks speculatively.** Always use L0/L1 metadata or concept search to identify the right chunks first.

### Cost Awareness

| Layer | Tool | Typical cost | When to use |
|-------|------|-------------|-------------|
| L0 | `browse_library` | ~50 tok/book | Discover what exists |
| L1 | `open_book` | ~1.5-2k tok | Decide what to read (chapters, summaries, concepts) |
| L2 | `read_chunks` | ~300-500 tok/chunk | Get actual content (max 10 chunks/call) |
| Ls | `search_concepts` | ~60 tok | Known concept shortcut — jumps to chunk IDs |

Each tool call adds to the conversation context. Minimize calls by using metadata to make informed decisions before requesting content. In a real benchmark, AgentLib reduced content tokens by 47% vs reading a raw 400-page PDF.
