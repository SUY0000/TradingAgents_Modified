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
- `output_language` 覆盖范围：产生用户可见字段的节点需调用 `get_language_instruction()`——4个analysts、`research_manager`（`investment_plan`）、`trader`（`trader_investment_plan`）、`portfolio_manager`；纯辩论节点（bull/bear researchers、risk debators）按设计保持英语，不加此调用。
- `SignalProcessor` uses `quick_thinking_llm` (not regex) to extract the 5-tier rating from verbose text.
- Memory uses BM25 (offline, no API calls) — no embedding model needed.
- `TradingAgentsGraph.__init__` calls `set_config()` on the dataflows interface, so config changes after init won't propagate to data routing.
- CCXT vendor reads `ccxt_symbol` from config (not the `symbol` function arg) — programmatic users must set `config["ccxt_symbol"]` when using CCXT, or the raw ticker will be passed to the exchange (likely invalid).
- CCXT cache key (`{symbol}-CCXT-data-{dates}.csv`) does not include exchange name — switching `ccxt_exchange` requires cache cleanup to avoid stale data.
- Adding new CLI steps requires manual renumbering of all subsequent steps (step numbers are hardcoded strings in `cli/main.py`).
- OKX rubik contracts stat 端点（`/api/v5/rubik/stat/contracts/*`）大多数需要 `instId`（如 `BTC-USDT-SWAP`），而非 `ccy`（如 `BTC`）。例外：`/open-interest-volume` 和 `/option/open-interest-volume-ratio` 使用 `ccy`。文档看似通用，但实际测试中 `ccy` 会返回 `"instId can't be empty"` 400 错误。
- OKX `/rubik/stat/contracts/open-interest-history` 响应为 4 字段数组：`[ts, oi, oiCcy, oiUsd]`，不是 3 字段。
- OKX crypto market 数据层：`okx_data.py` 用 `requests` 库直接调 REST API（rubik stat 端点不在 CCXT unified API 中）；`crypto_market_tools.py` 封装为 LangChain tools；`market_analyst.py` 通过 `is_crypto` 检测（`core_stock_apis == "ccxt"` **且** `technical_indicators == "ccxt"`）条件加载这些工具，与 CLI 同时赋值两个 vendor 的行为保持一致。
- LangGraph analyst 工具双注册要求：给 analyst 添加工具时必须同时更新两处——(1) analyst 文件内 `llm.bind_tools(tools)`（告诉 LLM 有哪些工具）；(2) `trading_graph.py` `_create_tool_nodes()` 里的 `ToolNode([...])`（决定哪些工具能实际执行）。只更新前者会导致 LLM 发起工具调用但 ToolNode 找不到该工具，静默失败。
- `config.py` 的 `set_config()` 对嵌套 dict（如 `data_vendors`）做深合并而非整体替换；`initialize_config()` 使用 `deepcopy`，`DEFAULT_CONFIG` 不会通过浅拷贝被外部代码意外修改。
- 所有 analyst（market/news/social/fundamentals）均使用 completion-gate 风格的 system prompt（而非通用多智能体 boilerplate），明确禁止在所有工具调用完成前输出报告。通用 boilerplate 中的 "another assistant will help where you left off" 措辞会削弱 MANDATORY 工具指令的约束力，不应用于任何有强制工具要求的节点。
- `get_news(ticker, ...)` 底层两个实现（yfinance: `yf.Ticker(ticker).get_news()`；Alpha Vantage: `params={"tickers": ticker}`）均为严格 ticker-based，不支持自由文本查询词。设计 news/sentiment analyst prompt 时不可要求 LLM 传入 CEO 名、情绪词等作为查询参数。
- `get_indicators` 的 `indicator` 参数支持逗号分隔多个指标（实现内部 split 处理）。设计 prompt 时应引导 LLM 每个 timeframe 一次传入所有指标，避免逐个调用（4 TF × 8 指标 = 32 次 → 4 次）。
- Risk debators（aggressive/conservative/neutral）通过 `state.get("investment_plan", "")` 可获取 research_manager 的原始投资计划；`state["trader_investment_plan"]` 是 trader 的执行决策。两者都是 risk debate 的有效上下文输入。

### Development Workflow

- **Python 环境**: 项目使用 conda 环境 `tradingagents`。运行 Python 代码需先激活 `conda activate tradingagents`，直接使用 `python` 会因缺少依赖（ccxt 等）而失败。
- **RTK工具使用**: 项目配置了RTK (Rust Token Killer)用于token优化。使用`rtk read`、`rtk grep`、`rtk find`代替内置的Read、Grep、Glob工具以节省token。
- **Edit 工具前置要求**: 调用 `Edit` 前必须用 `Read` 工具（非 `rtk read`）读取目标文件，否则报 "File has not been read yet" 错误；`rtk read` 不满足此前置条件。
- **供应商参数传递**: 供应商实现使用`**kwargs`接受额外参数，确保向后兼容。新参数可安全添加到工具层，非相关供应商会忽略这些参数。
- **工具层修改模式**: 修改工具函数时，添加参数并通过`route_to_vendor()`传递。CCXT支持`timeframe`参数用于多时间周期数据获取。
- **测试结构**: `tests/`目录包含测试模板和fixtures，但无完整测试运行器。参考`test_ccxt_data_template.py`作为测试模板。
- **OKX REST API smoke test**: 用 `os.environ['TRADINGAGENTS_CACHE_DIR'] = '/tmp/okx_test_cache'` 隔离测试缓存，避免污染 `~/.tradingagents/cache/`。
- **CLI 函数分工**: `select_*` 交互选择函数放 `cli/utils.py`（questionary）；简单文本输入 `get_*` 放 `cli/main.py`（`typer.prompt`）；`create_question_box()` 提供展示框，prompt 函数只做裸输入。`main.py` 中的 `get_ticker`/`get_analysis_date` 本地定义有意覆盖 `from cli.utils import *` 导入的同名函数。
- **`data_vendors` 键名**: 精确键名为 `core_stock_apis`、`technical_indicators`、`news_data`、`fundamental_data`、`crypto_market_data`；误用 `news`/`fundamentals` 等错误键名会静默无效（`set_config()` 深合并不报错）。
- **加密货币双 ticker 约定**: CLI 加密模式同时采集两个 ticker——yfinance 格式（如 `BTC-USD`，用于新闻/基本面，同时作为 `propagate()` 的主 ticker）与 CCXT 格式（如 `BTC/USDT`，写入 `config["ccxt_symbol"]`，用于行情/技术面）。
