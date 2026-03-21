# AgentLib

**AI agents waste massive tokens navigating knowledge because they have no map.**

When an agent needs to answer a question from a book, a paper corpus, or a database, it has no idea where to look. So it guesses. It reads the wrong file, backs up, reads another, accumulates context — and every token it has already read gets re-processed on every subsequent call. The cost isn't linear. It's **O(n²)** in the number of tool calls: the marginal cost of call *n+1* equals the entire accumulated context at that point.

AgentLib gives agents a map.

## How it works

Instead of reading raw content and hoping for the best, the agent navigates through three lightweight metadata layers:

```
L0  "What exists?"       →  catalog: ~50 tokens per book          (cheap)
L1  "What's inside?"     →  manifest: structure, summaries, concepts   (moderate)
L2  "Give me the content" →  small self-contained chunks, 300-500 tok  (expensive)
```

Plus a **concept search** shortcut (Ls) that jumps directly to relevant chunks when the agent already knows what it's looking for.

### Example: "What refresh token strategy does OWASP recommend?"

**Without AgentLib** (blind file reading):
1. List files — find 15 books
2. Read OWASP table of contents (raw PDF)
3. Guess pages 130-140 — wrong section
4. Read pages 140-150 — still wrong
5. Read pages 150-155 — finally found it

**5 calls, 25,900 cumulative input tokens, 1 wrong read.**

**With AgentLib:**
1. `search_concepts("token rotation")` — returns matching chunk IDs
2. `read_chunks(["ch07-042", "ch07-043"])` — reads exactly what's needed

**2 calls, 4,540 cumulative input tokens, 0 wrong reads.**

## Cost simulations

Simulated on realistic workloads (15-book library, 487-paper corpus, 80-table database):

|                      | Books |       | Papers |       | Database |       |
|----------------------|-------|-------|--------|-------|----------|-------|
| **Metric**           | Base  | AL    | Base   | AL    | Base     | AL    |
| Tool calls           | 5     | 2     | 6      | 5     | 7        | 4     |
| Cumul. input tokens  | 25.9K | 4.5K  | 51.7K  | 23.4K | 23.3K    | 10.4K |
| Wrong reads/queries  | 1     | 0     | 1      | 0     | 2        | 0     |
| **Token reduction**  |       | **82%** |      | **55%** |        | **55%** |

Each domain has a different primary win. **Books:** token efficiency (fewer calls, smaller reads). **Papers:** selection accuracy (find the right papers first). **Databases:** query correctness (right SQL on first attempt).

The core principle: *no heavy indexing, no vector databases — just smart, lightweight metadata and small content blobs.*

## Installation

```bash
# As a Claude Code plugin
/plugin marketplace add barkain/agentlib
/plugin install agentlib
```

## Usage

### Ingest a book
```bash
/agentlib-ingest-book ~/books/owasp-guide.pdf
```

### Query naturally
The agent discovers and uses AgentLib tools automatically:
```
"What does OWASP say about token rotation?"
"What are the most effective approaches for reducing hallucination in LLMs?"
"Total revenue by customer region last quarter, excluding cancelled orders?"
```

### MCP Tools

| Tool | Layer | What it does |
|------|-------|-------------|
| `browse_library` | L0 | List all books with metadata |
| `open_book` | L1 | Get chapter structure, summaries, key concepts |
| `read_chunks` | L2 | Read specific content chunks (max 10/call) |
| `search_concepts` | Ls | Find concepts across the library |

## Development

```bash
uv sync --dev        # Install dependencies
uv run pytest        # Run tests
uv run python server.py  # Start MCP server directly
```

## License

MIT
