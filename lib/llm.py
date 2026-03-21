"""Unified LLM client for multiple providers."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: str       # anthropic | openai | xai | google | deepseek
    model: str          # model identifier
    api_key: str | None = None  # None = read from env
    base_url: str | None = None  # None = provider default


# Provider defaults: (env_var_for_key, base_url, default_model)
PROVIDERS: dict[str, dict[str, str]] = {
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": "",  # uses anthropic SDK, not openai
        "default_model": "claude-haiku-4-5-20251001",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "xai": {
        "env_key": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3-mini",
    },
    "google": {
        "env_key": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
}


def detect_provider() -> LLMConfig:
    """Auto-detect which provider to use based on available API keys.

    Checks env vars in order: AGENTLIB_PROVIDER (explicit override),
    then checks for API keys in order of preference.

    Returns:
        LLMConfig for the first available provider.

    Raises:
        ValueError if no API key is found for any provider.
    """
    # Explicit override
    explicit = os.environ.get("AGENTLIB_PROVIDER", "").lower()
    if explicit and explicit in PROVIDERS:
        p = PROVIDERS[explicit]
        api_key = os.environ.get(p["env_key"])
        if api_key:
            return LLMConfig(
                provider=explicit,
                model=os.environ.get("AGENTLIB_MODEL", p["default_model"]),
                api_key=api_key,
                base_url=p["base_url"] or None,
            )

    # Auto-detect by checking API keys in preference order
    for name, p in PROVIDERS.items():
        api_key = os.environ.get(p["env_key"])
        # For Anthropic, also accept CLAUDE_CODE_OAUTH_TOKEN (Claude Code env)
        if not api_key and name == "anthropic":
            api_key = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if api_key:
            return LLMConfig(
                provider=name,
                model=os.environ.get("AGENTLIB_MODEL", p["default_model"]),
                api_key=api_key,
                base_url=p["base_url"] or None,
            )

    raise ValueError(
        "No LLM API key found. Set one of: "
        + ", ".join(p["env_key"] for p in PROVIDERS.values())
        + "\nOr configure via: /agentlib-configure set-key <key>"
    )


def call_llm(config: LLMConfig, prompt: str, max_tokens: int = 1024) -> str:
    """Call an LLM with a simple prompt, return the text response.

    Uses the Anthropic SDK for Anthropic, OpenAI SDK for everything else.
    """
    if config.provider == "anthropic":
        return _call_anthropic(config, prompt, max_tokens)
    else:
        return _call_openai_compat(config, prompt, max_tokens)


def _call_anthropic(config: LLMConfig, prompt: str, max_tokens: int) -> str:
    """Call Anthropic API via their SDK."""
    import anthropic  # type: ignore[import-untyped]

    client = anthropic.Anthropic(api_key=config.api_key)
    response = client.messages.create(
        model=config.model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _call_openai_compat(config: LLMConfig, prompt: str, max_tokens: int) -> str:
    """Call OpenAI-compatible API (works for OpenAI, xAI, Google, DeepSeek)."""
    from openai import OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    response = client.chat.completions.create(
        model=config.model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
