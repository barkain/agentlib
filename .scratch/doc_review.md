# AgentLib Documentation Review

## Summary

The documentation is generally well-written and the README is compelling. However, there are **critical stale references** to the old MCP server architecture in two command files and one configure file, contradicting the zero-server story told by the README, SKILL.md, and plugin.json. These must be fixed to avoid confusing both users and the agent itself.

---

## CRITICAL Issues

### 1. `commands/agentlib-ingest-book.md` lines 22-26: Stale MCP tool references

**Problem:** After describing ingestion, the file says:

```
After ingestion, the book's content will be available through the AgentLib MCP tools:
- `browse_library` to see it in the catalog
- `open_book` to view its chapter structure
- `read_chunks` to access specific content
- `search_concepts` to find concepts across the library
```

This directly contradicts the zero-server, skill-only architecture. The README explicitly says "No MCP server. No tool calls." These old tool names (`browse_library`, `open_book`, `read_chunks`, `search_concepts`) are from `server.py` which still exists but is NOT the primary interface.

**Fix:** Replace lines 22-26 with:

```markdown
After ingestion, the book is available in the library at `~/.claude/plugins/agentlib/library/books/`. The agent navigates it via the `agentlib:knowledge` skill by reading:
- `catalog.json` to discover the book
- `manifest.compact.json` to browse its structure
- `concepts.json` to search by concept
- `chunks/*.md` to read specific content
```

### 2. `commands/agentlib-library.md` lines 12-14: Stale MCP tool references

**Problem:** The file instructs:

```
Use the AgentLib MCP tools:
- No args: call `browse_library` and display results as a formatted table
- With book ID: call `open_book` with that ID and display the chapter structure
```

This tells the agent to call MCP tools that are not the primary interface.

**Fix:** Replace lines 12-14 with:

```markdown
Read directly from the library:
- No args: Read `~/.claude/plugins/agentlib/library/books/catalog.json` and display as a formatted table
- With book ID: Read `~/.claude/plugins/agentlib/library/books/{book-id}/manifest.compact.json` and display the chapter structure
```

### 3. `commands/agentlib-configure.md` line 35: MCP server reference

**Problem:** The confirmation message says:

```
"API key configured for <provider>. Restart the session or run /reload-plugins for the MCP server to pick it up."
```

References "MCP server" which contradicts the zero-server architecture.

**Fix:** Change to:

```
"API key configured for <provider>. This will be used for the next ingestion."
```

### 4. `commands/agentlib-configure.md` line 64: Another MCP reference

**Problem:** Says "Changes require a session restart or /reload-plugins to take effect" -- implying a server process needs restarting.

**Fix:** Change to: "Changes take effect on the next ingestion run." (API keys are only used during ingestion, not during navigation which is just file reads.)

---

## IMPORTANT Issues

### 5. `commands/agentlib-ingest-book.md` line 18: Hardcodes "Claude Haiku"

**Problem:** Says "Summarise each chapter using Claude Haiku" but the system supports 5 providers. If a user configured OpenAI, this description is wrong.

**Fix:** Change to: "Summarise each chapter using the configured LLM provider"

### 6. `marketplace.json` line 12: Understates reduction percentage

**Problem:** The description says "47% fewer tokens vs raw PDF" but the README's headline result is 82% reduction. The 47% is the lower-bound result. Using the weaker number in marketing copy undersells the product.

**Fix:** Change to: "47-82% fewer tokens vs raw PDF" or lead with the stronger number: "Up to 82% fewer tokens vs raw PDF."

### 7. `SKILL.md` line 39: Contradicts "Max 4 file reads" with "Max 10 chunks"

**Problem:** Line 35 says "Max 10 chunks per question" but line 39 says "Max 4 file reads per question." Reading 10 chunks would require at least 10 file reads (one per chunk file), plus catalog/manifest reads. These two limits are contradictory.

**Fix:** Either:
- Remove "Max 10 chunks" (the 4-read limit is the real constraint), or
- Clarify: "Max 4 navigation reads per question (catalog + manifest + concepts). Then read up to 3-4 chunks as needed." The total would be ~6-8 reads which seems reasonable.

### 8. `SKILL.md` description line (frontmatter): Skill trigger scope

**Problem:** The trigger description mentions "SBOM, CycloneDX" as trigger words. These are specific to one particular test book and should not be hardcoded in the general skill definition. As more books are ingested, this list would need constant updating.

**Fix:** Remove the specific domain references: "SBOM, CycloneDX" from the trigger description. The generic triggers ("research questions, book references, domain knowledge queries, 'according to', 'what does the book say'") are sufficient.

### 9. No NAVIGATION.md exists

**Problem:** The README shows `NAVIGATION.md` at the top of the library structure (line 37), but no such file was found at `~/.claude/plugins/agentlib/library/NAVIGATION.md` or anywhere in the repo. If it is meant to be generated during ingestion, it is either not implemented or the path in README is aspirational.

**Fix:** Either implement NAVIGATION.md generation during ingestion, or remove it from the README's directory tree diagram.

---

## NICE-TO-HAVE Issues

### 10. `README.md` line 3: Hero image may not exist

**Problem:** References `assets/hero.png` but this file's existence was not verified. If the repo is published without it, the README will show a broken image.

**Suggestion:** Verify the image exists or add a text-only fallback.

### 11. `README.md` line 93: Installation via marketplace may not work yet

**Problem:** Shows `/plugin marketplace add barkain/agentlib` and `/plugin install agentlib` as installation instructions. If the Claude Code plugin marketplace is not yet live or the plugin is not yet published, these instructions will fail for users.

**Suggestion:** Add a manual installation alternative:

```bash
# Manual installation
git clone https://github.com/barkain/agentlib.git ~/.claude/plugins/agentlib
```

### 12. `plugin.json`: Missing fields that might be expected

**Problem:** The plugin.json is minimal (name, version, description, author). Depending on the Claude Code plugin spec, it may need additional fields like `skills`, `commands`, or `entry_point` to be properly discovered.

**Suggestion:** Verify against the actual Claude Code plugin specification.

### 13. `README.md` line 105: Skill reference format

**Problem:** The README says "the `/agentlib` skill" but the actual skill is at `skills/knowledge/SKILL.md`. The canonical skill name in Claude Code plugin format would be `agentlib:knowledge`. The `/agentlib` notation is ambiguous -- it could be confused with a slash command.

**Fix:** Clarify: "the `agentlib:knowledge` skill" or at minimum "the AgentLib knowledge skill."

### 14. `README.md`: No mention of `server.py` existence or its role

**Problem:** `server.py` exists in the repo with full MCP tool implementations. The README says "No MCP server" but the file is there. This could confuse contributors.

**Suggestion:** Either (a) add a brief note in a Development section that `server.py` exists for benchmarking/legacy purposes, or (b) move it to `benchmark/` if it is only used there.

### 15. `SKILL.md` line 38: "NEVER manifest.json" implies a file that shouldn't exist

**Problem:** The rule "ALWAYS use `manifest.compact.json`, NEVER `manifest.json`" implies both files exist in the output. If `manifest.json` is also generated, consider either not generating it or documenting why it exists (perhaps for debugging).

**Suggestion:** Clarify in the ingestion docs why both exist, or stop generating `manifest.json` if agents should never read it.

---

## Consistency Matrix

| Aspect | README | SKILL.md | ingest-book.md | configure.md | library.md | plugin.json | marketplace.json |
|--------|--------|----------|----------------|--------------|------------|-------------|------------------|
| Zero-server | Yes | Yes | **NO (MCP tools)** | **NO (MCP server)** | **NO (MCP tools)** | Yes | Yes |
| Skill-based nav | Yes | Yes | No mention | N/A | No mention | Yes | N/A |
| Multi-provider | Yes | N/A | **Hardcodes Haiku** | Yes | N/A | N/A | N/A |
| Token reduction | 82% | N/A | N/A | N/A | N/A | N/A | 47% |
| Library path | Correct | Correct | N/A | Correct | N/A | N/A | N/A |

---

## Priority Action Items

1. **Fix 3 command files** (agentlib-ingest-book.md, agentlib-library.md, agentlib-configure.md) to remove all MCP/tool references -- this is the single most impactful change
2. **Fix marketplace.json** description to use the stronger reduction number
3. **Resolve SKILL.md** contradictory read limits
4. **Remove hardcoded domain terms** (SBOM, CycloneDX) from SKILL.md trigger
5. **Implement or remove** NAVIGATION.md from README diagram
6. **Clarify skill name** as `agentlib:knowledge` in README
