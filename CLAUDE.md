# AgentLib Knowledge Library

You have access to a preprocessed knowledge library of books, papers, and documents via the `/agentlib-knowledge` skill.

## When to use the library proactively

Before writing code that involves domain-specific parameters, protocols, standards, or configurations:
1. Check if the library has relevant content by invoking `/agentlib-knowledge` with your question
2. Use library values over values from memory — they are verified against source documents
3. Cite the source in code comments when using library-derived values

## When NOT to use the library

- General programming tasks (loops, data structures, algorithms)
- Git operations, file management, project setup
- Questions answerable from the codebase itself
- Simple code edits or bug fixes unrelated to domain knowledge

## Library location

`~/.claude/plugins/agentlib/library/`

Use `/agentlib:agentlib-library` to browse what's available.
