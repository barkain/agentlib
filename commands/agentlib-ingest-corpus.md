---
description: Ingest a folder of scientific papers (PDFs) into the AgentLib library as a corpus
argument-hint: "<folder-path> [--corpus-id <id>]"
---

Ingest all PDF files in the folder at `$ARGUMENTS` into the AgentLib library as a paper corpus.

Run the ingestion pipeline:
```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python preprocessing/corpus.py $ARGUMENTS
```

This will:
1. Extract metadata from each paper (title, authors, abstract)
2. Parse and chunk each paper into 300-500 token segments
3. Summarise each paper's sections using the configured LLM provider
4. Cluster papers by topic
5. Build a cross-paper concept index with pattern fingerprints
6. Update the unified library_index.json and pattern_index.json

After ingestion, use `/agentlib-knowledge` to query the corpus. The agent can discover connections between corpus papers and ingested books through shared pattern fingerprints.
