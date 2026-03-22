# AgentLib Walkthrough: OWASP Web Security Testing Guide

A concrete, end-to-end example showing how AgentLib ingests a PDF, what it produces, and how Claude navigates the output to answer questions — all without reading the full document.

---

## 1. The Book

**OWASP Web Security Testing Guide v4.2**
- URL: https://owasp.org/www-project-web-security-testing-guide/
- ~400 pages covering web application security testing methodology
- Chapters on authentication, session management, input validation, cryptography, business logic, client-side testing, and API security

This is the kind of dense reference material that benefits most from AgentLib: a developer needs specific answers, not the whole book.

---

## 2. Ingestion

### Command

```bash
agentlib ingest \
  --source "https://owasp.org/www-project-web-security-testing-guide/v42/OWASP_Testing_Guide_v4.2.pdf" \
  --id owasp-wstg-v42
```

### What happens at each stage

1. **PDF parsing** — Extracts text from all pages, preserving headings and structure.
2. **Chapter detection** — Identifies chapter boundaries from headings (e.g., "4.5 Authentication Testing", "4.6 Session Management Testing").
3. **Section splitting** — Breaks chapters into logical sections based on subheadings.
4. **Chunking** — Splits sections into chunks of ~300-500 tokens each. Each chunk gets a stable ID like `ch07-s03-002`.
5. **Concept extraction** — Scans all chunks and builds a reverse index: concept name to chunk IDs.
6. **Manifest generation** — Creates a compact table of contents with chapter/section summaries.
7. **Catalog update** — Adds the book entry to the global `catalog.json`.

### What gets produced

```
~/.claude/plugins/agentlib/library/books/owasp-wstg-v42/
├── manifest.compact.json    # Table of contents with summaries (~2k tokens)
├── concepts.json            # Reverse index: concept → chunk IDs (~1k tokens)
└── chunks/
    ├── ch01-s01-001.md      # Introduction > Scope
    ├── ch01-s02-001.md      # Introduction > Principles
    ├── ch04-s01-001.md      # Information Gathering > Search Engine Discovery
    ├── ...
    ├── ch07-s03-001.md      # Authentication Testing > Token-Based Auth
    ├── ch07-s03-002.md      # Authentication Testing > Token-Based Auth (cont.)
    ├── ch08-s02-001.md      # Session Management > Cookie Attributes
    ├── ...
    └── ch12-s04-002.md      # API Testing > GraphQL Injection (cont.)
```

Approximately 150 chunks total. Each chunk is a self-contained markdown file of 300-500 tokens.

---

## 3. What the Output Looks Like

### catalog.json (after ingestion)

The global catalog gets a new entry. This is what Claude reads first to decide if a book is relevant.

```json
{
  "books": [
    {
      "id": "owasp-wstg-v42",
      "title": "OWASP Web Security Testing Guide v4.2",
      "domain_tags": [],
      "summary": "The OWASP Web Security Testing Guide provides a comprehensive framework for testing the security of web applications and web services, covering information gathering, configuration management, identity management, authentication, session management, input validation, error handling, cryptography, business logic, client-side, and API security testing methodologies with practical test cases and remediation guidance.",
      "chapter_count": 12,
      "total_chunks": 150
    }
  ]
}
```

### manifest.compact.json (excerpt)

The compact manifest gives Claude a browsable table of contents with summaries and concept tags per chapter.

```json
{
  "book_id": "owasp-wstg-v42",
  "chapters": [
    {
      "id": "ch07",
      "title": "Authentication Testing",
      "summary": "This chapter covers testing authentication mechanisms including credentials transport, default cred...",
      "concepts": [
        "Token-based authentication",
        "Multi-factor authentication",
        "Credential stuffing"
      ],
      "sections": [
        {
          "id": "ch07-s01",
          "title": "Testing for Credentials Transported over Encrypted Channel",
          "chunks": 1
        },
        {
          "id": "ch07-s02",
          "title": "Testing for Default Credentials",
          "chunks": 1
        },
        {
          "id": "ch07-s03",
          "title": "Testing for Token-Based Authentication",
          "chunks": 2
        },
        {
          "id": "ch07-s04",
          "title": "Testing for Weak Password Policy",
          "chunks": 1
        }
      ]
    },
    {
      "id": "ch08",
      "title": "Session Management Testing",
      "summary": "This chapter covers testing session management controls including cookie attributes, session fixatio...",
      "concepts": [
        "Session fixation",
        "CSRF tokens",
        "JWT rotation",
        "Refresh token rotation"
      ],
      "sections": [
        {
          "id": "ch08-s01",
          "title": "Testing for Session Management Schema",
          "chunks": 2
        },
        {
          "id": "ch08-s02",
          "title": "Testing for Cookie Attributes",
          "chunks": 1
        },
        {
          "id": "ch08-s03",
          "title": "Testing for Session Fixation",
          "chunks": 1
        },
        {
          "id": "ch08-s04",
          "title": "Testing for Cross-Site Request Forgery",
          "chunks": 2
        },
        {
          "id": "ch08-s05",
          "title": "Testing for Refresh Token Rotation",
          "chunks": 2
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
  "Token-Based Authentication": [
    "ch07-s03-001",
    "ch07-s03-002",
    "ch08-s05-001"
  ],
  "Refresh Token Rotation": [
    "ch08-s05-001",
    "ch08-s05-002"
  ],
  "CSRF Tokens": [
    "ch08-s04-001",
    "ch08-s04-002"
  ],
  "JWT Rotation": [
    "ch08-s01-001",
    "ch08-s05-001"
  ],
  "Session Fixation": [
    "ch08-s03-001"
  ],
  "SQL Injection": [
    "ch09-s01-001",
    "ch09-s01-002",
    "ch09-s01-003"
  ],
  "Cross-Site Scripting (XSS)": [
    "ch09-s02-001",
    "ch09-s02-002"
  ]
}
```

### Chunk file: `chunks/ch08-s05-001.md`

Each chunk is a small, self-contained markdown file with structured frontmatter.

```markdown
---
chunk_id: ch08-s05-001
source_id: owasp-wstg-v42
section: Session Management Testing > Testing for Refresh Token Rotation
token_count: 412
---

Refresh token rotation is a security mechanism where each time a refresh token is used to obtain
a new access token, a new refresh token is also issued and the previous one is invalidated. This
limits the window of opportunity for an attacker who has compromised a refresh token.

Testing objectives:
•
Verify that refresh tokens are single-use and invalidated after exchange
•
Verify that reuse of an already-exchanged refresh token triggers revocation of the entire
token family
•
Verify that refresh tokens have a reasonable absolute expiry independent of rotation

How to test:
1. Authenticate and capture the initial refresh token (RT1)
2. Use RT1 to obtain a new access token — the response should include a new refresh token (RT2)
   and RT1 should no longer be valid
3. Attempt to reuse RT1 — the server should reject it and ideally revoke RT2 as well
   (automatic reuse detection)
4. Verify that refresh tokens expire even if continuously rotated (absolute lifetime)

If the application does not implement rotation, an attacker who steals a refresh token has
persistent access until the token's natural expiry, which may be days or weeks.
```

---

## 4. Querying — Example 1: Concept Search Path

**User asks:** "What refresh token rotation strategy does OWASP recommend?"

Here is the exact sequence Claude follows, defined by the `/knowledge` skill:

### Step 1: Check catalog (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/catalog.json`.

Sees `owasp-wstg-v42` with summary mentioning "session management" and "authentication" — relevant.

### Step 2: Search by concept (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/owasp-wstg-v42/concepts.json`.

Scans for "token rotation" and finds:

```json
"Refresh Token Rotation": ["ch08-s05-001", "ch08-s05-002"]
```

Direct hit. Two chunk IDs identified.

### Step 3: Read chunks (2 reads)

Claude reads:
- `chunks/ch08-s05-001.md` — covers the rotation mechanism, testing objectives, and how-to-test steps
- `chunks/ch08-s05-002.md` — covers remediation guidance and implementation patterns

### Step 4: Answer with citation

Claude synthesizes an answer from ~800 tokens of chunk content and cites the source:

> According to the OWASP Web Security Testing Guide (ch08-s05), refresh token rotation requires that each refresh token is single-use. When a refresh token is exchanged for a new access token, a new refresh token must also be issued and the old one invalidated. Critically, if a previously-used refresh token is presented again, the server should revoke the entire token family (automatic reuse detection). Refresh tokens should also have an absolute expiry regardless of rotation.

**Total reads: 4** (catalog + concepts + 2 chunks). Total tokens consumed: ~1,500.

---

## 5. Querying — Example 2: Exploration Path

**User asks:** "What authentication tests does OWASP cover?"

This is a broader question — the user wants an overview, not a specific concept. Claude uses the manifest browsing path.

### Step 1: Check catalog (1 read)

Claude reads `catalog.json`. The OWASP book is relevant.

### Step 2: Browse manifest (1 read)

Claude reads `~/.claude/plugins/agentlib/library/books/owasp-wstg-v42/manifest.compact.json`.

Finds chapter `ch07` titled "Authentication Testing" with this structure:

```
ch07 - Authentication Testing
  ├── ch07-s01 - Testing for Credentials Transported over Encrypted Channel (1 chunk)
  ├── ch07-s02 - Testing for Default Credentials (1 chunk)
  ├── ch07-s03 - Testing for Token-Based Authentication (2 chunks)
  ├── ch07-s04 - Testing for Weak Password Policy (1 chunk)
  ├── ch07-s05 - Testing for Weak Security Question/Answer (1 chunk)
  ├── ch07-s06 - Testing for Brute Force (2 chunks)
  └── ch07-s07 - Testing for Account Lockout (1 chunk)
```

The chapter summary and section titles already answer the question at a high level.

### Step 3: Read selected chunks for detail (2-3 reads)

Claude picks the most relevant sections to flesh out the answer:
- `chunks/ch07-s03-001.md` — token-based auth testing (likely the meatiest)
- `chunks/ch07-s06-001.md` — brute force testing
- `chunks/ch07-s04-001.md` — weak password policy

### Step 4: Answer with citation

Claude provides a structured overview of the seven authentication test categories, with deeper detail on the three it read, all citing specific chunks.

**Total reads: 5-6** (catalog + manifest + 3 chunks). Total tokens consumed: ~3,000.

---

## 6. Token Comparison

| Approach | Tokens consumed | Reads |
|---|---|---|
| Paste full PDF into context | ~250,000 tokens | 1 (but it doesn't fit) |
| Naive RAG (embed + retrieve top-5) | ~2,500 tokens | 1 retrieval call |
| AgentLib — concept search (Example 1) | ~1,500 tokens | 4 reads |
| AgentLib — exploration (Example 2) | ~3,000 tokens | 5-6 reads |

The raw OWASP Testing Guide PDF is ~400 pages. Even at aggressive compression, pasting it would consume ~250k tokens — exceeding most context windows and wasting budget on irrelevant content.

AgentLib's structured navigation keeps total consumption to **1,500-3,000 tokens** by letting Claude decide what to read based on a lightweight table of contents and concept index. The trade-off is a few extra reads (tool calls), but each read is small and targeted.

The key advantage over naive RAG: Claude sees the *structure* of the document (chapter titles, section hierarchy, concept relationships) before deciding what to read. This means it can answer structural questions ("what tests does OWASP cover?") from the manifest alone, without reading any chunks at all.

---

## Summary

```
PDF (400 pages)
    │
    ▼  agentlib ingest
    │
    ├── catalog.json          ← "Is this book relevant?" (~100 tokens)
    ├── manifest.compact.json ← "What chapters/sections exist?" (~2k tokens)
    ├── concepts.json         ← "Where is concept X discussed?" (~1k tokens)
    └── chunks/               ← Actual content, ~300-500 tokens each
         ├── ch07-s03-001.md
         ├── ch08-s05-001.md
         └── ...

Claude reads catalog → picks a path (concept or browse) → reads 2-3 chunks → answers.
Total: 1,500-3,000 tokens instead of 250,000.
```
