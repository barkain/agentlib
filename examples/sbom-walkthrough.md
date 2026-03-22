# AgentLib Walkthrough: Authoritative Guide to SBOM (CycloneDX)

A concrete, end-to-end example showing how AgentLib ingests a PDF, what it produces, and how Claude navigates the output to answer questions — all without reading the full document.

---

## 1. The Book

**Authoritative Guide to SBOM (CycloneDX)**
- URL: https://cyclonedx.org/guides/OWASP_CycloneDX-Authoritative-Guide-to-SBOM-en.pdf
- ~80 pages covering the CycloneDX standard (ECMA-424) for Software Bills of Materials
- Chapters on the object model, lifecycle phases, BOM maturity and quality, SBOM generation and consumption, license compliance, cryptographic components, component relationships, extensibility, and practical scenarios

This is the kind of dense reference material that benefits most from AgentLib: a developer needs specific answers, not the whole book.

---

## 2. Ingestion

### Step 1: Download the PDF

Download from: https://cyclonedx.org/guides/OWASP_CycloneDX-Authoritative-Guide-to-SBOM-en.pdf

### Step 2: Ingest

```
/agentlib:agentlib-ingest-book ~/Downloads/OWASP_CycloneDX-Authoritative-Guide-to-SBOM-en.pdf
```

### What happens at each stage

1. **PDF parsing** — Extracts text from all pages, preserving headings and structure.
2. **Chapter detection** — Identifies chapter boundaries from headings (e.g., "CycloneDX Object Model", "Lifecycle Phases", "License Compliance").
3. **Section splitting** — Breaks chapters into logical sections based on subheadings.
4. **Chunking** — Splits sections into chunks of ~150-400 tokens each. Each chunk gets a stable ID like `ch10-s03-001`.
5. **Concept extraction** — Scans all chunks and builds a reverse index: concept name to chunk IDs.
6. **Manifest generation** — Creates a compact table of contents with chapter/section summaries.
7. **Catalog update** — Adds the book entry to the global `catalog.json`.

### What gets produced

```
~/.claude/plugins/agentlib/library/books/authoritativeguide-to-sbom/
├── manifest.compact.json    # Table of contents with summaries (~2k tokens)
├── concepts.json            # Reverse index: concept → chunk IDs (~1k tokens)
└── chunks/
    ├── ch03-s03-001.md      # Authoritative > About the Guide
    ├── ch06-s01-001.md      # Introduction > Main
    ├── ch07-s01-001.md      # CycloneDX Object Model > Main
    ├── ...
    ├── ch10-s03-001.md      # BOM Coverage, Maturity, and Quality > SCVS BOM Maturity Model
    ├── ch15-s02-001.md      # License Compliance > Open Source Licensing
    ├── ...
    └── ch20-s02-001.md      # Extensibility > CycloneDX Properties
```

98 chunks total. Each chunk is a self-contained markdown file of 150-400 tokens.

---

## 3. What the Output Looks Like

### catalog.json (after ingestion)

The global catalog gets a new entry. This is what Claude reads first to decide if a book is relevant.

```json
{
  "books": [
    {
      "id": "authoritativeguide-to-sbom",
      "title": "Authoritativeguide To Sbom",
      "domain_tags": [],
      "summary": "The Authoritative Guide to SBOM provides comprehensive documentation of CycloneDX, an OWASP-ratified standard (ECMA-424) for creating, generating, and consuming machine-readable Software Bills of Materials that enable software transparency and supply chain risk management across diverse use cases including vulnerability tracking, license compliance, cryptographic management, and intellectual property protection. The guide covers CycloneDX's object model, lifecycle phases, quality standards, consumption tools, and practical implementation strategies for organizations seeking to establish transparency and security throughout their software supply chains.",
      "chapter_count": 20,
      "total_chunks": 98
    }
  ]
}
```

### manifest.compact.json (excerpt)

The compact manifest gives Claude a browsable table of contents with summaries and concept tags per chapter.

```json
{
  "book_id": "authoritativeguide-to-sbom",
  "chapters": [
    {
      "id": "ch10",
      "title": "BOM Coverage, Maturity, and Quality",
      "summary": "This chapter defines SBOM coverage, maturity, and quality standards, establishing minimum elements r...",
      "concepts": [
        "NTIA Minimum Elements",
        "SCVS BOM Maturity Model",
        "SBOM Quality Dimensions"
      ],
      "sections": [
        {
          "id": "ch10-s02",
          "title": "NTIA Minimum Elements",
          "chunks": 1
        },
        {
          "id": "ch10-s03",
          "title": "SCVS BOM Maturity Model",
          "chunks": 1
        },
        {
          "id": "ch10-s04",
          "title": "SBOM Quality",
          "chunks": 1
        }
      ]
    },
    {
      "id": "ch20",
      "title": "Extensibility",
      "summary": "This chapter explains the three primary means of extending CycloneDX: properties, properties with re...",
      "concepts": [
        "Extension points",
        "CycloneDX properties",
        "Registered namespaces"
      ],
      "sections": [
        {
          "id": "ch20-s01",
          "title": "Main",
          "chunks": 1
        },
        {
          "id": "ch20-s02",
          "title": "CycloneDX Properties",
          "chunks": 1
        },
        {
          "id": "ch20-s03",
          "title": "CycloneDX Properties and Registered Namespaces",
          "chunks": 1
        },
        {
          "id": "ch20-s04",
          "title": "XML Extensions",
          "chunks": 1
        }
      ]
    }
  ]
}
```

### concepts.json (excerpt)

The concept index maps domain terms directly to chunk IDs. This is the fastest lookup path.

```json
{
  "SCVS BOM Maturity Model": [
    "ch10-s03-001",
    "ch10-s04-001"
  ],
  "SBOM Quality and Maturity": [
    "ch10-s04-001",
    "ch18-s01-001"
  ],
  "CycloneDX Extensions": [
    "ch20-s01-001",
    "ch20-s02-001",
    "ch20-s03-001",
    "ch20-s04-001"
  ],
  "License Compliance": [
    "ch15-s01-001",
    "ch15-s02-001",
    "ch15-s03-001"
  ],
  "CycloneDX Lifecycle Phases": [
    "ch08-s01-001",
    "ch11-s03-001"
  ],
  "Dependency Graphs": [
    "ch17-s04-001",
    "ch19-s02-001"
  ],
  "Software Supply Chain Security": [
    "ch03-s03-001",
    "ch06-s05-001",
    "ch11-s01-001",
    "ch17-s01-001"
  ]
}
```

### Chunk file: `chunks/ch10-s03-001.md`

Each chunk is a small, self-contained markdown file with structured frontmatter.

```markdown
---
chunk_id: ch10-s03-001
source_id: authoritativeguide-to-sbom
section: BOM Coverage, Maturity, and Quality > SCVS BOM Maturity Model
token_count: 284
---

The OWASP Software Component Verification Standard (SCVS) is a way for organizations to measure
and improve their software supply chain assurance. SCVS is required in NIST SP 800-218 (SSDF v1.1)
and similar frameworks.
In addition to the supply chain controls it recommends, SCVS also has a complementary BOM Maturity
Model which allows bill of materials to be evaluated. The model consists of:
•
a formal taxonomy of different types of data possible in a bill of materials, independent of BOM
format
•
a unique identifier, description, and other metadata about each item in the taxonomy
•
the level of complexity or difficulty in supporting different types of data
The model can be used to evaluate:
•
Incoming BOMs adherance to organizational policy by supporting the data required by various
stakeholders
•
BOM generation and consumption tools
```

---

## 4. Querying — Example 1: Concept Search Path

**User asks:** "What are the maturity levels for SBOM according to the CycloneDX standard?"

Here is the exact sequence Claude follows, defined by the `/knowledge` skill:

### Step 1: Check catalog (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/catalog.json`.

Sees `authoritativeguide-to-sbom` with summary mentioning "quality standards" and "Software Bills of Materials" — relevant.

### Step 2: Search by concept (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/authoritativeguide-to-sbom/concepts.json`.

Scans for "maturity" and finds:

```json
"SCVS BOM Maturity Model": ["ch10-s03-001", "ch10-s04-001"],
"SBOM Quality and Maturity": ["ch10-s04-001", "ch18-s01-001"]
```

Direct hit. Three unique chunk IDs identified.

### Step 3: Read chunks (2 reads)

Claude reads:
- `chunks/ch10-s03-001.md` — covers the SCVS BOM Maturity Model: a formal taxonomy of data types possible in a BOM, with complexity levels and evaluation criteria
- `chunks/ch10-s04-001.md` — covers SBOM Quality as a multidimensional construct with five dimensions: Breadth (SCVS), Depth (SCVS), Lifecycles, Techniques, and Confidence

### Step 4: Answer with citation

Claude synthesizes an answer from ~700 tokens of chunk content and cites the source:

> According to the CycloneDX Authoritative Guide to SBOM (ch10-s03, ch10-s04), SBOM maturity is evaluated through the OWASP SCVS BOM Maturity Model, which provides a formal taxonomy of data types possible in a BOM along with the complexity level for supporting each type. The model evaluates three areas: incoming BOM adherence to organizational policy, BOM generation/consumption tool capabilities, and BOM format alignment with requirements. SBOM quality itself is multidimensional, assessed across five dimensions: Breadth (coverage of data types), Depth (detail level), Lifecycles (which SDLC phases produced the BOM), Techniques (approaches for determining component identity), and Confidence (reliability of identity analysis).

**Total reads: 4** (catalog + concepts + 2 chunks). Total tokens consumed: ~1,400.

---

## 5. Querying — Example 2: Exploration Path

**User asks:** "How do I extend CycloneDX with custom properties?"

This is a targeted question, but the user wants practical how-to guidance. Claude uses a combination of concept lookup and manifest browsing.

### Step 1: Check catalog (1 read)

Claude reads `catalog.json`. The SBOM guide is relevant.

### Step 2: Search by concept (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/authoritativeguide-to-sbom/concepts.json`.

Finds:

```json
"CycloneDX Extensions": ["ch20-s01-001", "ch20-s02-001", "ch20-s03-001", "ch20-s04-001"]
```

Four chunks in chapter 20 (Extensibility). Claude also optionally checks the manifest to confirm section titles:

```
ch20 - Extensibility
  ├── ch20-s01 - Main (1 chunk)
  ├── ch20-s02 - CycloneDX Properties (1 chunk)
  ├── ch20-s03 - CycloneDX Properties and Registered Namespaces (1 chunk)
  └── ch20-s04 - XML Extensions (1 chunk)
```

### Step 3: Read selected chunks for detail (2-3 reads)

Claude picks the most relevant sections:
- `chunks/ch20-s01-001.md` — overview of three extension mechanisms: properties, registered namespaces, and XML extensions; notes on hardened schemas
- `chunks/ch20-s02-001.md` — how to use CycloneDX properties as name-value pairs, with JSON and XML examples
- `chunks/ch20-s03-001.md` — registered namespaces with hierarchical naming (e.g., `cdx:gomod:binary`, `cdx:npm:package:bundled`) and the GitHub taxonomy registry

### Step 4: Answer with citation

Claude provides a structured answer covering the three extension mechanisms, with the JSON/XML property examples from ch20-s02, and links to the CycloneDX Property Taxonomy repository on GitHub for namespace registration.

**Total reads: 5-6** (catalog + concepts + manifest + 2-3 chunks). Total tokens consumed: ~2,500.

---

## 6. Token Comparison

| Approach | Tokens consumed | Reads |
|---|---|---|
| Paste full PDF into context | ~50,000 tokens | 1 (wastes budget on irrelevant content) |
| Naive RAG (embed + retrieve top-5) | ~2,000 tokens | 1 retrieval call |
| AgentLib — concept search (Example 1) | ~1,400 tokens | 4 reads |
| AgentLib — exploration (Example 2) | ~2,500 tokens | 5-6 reads |

The CycloneDX Authoritative Guide to SBOM PDF is ~80 pages. Pasting it would consume ~50k tokens — wasting budget on irrelevant content like the glossary, references, and chapters unrelated to the question.

AgentLib's structured navigation keeps total consumption to **1,400-2,500 tokens** by letting Claude decide what to read based on a lightweight table of contents and concept index. The trade-off is a few extra reads (tool calls), but each read is small and targeted.

The key advantage over naive RAG: Claude sees the *structure* of the document (chapter titles, section hierarchy, concept relationships) before deciding what to read. This means it can answer structural questions ("what does CycloneDX cover?") from the manifest alone, without reading any chunks at all.

---

## Summary

```
PDF (~80 pages)
    │
    ▼  agentlib ingest
    │
    ├── catalog.json          ← "Is this book relevant?" (~100 tokens)
    ├── manifest.compact.json ← "What chapters/sections exist?" (~2k tokens)
    ├── concepts.json         ← "Where is concept X discussed?" (~1k tokens)
    └── chunks/               ← Actual content, ~150-400 tokens each
         ├── ch10-s03-001.md
         ├── ch20-s02-001.md
         └── ... (98 chunks total)

Claude reads catalog → picks a path (concept or browse) → reads 2-3 chunks → answers.
Total: 1,400-2,500 tokens instead of 50,000.
```
