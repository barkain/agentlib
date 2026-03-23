# AgentLib Walkthrough: Scientific Paper Corpus (Davidson Physics)

A concrete example showing how AgentLib ingests a collection of scientific papers, and how the `library-researcher` agent navigates them to answer a specific question — using 58% fewer tokens than reading the raw PDFs.

---

## 1. The Corpus

**8 papers by Prof. Aharon Davidson** covering quantum cosmology, black hole microstates, particle physics unification, and modified gravity theories. Published 2017-2024, sourced from arXiv.

These are dense theoretical physics papers — exactly the kind of content where structured navigation saves massive tokens compared to reading raw PDFs.

---

## 2. Ingestion

```
/agentlib:agentlib-ingest-corpus aharon_davidson_papers/
```

### What happens

1. **PDF discovery** — finds all PDFs in the folder (8 papers)
2. **Metadata extraction** — LLM reads first page of each paper to extract title, authors, year, abstract
3. **Parsing + chunking** — extracts text, splits into ~300-500 token chunks
4. **Summarisation** — LLM summarises each section, extracts key findings
5. **Topic clustering** — LLM groups papers into thematic clusters
6. **Concept indexing** — LLM builds cross-paper concept index (35 concepts)
7. **Navigation update** — updates NAVIGATION.md with the new corpus

### What gets produced

```
~/.claude/plugins/agentlib/library/corpus/davidson-physics/
├── corpus_catalog.json              # 4 topic clusters
├── concept_index.json               # 35 concepts across all papers
├── clusters/
│   ├── quantum-cosmology-gravity.json
│   ├── brane-cosmology-universe-creation.json
│   ├── particle-physics-unification.json
│   └── spacetime-geometry-relativity.json
└── papers/
    ├── davidson2017-hydrogenlike-spectrum-of/
    │   ├── manifest.compact.json
    │   └── chunks/*.md
    ├── davidson2019-from-planck-area/
    │   ├── manifest.compact.json
    │   └── chunks/*.md
    └── ... (8 papers total, 106 chunks)
```

---

## 3. Querying

**User asks:** "What is the dimensionless constant η in Davidson's Planck area formula, and how is it determined?"

This is a highly specific question that can only be answered by reading the actual paper content — no LLM would have this in training data.

### What happens

The `/agentlib-knowledge` skill delegates to the `library-researcher` agent, which runs in an **isolated context window**:

1. **Read NAVIGATION.md** (1 read) — sees the Davidson physics corpus
2. **Read concept_index.json** (1 read) — finds "Bekenstein-Hawking entropy", "Planck scale", "Graph theory enumeration" pointing to `davidson2019-from-planck-area`
3. **Read 2-3 chunks** — reads the relevant sections on horizon tiling and entropy derivation

**Agent stats:** 7 tool uses, 14.6k tokens, 16 seconds.

### The answer

> Based on Davidson's paper "From Planck area to graph theory: Topologically distinct black hole microstates" (arXiv:1907.03090):
>
> **The Formula**
>
> The Planck-sized horizon unit area is:
> `A_P = η ℓ²_P`
> where η is a dimensionless universal constant.
>
> **How η is determined**
>
> `η = 4 log γ`
>
> where γ is the asymptotic growth constant of unlabeled planar chordal graphs that tile the black hole horizon.
>
> Davidson maps horizon tilings to planar chordal graphs. The number of topologically distinct configurations grows as:
> `g(n) ≈ α · n^(-5/2) · γ^n`
>
> The Boltzmann entropy then becomes:
> `S_BH(n) = k_B (n log γ − 5/2 log n + ...)`
>
> Matching this to the Bekenstein-Hawking formula yields η = 4 log γ.
>
> **Bounds on η:** 27.23 < γ < 30.06, giving roughly **9.0 < η < 13.6**
>
> *Source: Davidson (2019), chunks ch01-s04-001 and ch02-s04-001*

---

## 4. Token Comparison

| Approach | Main context | Total tokens | Time |
|---|---|---|---|
| **AgentLib (agent)** | **~3k** | **~33k** | **32s** |
| AgentLib (direct reads) | ~15k | ~30k | 38s |
| Raw PDF reading | ~3k | ~79k | 1m 9s |

The agent approach keeps the main conversation at just **3k tokens** while still providing a detailed, cited answer. This means you can ask many research questions in a single session without filling up the context window.

Over two queries in one session (this question + a book question), the main context only grew by **7k tokens** total — compared to 30k+ without agent delegation.

---

## 5. Key Takeaway

For a specific physics question buried in 8 papers:
- **Raw approach:** spawns a subagent that reads raw PDFs → 79k total tokens, 1+ minute
- **AgentLib:** structured agent reads concept index → targeted chunks → 33k total tokens, 32 seconds
- **Same answer quality**, with citations to specific paper sections and chunk IDs
