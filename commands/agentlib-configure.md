---
name: agentlib-configure
description: Configure AgentLib settings (API key for book ingestion)
arguments:
  - name: action
    description: "Action: 'set-key <key>', 'clear-key', or empty to show status"
    required: false
---

Configure AgentLib's Anthropic API key for book ingestion (Haiku summarisation).

## Actions

### Show status (no arguments)
Check if the API key is configured. Read `${CLAUDE_PLUGIN_DATA}/.env` and report whether `ANTHROPIC_API_KEY` is set (show first 8 chars + "..." for confirmation, never the full key).

### Set API key: `/agentlib-configure set-key sk-ant-...`
1. Create the directory: `mkdir -p "${CLAUDE_PLUGIN_DATA}"`
2. Read existing `.env` if it exists (preserve other keys)
3. Add or update the `ANTHROPIC_API_KEY=<key>` line
4. Write the file with no quotes around values
5. Set permissions: `chmod 600 "${CLAUDE_PLUGIN_DATA}/.env"`
6. Confirm: "API key configured. Restart the session or run /reload-plugins for the MCP server to pick it up."

### Clear key: `/agentlib-configure clear-key`
1. Remove the `ANTHROPIC_API_KEY` line from `.env`
2. If `.env` is now empty, delete it
3. Confirm: "API key removed."

## Important
- Never log or display the full API key
- The .env file must be chmod 600 (contains credentials)
- Shell environment variables always take precedence over .env values
- Changes require a session restart or /reload-plugins to take effect
