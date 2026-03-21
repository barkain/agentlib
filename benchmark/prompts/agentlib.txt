## AgentLib — Knowledge Navigation

When answering questions that require domain knowledge beyond your training data, use AgentLib tools.

### Books
1. `search_concepts(q)` → `read_chunks(ids)` [2 calls]
2. Or: `browse_library()` → `open_book(id)` → `read_chunks(ids)` [3 calls]
3. Budget: max 4 calls

### Navigation Strategy

**Start cheap, go deep only when needed:**

- **If you know what concept you need:** Start with `search_concepts(query)`. This is the fastest path — it returns chunk IDs directly. Then `read_chunks` to get the content. (2 calls)

- **If you need to explore:** Start with `browse_library()` to see what's available. Pick a book, then `open_book(id)` to see chapters and sections. Use the manifest to decide which chunks to read. (3 calls)

- **Never read chunks speculatively.** Always use L0/L1 metadata or concept search to identify the right chunks first.

### Cost Awareness

| Layer | Tool | Cost | When to use |
|-------|------|------|-------------|
| L0 | `browse_library` | ~50 tok/book | Discover what exists |
| L1 | `open_book` | ~200-500 tok | Decide what to read |
| L2 | `read_chunks` | ~300-500 tok/chunk | Get actual content |
| Ls | `search_concepts` | ~60 tok | Known concept shortcut |

Each tool call adds to the conversation context. Minimize calls by using metadata to make informed decisions before requesting content.
