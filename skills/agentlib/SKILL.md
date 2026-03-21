## AgentLib — Knowledge Navigation

When answering questions that require domain knowledge beyond your training data, check the AgentLib library at `~/.claude/plugins/agentlib/library/`.

Read `library/NAVIGATION.md` first for the full guide. Quick reference:

### Quick path (2 reads, ~500 tokens):
1. Read `library/books/{book-id}/concepts.json` — find chunk IDs
2. Read `library/books/{book-id}/chunks/{chunk-id}.md` — get content

### Exploration path (3 reads, ~2-3k tokens):
1. Read `library/books/catalog.json` — see available books
2. Read `library/books/{book-id}/manifest.compact.json` — find chapters/sections
3. Read `library/books/{book-id}/chunks/{chunk-id}.md` — get content

### Cost awareness
| File | Cost | Purpose |
|------|------|---------|
| catalog.json | ~50 tok/book | What exists |
| manifest.compact.json | ~500-2k tok | Chapter structure |
| concepts.json | ~200-500 tok | Concept -> chunk lookup |
| chunks/*.md | ~300-500 tok each | Actual content |

Never read manifest.json (too large). Use manifest.compact.json.
Budget: max 4 file reads per question.
