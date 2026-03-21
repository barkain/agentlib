---
description: Show contents of the AgentLib knowledge library
argument-hint: "[book-id]"
---

Show the contents of the AgentLib knowledge library.

If no argument is provided, list all books with their chapter and chunk counts.

If a book ID is provided (`$ARGUMENTS`), show the detailed structure of that book: chapters, sections, concept count, and sample concepts.

Use the AgentLib MCP tools:
- No args: call `browse_library` and display results as a formatted table
- With book ID: call `open_book` with that ID and display the chapter structure
