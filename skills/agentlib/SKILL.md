## AgentLib — Knowledge Navigation

You have access to a preprocessed knowledge library at `~/.claude/plugins/agentlib/library/`.
Each source (book, paper corpus, database) has been chunked into small, self-contained pieces with lightweight metadata for efficient navigation.

### The Rule
**Read cheap metadata first. Only read content when you know exactly what you need.**

### Library Structure

```
library/
├── NAVIGATION.md          ← start here if unsure
└── books/
    ├── catalog.json       ← L0: what books exist (~50 tok/book)
    └── {book-id}/
        ├── manifest.compact.json  ← L1: chapters, summaries (~500-2k tok)
        ├── concepts.json          ← Ls: concept → chunk IDs (~200 tok)
        └── chunks/
            └── {chunk-id}.md      ← L2: actual content (~300-500 tok)
```

### Navigation Paths

**Know what concept you need? (2 reads)**
1. `concepts.json` → find chunk IDs for your concept
2. `chunks/{chunk-id}.md` → read the content

**Need to explore? (3 reads)**
1. `catalog.json` → pick a book
2. `manifest.compact.json` → find the right chapter/section
3. `chunks/{chunk-id}.md` → read the content

### Token Budget
| File | Cost | What it tells you |
|------|------|-------------------|
| catalog.json | ~50 tok/book | Title, summary, chapter count |
| manifest.compact.json | ~500-2k tok | Chapter titles, summaries, section structure |
| concepts.json | ~200-500 tok | Concept name → chunk IDs |
| chunks/*.md | ~300-500 tok each | Self-contained content with YAML frontmatter |

### Rules
- **Never** read `manifest.json` — always use `manifest.compact.json`
- **Never** read all chunks — use concepts.json or manifest to pick specific ones
- **Max 10 chunk reads** per question — if you need more, refine your search
- **Max 4 total file reads** per question
- Chunks have `prev`/`next` links in frontmatter — follow them if you need adjacent context
