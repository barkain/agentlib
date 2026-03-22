<p align="center">
  <img src="assets/hero.png" alt="AgentLib — Agentic Knowledge Navigation" width="100%">
</p>

# AgentLib

**AI agents waste massive tokens navigating knowledge because they have no map.**

When an agent needs to answer a question from a book, a paper corpus, or a database, it has no idea where to look. So it guesses. It reads the wrong file, backs up, reads another, accumulates context — and every token it has already read gets re-processed on every subsequent call. The cost isn't linear. It's **O(n^2)** in the number of tool calls: the marginal cost of call *n+1* equals the entire accumulated context at that point.

AgentLib gives agents a map.

## How it works

AgentLib has two parts:

1. **Ingestion pipeline** — preprocesses books, papers, and databases into small, self-contained chunks with lightweight metadata at multiple layers.
2. **Universal navigation skill** — a single skill (`knowledge`) that teaches the agent to read cheap metadata first, then drill into specific chunks.

No MCP server required. No tool calls. The agent reads preprocessed files directly from `~/.claude/plugins/agentlib/library/`.

> **Note:** `server.py` is included for optional MCP usage and benchmarking but is not required for normal operation.

### Three metadata layers

```
L0  "What exists?"       →  catalog: ~50 tokens per book          (cheap)
L1  "What's inside?"     →  manifest: structure, summaries, concepts   (moderate)
L2  "Give me the content" →  small self-contained chunks, 300-500 tok  (expensive)
```

Plus a **concept index** shortcut (Ls) that jumps directly to relevant chunks when the agent already knows what it's looking for.

### Library structure

```
library/
├── NAVIGATION.md
└── books/
    ├── catalog.json                    ← L0
    └── {book-id}/
        ├── manifest.compact.json       ← L1
        ├── concepts.json               ← Ls
        └── chunks/
            └── {chunk-id}.md           ← L2
```

## Real-World Results

### Result 1 — 82% reduction

**Question:** "What specific actor frameworks does the book mention for multiagent communication?"

| Metric | AgentLib | Raw PDF | Reduction |
|--------|----------|---------|-----------|
| Content tokens | 6.9k | 38.6k | **82%** |
| Answer quality | Correct — Ray, Orleans, Akka | Correct — Ray, Orleans, Akka | Same |
| Source citations | Yes (chapter + chunk IDs) | No | — |

**How AgentLib navigated:** skill triggered → `concepts.json` → `manifest.compact.json` → 2 chunks → answer with citations.

**How raw PDF was read:** read TOC → landed on wrong pages → re-read → answer. 38.6k content tokens, multiple wasted reads.

### Result 2 — 47% reduction

**Question:** "What are the maturity levels for SBOM according to the CycloneDX standard?"

| Metric | AgentLib | Raw PDF | Reduction |
|--------|----------|---------|-----------|
| Content tokens | 7.8k | 14.7k | **47%** |
| Answer quality | Correct (5 dimensions table) | Correct (5 dimensions table) | Same |

**How AgentLib navigated:** `concepts.json` → chunk IDs → `manifest.compact.json` → 2 exact chunks (~700 tokens).

**How raw PDF was read:** read entire 80-page PDF and scanned for the answer — no structure, no way to skip irrelevant pages.

## Cost simulations

Simulated on realistic workloads (15-book library, 487-paper corpus, 80-table database):

|                      | Books |       | Papers |       | Database |       |
|----------------------|-------|-------|--------|-------|----------|-------|
| **Metric**           | Base  | AL    | Base   | AL    | Base     | AL    |
| Tool calls           | 5     | 2     | 6      | 5     | 7        | 4     |
| Cumul. input tokens  | 25.9K | 4.5K  | 51.7K  | 23.4K | 23.3K    | 10.4K |
| Wrong reads/queries  | 1     | 0     | 1      | 0     | 2        | 0     |
| **Token reduction**  |       | **82%** |      | **55%** |        | **55%** |

The core principle: *no heavy indexing, no vector databases — just smart, lightweight metadata and small content blobs.*

## Installation

```bash
# As a Claude Code plugin
/plugin marketplace add barkain/agentlib
/plugin install agentlib
```

Or install manually:
```bash
git clone https://github.com/barkain/agentlib.git
claude --plugin-dir ./agentlib
```

## Usage

### Ingest a book
```bash
/agentlib:agentlib-ingest-book ~/books/owasp-guide.pdf
```

### Querying

**Auto-trigger** — just ask naturally. The skill activates when it detects research/knowledge questions:
> "What specific actor frameworks does the book mention for multiagent communication?"

**Explicit invocation** — prefix with `/knowledge` when you want the book's answer, not Claude's training data:
> /knowledge What defensive techniques protect against prompt injection?

Use explicit invocation when Claude might already know the answer but you want the book's specific take.

The skill teaches the agent to read `catalog.json` or `concepts.json` first (cheap), then drill into specific chunks (expensive) — no server process, no tool overhead.

## LLM Providers

AgentLib supports 5 LLM providers for ingestion and summarization (auto-detected from environment):

| Provider | Model | Env var |
|----------|-------|---------|
| Anthropic | Claude Haiku 4.5 | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-4o Mini | `OPENAI_API_KEY` |
| xAI | Grok-3 Mini | `XAI_API_KEY` |
| Google | Gemini 2.0 Flash | `GOOGLE_API_KEY` |
| DeepSeek | DeepSeek Chat | `DEEPSEEK_API_KEY` |

Set `AGENTLIB_PROVIDER` to override auto-detection.

## Development

```bash
uv sync --dev        # Install dependencies
uv run pytest        # Run tests
```

## License

MIT
