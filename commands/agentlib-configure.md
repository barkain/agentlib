---
name: agentlib-configure
description: Configure AgentLib settings (LLM provider API keys for book ingestion)
arguments:
  - name: action
    description: "Action: 'set-key <key>', 'clear-key [provider]', or empty to show status"
    required: false
---

Configure AgentLib's LLM provider API keys for book ingestion (summarisation).

Supported providers: Anthropic (Claude), OpenAI (GPT), xAI (Grok), Google (Gemini), DeepSeek.

## Actions

### Show status (no arguments)
Check which providers are configured. Read `${CLAUDE_PLUGIN_DATA}/.env` and report:
- Which API keys are set (show first 8 chars + "..." for each, never the full key)
- Which provider is currently active (based on `AGENTLIB_PROVIDER` or auto-detection order)
- Current model override if `AGENTLIB_MODEL` is set

Auto-detection priority: Anthropic > OpenAI > xAI > Google > DeepSeek.

### Set API key: `/agentlib-configure set-key <key>`
1. Auto-detect the provider from the key prefix:
   - `sk-ant-` -> ANTHROPIC_API_KEY
   - `sk-` (other) -> OPENAI_API_KEY
   - `xai-` -> XAI_API_KEY
   - `gsk_` or starts with `AI` -> GOOGLE_API_KEY
   - `sk-` with no other match -> ask the user which provider
   - Other -> ask the user which provider (anthropic, openai, xai, google, deepseek)
2. Create the directory: `mkdir -p "${CLAUDE_PLUGIN_DATA}"`
3. Read existing `.env` if it exists (preserve other keys)
4. Add or update the appropriate `<PROVIDER>_API_KEY=<key>` line
5. Write the file with no quotes around values
6. Set permissions: `chmod 600 "${CLAUDE_PLUGIN_DATA}/.env"`
7. Confirm: "API key configured for <provider>. Restart the session or run /reload-plugins for the MCP server to pick it up."

### Clear key: `/agentlib-configure clear-key [provider]`
1. If provider is specified, remove that provider's API key line from `.env`
2. If no provider specified, ask which key to remove
3. If `.env` is now empty, delete it
4. Confirm: "<Provider> API key removed."

### Set provider override: `/agentlib-configure set-provider <provider>`
1. Set `AGENTLIB_PROVIDER=<provider>` in `.env` (one of: anthropic, openai, xai, google, deepseek)
2. This overrides auto-detection order

### Set model override: `/agentlib-configure set-model <model>`
1. Set `AGENTLIB_MODEL=<model>` in `.env`
2. This overrides the default model for the active provider

## Environment variables
- `ANTHROPIC_API_KEY` - Anthropic (Claude) API key
- `OPENAI_API_KEY` - OpenAI API key
- `XAI_API_KEY` - xAI (Grok) API key
- `GOOGLE_API_KEY` - Google (Gemini) API key
- `DEEPSEEK_API_KEY` - DeepSeek API key
- `AGENTLIB_PROVIDER` - Override auto-detection (anthropic|openai|xai|google|deepseek)
- `AGENTLIB_MODEL` - Override default model for active provider

## Important
- Never log or display the full API key
- The .env file must be chmod 600 (contains credentials)
- Shell environment variables always take precedence over .env values
- Changes require a session restart or /reload-plugins to take effect
