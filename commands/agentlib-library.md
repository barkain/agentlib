---
description: Show contents of the AgentLib knowledge library
argument-hint: "[book-id]"
---

Show the contents of the AgentLib knowledge library.

If no argument is provided, list all books with their chapter and chunk counts.

If a book ID is provided (`$ARGUMENTS`), show the detailed structure of that book: chapters, sections, concept count, and sample concepts.

Read directly from the library:
- No args: Read ~/.claude/plugins/agentlib/library/books/catalog.json and display as a formatted table
- With book ID: Read ~/.claude/plugins/agentlib/library/books/{book-id}/nav.json and display the chapter structure
