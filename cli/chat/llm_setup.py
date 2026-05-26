"""Interactive LLM setup for chat sessions.

Reuses helpers from cli.utils that the main analysis flow already uses,
but selects the single (provider, model, effort) tuple for chat instead
of separate quick/deep tuples.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, set_key
from rich.console import Console

from tradingagents.llm_clients.api_key_env import get_api_key_env

console = Console()


def _env_key_for_provider(provider: str) -> str | None:
    """Read the API key for `provider` from environment without prompting."""
    if provider == "custom_openai":
        return os.environ.get("CUSTOM_OPENAI_API_KEY")
    if provider == "custom_anthropic":
        return os.environ.get("CUSTOM_ANTHROPIC_API_KEY")
    env_var = get_api_key_env(provider)
    if env_var:
        return os.environ.get(env_var)
    return None  # ollama / unknown — no key needed


def _persist_chat_llm_to_env(provider: str, model: str, effort: str) -> None:
    """Persist the chat LLM triple to {cwd}/.env via dotenv.set_key.

    Mirrors how ensure_api_key() saves API keys, so /model selections
    survive across chat invocations. set_key creates .env if missing.
    """
    env_path = find_dotenv(usecwd=True) or str(Path.cwd() / ".env")
    Path(env_path).touch(exist_ok=True)
    set_key(env_path, "TRADINGAGENTS_CHAT_LLM_PROVIDER", provider)
    set_key(env_path, "TRADINGAGENTS_CHAT_LLM_MODEL", model)
    set_key(env_path, "TRADINGAGENTS_CHAT_LLM_EFFORT", effort or "default")
    console.print(f"[dim]Saved chat LLM selection to {env_path}[/dim]")


def setup_chat_llm_interactive(config: dict, force_interactive: bool = False) -> dict:
    """Walk the user through provider/model/effort/key selection for chat.

    Mutates `config` in place AND returns it, populating:
      - chat_llm_provider
      - chat_llm_model
      - chat_llm_effort
      - llm_api_key   (what _build_chat_kwargs reads)
      - backend_url   (when relevant for custom providers)

    Fast path: if the API key for the currently configured provider is
    already present in the environment, print a one-line summary and skip
    all menus. This covers users who set TRADINGAGENTS_CHAT_LLM_* via
    env vars and have their key in the environment.
    """
    from cli.utils import (
        select_llm_provider,
        ask_qwen_region,
        ask_minimax_region,
        ask_glm_region,
        confirm_ollama_endpoint,
        ensure_api_key,
        get_custom_llm_api_key,
        ask_openai_reasoning_effort,
        ask_anthropic_effort,
        ask_deepseek_reasoning_effort,
        ask_gemini_thinking_config,
    )
    from cli.utils import _select_model

    provider = config.get("chat_llm_provider", "openai")
    model = config.get("chat_llm_model", "gpt-4o")
    effort = config.get("chat_llm_effort", "default")

    key = _env_key_for_provider(provider)

    # Fast path: key already available (or provider needs no key, e.g. ollama)
    if not force_interactive and (key is not None or provider == "ollama"):
        effort_display = effort if effort and effort != "default" else "default"
        console.print(
            f"[dim]Using configured chat LLM: {provider}/{model} "
            f"(effort={effort_display})[/dim]"
        )
        if key:
            config["llm_api_key"] = key
        return config

    # Slow path: interactive selection
    provider, backend_url = select_llm_provider()

    # Secondary regional selection for multi-endpoint providers
    if provider == "qwen":
        provider, backend_url = ask_qwen_region()
    elif provider == "minimax":
        provider, backend_url = ask_minimax_region()
    elif provider == "glm":
        provider, backend_url = ask_glm_region()

    if provider == "ollama":
        confirm_ollama_endpoint(backend_url)

    # Obtain API key
    if provider in ("custom_openai", "custom_anthropic"):
        key = get_custom_llm_api_key(provider)
    else:
        key = ensure_api_key(provider)

    # Select model
    model = _select_model(provider, "chat")

    # Select effort (provider-specific)
    provider_lower = provider.lower()
    effort = ""
    if provider_lower in ("openai", "custom_openai"):
        effort = ask_openai_reasoning_effort() or ""
    elif provider_lower in ("anthropic", "custom_anthropic"):
        effort = ask_anthropic_effort() or ""
    elif provider_lower == "deepseek":
        effort = ask_deepseek_reasoning_effort() or ""
    elif provider_lower == "google":
        effort = ask_gemini_thinking_config() or ""

    config["chat_llm_provider"] = provider
    config["chat_llm_model"] = model
    config["chat_llm_effort"] = effort
    if backend_url:
        config["backend_url"] = backend_url
    if key:
        config["llm_api_key"] = key

    _persist_chat_llm_to_env(provider, model, effort)

    return config
