# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents is a multi-agent LLM financial trading framework built on LangGraph. It simulates a trading firm with specialized agents (analysts, researchers, traders, risk managers) that collaborate through structured debate to produce trading decisions. Decisions are one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.

## Build & Run Commands

```bash
# Install (editable mode for development)
pip install -e .

# Run CLI
tradingagents
# or from source:
python -m cli.main

# Run a single trading analysis programmatically
python main.py

# Docker
cp .env.example .env  # fill in API keys
docker compose run --rm tradingagents

# Docker with local Ollama models
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required Environment Variables

Set the API key for your chosen LLM provider (at least one required):
`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY` (Qwen), `ZHIPU_API_KEY` (GLM), `OPENROUTER_API_KEY`

For Alpha Vantage data (optional, yfinance is default): `ALPHA_VANTAGE_API_KEY`

Or copy `.env.example` to `.env` and fill in keys.

No test suite runner exists. The test files in `tests/` are ad-hoc API key validation scripts, not unit tests.

## Architecture

### Agent Pipeline (LangGraph StateGraph)

The core execution flows through a compiled LangGraph `StateGraph` defined in `tradingagents/graph/setup.py`:

```
START → Analyst Team (parallel-optional) → Researcher Debate → Trader → Risk Debate → Portfolio Manager → END
```

1. **Analyst Team** (`tradingagents/agents/analysts/`): Market, Social, News, Fundamentals analysts run sequentially. Each calls tools via LangGraph `ToolNode`, then a "Msg Clear" node resets messages for the next analyst. Selectable via `selected_analysts` parameter.

2. **Researcher Debate** (`tradingagents/agents/researchers/`): Bull vs Bear researchers alternate for `max_debate_rounds` rounds. Research Manager (judge) resolves.

3. **Trader** (`tradingagents/agents/trader/`): Composes debate outcomes into an investment plan.

4. **Risk Debate** (`tradingagents/agents/risk_mgmt/`): Aggressive, Conservative, Neutral debators rotate for `max_risk_discuss_rounds` rounds.

5. **Portfolio Manager** (`tradingagents/agents/managers/portfolio_manager.py`): Makes final decision.

State flows through `AgentState` (extends LangGraph `MessagesState`) in `tradingagents/agents/utils/agent_states.py`.

### Data Layer

- **Tool definitions**: `tradingagents/agents/utils/{core_stock_tools,technical_indicators_tools,fundamental_data_tools,news_data_tools}.py` — LangChain `@tool` functions that call `route_to_vendor()`.
- **Vendor routing**: `tradingagents/dataflows/interface.py` — `route_to_vendor()` dispatches to yfinance, Alpha Vantage, or CCXT based on config. Supports comma-separated fallback chains and automatic fallback on `AlphaVantageRateLimitError`.
- **Vendor implementations**: `tradingagents/dataflows/y_finance.py` and `tradingagents/dataflows/alpha_vantage_*.py`.
- **CCXT vendor**: `tradingagents/dataflows/ccxt_data.py` — crypto exchange data (default: OKX). Only registered for `get_stock_data` and `get_indicators`; fundamentals/news stay on other vendors. Reads `ccxt_symbol` from config to override the `symbol` arg transparently.
- **Config routing**: `tradingagents/dataflows/config.py` holds a module-level config singleton; tool-level `tool_vendors` overrides category-level `data_vendors`.

### LLM Client Layer

- **Factory**: `tradingagents/llm_clients/factory.py` — `create_llm_client(provider, model)` returns a `BaseLLMClient`.
- **OpenAI-compatible**: OpenAI, xAI, DeepSeek, Qwen, GLM, Ollama, OpenRouter all route through `OpenAIClient` with provider-specific base URLs.
- **Native clients**: `AnthropicClient`, `GoogleClient`, `AzureOpenAIClient` use their respective LangChain integrations.
- **Model catalog**: `tradingagents/llm_clients/model_catalog.py` — `MODEL_OPTIONS` dict drives CLI model selection menus.

### Memory / Reflection System

- `FinancialSituationMemory` (`tradingagents/agents/utils/memory.py`) uses BM25 (not embeddings) for offline similarity matching.
- `Reflector` (`tradingagents/graph/reflection.py`) generates post-hoc reflections on each agent's decisions and stores them as (situation, recommendation) pairs.
- Memory instances: bull, bear, trader, invest_judge, portfolio_manager — each updated independently via `reflect_and_remember(returns)`.

### Signal Processing

`SignalProcessor` (`tradingagents/graph/signal_processing.py`) extracts the final 5-tier rating from the Portfolio Manager's verbose decision text.

## Key Configuration

`tradingagents/default_config.py` defines `DEFAULT_CONFIG`. Key fields:
- Defaults: `llm_provider="openai"`, `deep_think_llm="gpt-5.4"`, `quick_think_llm="gpt-5.4-mini"`
- `llm_provider`, `deep_think_llm`, `quick_think_llm` — provider and model selection
- `max_debate_rounds`, `max_risk_discuss_rounds` — debate depth
- `data_vendors` / `tool_vendors` — per-category or per-tool data source routing
- `ccxt_exchange` / `ccxt_symbol` — CCXT exchange id (default "okx") and trading pair (e.g. "BTC/USDT"); `ccxt_symbol` overrides the `symbol` arg in CCXT vendor functions
- `output_language` — non-English output for user-facing agents (debate stays English)
- Provider-specific kwargs: `google_thinking_level`, `openai_reasoning_effort`, `anthropic_effort`
- `backend_url` — custom endpoint for OpenAI-compatible providers (self-hosted, proxies)
- Cache/logs default to `~/.tradingagents/`

### Python API Quick Start

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4-mini"

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)  # One of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL
```

## Key Patterns

### Gotchas & Non-Obvious Behaviors

- Agent creation functions follow the pattern `create_X_analyst(llm, memory=None) -> function` — they return a callable node function, not a class.
- `create_msg_delete()` returns a state-cleaning function used between analysts to reset the message history.
- `ConditionalLogic` methods on `state["messages"][-1].tool_calls` determine if an analyst needs more tool calls or should proceed.
- Debate round counting: investment debate uses `2 * max_debate_rounds` (2 agents), risk debate uses `3 * max_risk_discuss_rounds` (3 agents).
- `tool_vendors` overrides `data_vendors` — tool-level config takes precedence over category-level.
- `output_language` only affects user-facing outputs (analyst reports, final decision); internal agent debate always stays English.
- `SignalProcessor` uses `quick_thinking_llm` (not regex) to extract the 5-tier rating from verbose text.
- Memory uses BM25 (offline, no API calls) — no embedding model needed.
- `TradingAgentsGraph.__init__` calls `set_config()` on the dataflows interface, so config changes after init won't propagate to data routing.
- CCXT vendor reads `ccxt_symbol` from config (not the `symbol` function arg) — programmatic users must set `config["ccxt_symbol"]` when using CCXT, or the raw ticker will be passed to the exchange (likely invalid).
- CCXT cache key (`{symbol}-CCXT-data-{dates}.csv`) does not include exchange name — switching `ccxt_exchange` requires cache cleanup to avoid stale data.
- Adding new CLI steps requires manual renumbering of all subsequent steps (step numbers are hardcoded strings in `cli/main.py`).
