# CLAUDE.md

TradingAgents is a LangGraph-based multi-agent trading framework. Agents produce one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.

## Fork / Worktree Rules

This fork uses two worktrees:

```text
TradingAgents_Modified/        # development worktree: edit code, git commit/rebase/push
TradingAgents_Modified_Build/  # build/install worktree: detached HEAD, no source edits
```

Hard rules:
- Run `git worktree list` before code changes; edit only in the development worktree.
- Do not run install/build commands in the development worktree.
- Build worktree must stay detached: `git switch --detach FETCH_HEAD`.
- Never push to `upstream`; `origin` is the fork, `upstream` is read-only source.
- Rebase force-push only with `--force-with-lease`; never `--force`.
- Do not commit untracked local artifacts (`.DS_Store`, `plan/`, `reports/`, build outputs).

Sync build worktree after committing in development:

```bash
git -C "/Users/suy/Documents/编程/TradingAgents_Modified_Build" fetch . <branch>
git -C "/Users/suy/Documents/编程/TradingAgents_Modified_Build" switch --detach FETCH_HEAD
```

Upstream sync flow from development worktree:

```bash
git fetch upstream
git checkout main
git merge --ff-only upstream/main
git push origin main
git checkout <feature-branch>
git rebase main
git push --force-with-lease origin <feature-branch>
```

## Commands

```bash
pip install -e .                    # install editable package
tradingagents                       # run CLI
python -m cli.main                  # run CLI from source
python main.py                      # run single analysis example
python -m compileall -f -q tradingagents/agents  # prompt/agent syntax check
python tests/test_akshare_smoke.py  # ad-hoc akshare API drift smoke test
```

There is no normal unit-test suite; files under `tests/` are mostly ad-hoc/API-key smoke scripts.

Known upstream warning: `python -m compileall -f -q tradingagents cli` reports `cli/utils.py` invalid escape sequence around ``\`OLLAMA_BASE_URL\``; this is upstream v0.2.5 behavior.

## Architecture

Core graph: `tradingagents/graph/setup.py`

```text
START → Analysts → Bull/Bear Research Debate → Research Manager → Trader → Risk Debate → Portfolio Manager → END
```

Analysts run sequentially: Market, Sentiment (`selected_analysts` key remains `"social"`), News, Fundamentals. Market/News/Fundamentals use LangGraph `ToolNode`; Sentiment prefetches data inside the agent (all three asset paths) and then goes directly to `Msg Clear Social`.

Key files:
- `tradingagents/graph/trading_graph.py` — graph orchestration, LLM clients, tool nodes, reflection/benchmark flow.
- `tradingagents/graph/setup.py` — LangGraph node/edge wiring.
- `tradingagents/graph/conditional_logic.py` — tool-call and debate loop routing.
- `tradingagents/agents/utils/agent_states.py` — graph state schema.
- `tradingagents/agents/utils/agent_utils.py` — shared tools, language instruction, asset-type prompt context.
- `tradingagents/dataflows/interface.py` — `route_to_vendor()` and vendor/category registry.
- `tradingagents/default_config.py` — config defaults and `TRADINGAGENTS_*` env overrides.
- `tradingagents/llm_clients/factory.py` — provider routing.

## Config / Data Routing

Important config keys:
- `data_vendors`: `core_stock_apis`, `technical_indicators`, `news_data`, `fundamental_data`, `crypto_market_data`, `cn_market_data`, `cn_sentiment_data`.
- `tool_vendors` overrides `data_vendors` per tool.
- `set_config()` deep-merges nested dicts; `TradingAgentsGraph.__init__` calls `set_config()`, so config changes after graph init do not affect routing.
- `ccxt_symbol` overrides the ticker arg for CCXT/OKX market data.
- `benchmark_ticker` overrides `benchmark_map`; otherwise reflection alpha benchmark is selected by ticker suffix.
- `output_language` is applied by `get_language_instruction()` to analysts, researchers, risk debators, Research Manager, Trader, and Portfolio Manager.

Asset type helper:
- Use `agent_utils.get_asset_type()` / `get_asset_prompt_context()` for stock/A股/crypto detection; do not duplicate `data_vendors` checks in agents.
- A-share mode: `core_stock_apis == "akshare"` and `technical_indicators == "akshare"`.
- Crypto mode: `core_stock_apis == "ccxt"` and `technical_indicators == "ccxt"`.

## Agent / Prompt Rules

Pipeline responsibility boundary:
- Analysts: describe objective evidence only; no entry/stop/sizing/trade recommendation.
- Bull/Bear Researchers: argue evidence quality/direction; do not compute entry/exit targets or risk/reward ratios.
- Research Manager: synthesize debate into a directional research brief; no concrete sizing.
- Trader: translate Research Manager brief into execution parameters.
- Risk Debators: debate risk parameters only; do not redefine investment direction or targets.
- Portfolio Manager: only final decision authority.

Prompt patterns:
- Agent factories return callable node functions, not classes: `create_X(llm) -> node`.
- Analyst tool-calling outer template should stay: `"Tools available: {tool_names}.\n\n{system_message}\n\nCurrent date: {current_date}. {instrument_context}"`.
- Completion gate is code-level: `if len(result.tool_calls) == 0: report = result.content`.
- Avoid generic multi-agent boilerplate like “another assistant will help where you left off”; it weakens mandatory tool behavior.
- `get_news(ticker, ...)` is strict ticker-based, not free-text search; prompts must not ask for CEO names or sentiment keywords as query strings.
- `get_indicators(indicator=...)` accepts comma-separated indicators; prompt should request one call per timeframe, not one call per indicator.
- `sentiment_analyst.py` has no ToolNode: it prefetches data and makes one LLM call across all three asset paths (US stock = yfinance+StockTwits+Reddit; A-share = 3-layer akshare; crypto = F&G + CoinGecko votes). `trading_graph._create_tool_nodes()` must not register `social`. `crypto_sentiment_tools.py` exposes `get_crypto_smart_money` / `get_crypto_margin_leverage` as `@tool`s but they are not currently bound to any analyst — either wire them in or treat as dead code.
- market/news/fundamentals/sentiment prompts are split by stock/A股/crypto; update the relevant `_build_*system_message()` branch instead of mixing all assets into one long prompt.

Prompt/graph smoke test: after editing asset-specific prompts or ToolNode wiring, use a dummy LLM to initialize stock/A股/crypto configs and compile `TradingAgentsGraph` without API keys.

## Asset-Specific Gotchas

### Crypto / CCXT / OKX

Symbol / ticker:
- **Single ticker source**: CLI crypto mode prompts for one CCXT pair (e.g. `BTC/USDT`); `cli/main.py` derives `company_of_interest` via `ccxt_to_display_ticker()`. Previous dual yfinance + CCXT input was removed in `7361e60`.
- `tradingagents/dataflows/crypto_symbols.py` is the single source for crypto ticker conversion. `ccxt_to_base()` accepts any of `BTC/USDT` / `ETH/USDT:USDT` / `BTC-USDT-SWAP` / `BTC` and returns the bare base. All vendor lookups (CoinGecko id, DefiLlama slug, OKX ccy, RSS news base currency) flow through `ccxt_to_base()` — do not parse tickers ad-hoc in agent or vendor code.
- `CRYPTO_SYMBOL_MAP` is keyed by base currency. Adding a new coin = one entry mapping base → `{cg_id, defillama_slug}`.

Vendor / endpoint layout:
- `tradingagents/dataflows/okx_data.py` — OKX v5 REST endpoints via `requests` (rubik + public + market). All public endpoints; no HMAC signature helper is implemented.
- `tradingagents/dataflows/free_crypto_news_data.py` — free/no-key public RSS news from major crypto outlets; filters by base currency plus macro/regulatory keywords.
- `tradingagents/dataflows/coingecko_data.py` — Single `/coins/{id}` HTTP call shared by fundamentals (`get_coingecko_fundamentals_block`) and sentiment (`get_coingecko_sentiment_block`); cache by `cg_id`. Optional `COINGECKO_DEMO_API_KEY`.
- `tradingagents/dataflows/defillama_data.py` — `/protocol/{slug}` + `/summary/fees/{slug}`. No auth. Slow API: 25s timeout + 1 retry (see `ad1c06f`); current TVL must be pulled from the historical array's last element, not the top-level field (see `579dc1f`).
- `tradingagents/dataflows/alternative_me_data.py` — `/fng/?limit=N`. No auth. F&G consumed by sentiment_analyst pre-fetch only.

Analyst → tool wiring:
- `crypto_market_tools.py` — 7 rubik + 5 new public-endpoint tools (`get_okx_ticker_snapshot`, `get_okx_perp_basis`, `get_okx_funding_rate_now`, `get_okx_open_interest_now`, `get_okx_liquidation_orders`).
- `crypto_news_tools.py` — `get_free_crypto_news`, `get_okx_exchange_announcements`, `get_okx_delivery_events`.
- `crypto_fundamental_tools.py` — `get_token_profile`, `get_protocol_metrics`.
- `crypto_sentiment_tools.py` — defines `get_crypto_smart_money` and `get_crypto_margin_leverage` as `@tool`s, but neither is currently bound to any analyst. Sentiment runs as pre-fetch only (F&G + CoinGecko via `sentiment_analyst.py` crypto branch).

OKX endpoint quirks (learned the hard way during this revamp):
- Contracts stat endpoints generally require `instId` (`BTC-USDT-SWAP`); exceptions: `/rubik/contracts/open-interest-volume` and `/rubik/option/open-interest-volume-ratio` take `ccy`.
- `/public/liquidation-orders` requires `uly` (underlying, e.g. `BTC-USDT`), not `ccy`; passing `ccy` returns empty (`91639a0`).
- `/rubik/contracts/open-interest-volume-aggregated` rejects `4H` — use `1H` default (`15e984c`).
- `/support/announcements` response is nested two levels: `data[0]['details']` not `data[0]` (`4b36958`).
- `open-interest-history` row layout: `[ts, oi, oiCcy, oiUsd]`.
- `_okx_request()` retries network errors and rate-limit code `50011`; per-function rate-limiter does not coordinate across different rubik endpoints.

Auth-gated OKX endpoints that LOOK public but aren't (do not wire without HMAC auth):
- `/public/economic-calendar` returns `50103 OK-ACCESS-KEY required`; no tool is currently exposed for it.
- `/finance/savings/public-borrow-info` returns 403 without auth; no fundamentals tool is currently exposed for it.

CCXT:
- CCXT cache key does not include exchange name; clear cache when switching `ccxt_exchange`.
- CCXT vendor only handles `get_stock_data` and `get_indicators`; all crypto news/fundamentals/sentiment go through the dedicated vendors above.

ENV:
- `COINGECKO_DEMO_API_KEY` — optional; missing → anonymous public endpoint (stricter IP throttling).
- Crypto news RSS, DefiLlama, Alternative.me, and current OKX public endpoints require no env vars.
- No OKX env vars currently used.

### A-share / AkShare

- External ticker format: `600519.SH`, `000001.SZ`, `430047.BJ`; state/agents preserve this format.
- Vendor converts via `_resolve_a_share_symbol(symbol, fmt)`: `6digit` for many APIs, `exchange_prefix` (`SH600519`) for financial statements and some detail endpoints.
- AkShare financial statement APIs require `exchange_prefix`: `stock_balance_sheet_by_report_em`, `stock_cash_flow_sheet_by_report_em`, `stock_profit_sheet_by_report_em`.
- Margin APIs require `YYYYMMDD`, not `YYYY-MM-DD`.
- `cn_market_data` and `cn_sentiment_data` are akshare-only categories with no fallback.
- A-share OHLCV defaults to `adjust="qfq"`; `get_akshare_limit_status` infers limit-up/down from daily returns.
- `akshare_retry()` retries requests errors and JSONDecodeError/KeyError with throttle/backoff; programming errors should propagate.
- Known AkShare API drift: `stock_em_jgdy_detail` → `stock_jgdy_detail_em`; use `stock_jgdy_tj_em(date=YYYYMMDD)` then filter by ticker for institutional visits.
- `news_cctv` replaced stale `news_economic_baidu`; A-share global news filters CCTV daily transcripts by Shenwan industry keywords.
- A-share sentiment prefetches three layers from `cn_sentiment_tools.py`: retail hot-rank, sell-side research, buy-side institutional visits.
- A-share fundamentals append `get_earnings_forecast`, `get_shareholder_count`, `get_valuation_comparison` to the four core fundamentals tools.

## LLM / CLI Notes

- OpenAI-compatible providers include OpenAI, custom_openai, xAI, DeepSeek, Qwen/Qwen-CN, GLM/GLM-CN, MiniMax/MiniMax-CN, Ollama, OpenRouter.
- `custom_openai` uses `CUSTOM_OPENAI_BASE_URL` / `CUSTOM_OPENAI_API_KEY`; `custom_anthropic` uses `CUSTOM_ANTHROPIC_BASE_URL` / `CUSTOM_ANTHROPIC_API_KEY`.
- `CUSTOM_OPENAI_HEADERS` / `CUSTOM_ANTHROPIC_HEADERS` are JSON object strings parsed by `headers_env.load_custom_headers()` and forwarded as LangChain `default_headers`.
- Custom provider model selection bypasses `model_catalog.py`; `cli/utils.select_custom_provider_model()` fetches `{CUSTOM_*_BASE_URL}/models` and falls back to manual entry.
- `custom_model_discovery.fetch_custom_models()` must tolerate `{"data": [...]}`, `{"models": [...]}`, top-level `[...]`, and empty `{"data": []}` responses.
- OpenAI/Anthropic effort menus share Default/Low/Medium/High/XHigh/Max with High as CLI default; select Default when a backend rejects effort fields.
- DeepSeek supports `deepseek_reasoning_effort` and `deepseek_thinking_enabled`; thinking mode is injected through `extra_body.thinking` in `DeepSeekChatOpenAI`.
- CLI interactive selection helpers live mostly in `cli/utils.py`; simple prompt wrappers and run assembly live in `cli/main.py`.
- Adding CLI steps requires manual step-number renumbering in `cli/main.py`.

## Memory / Reflection

- Memory uses BM25/offline matching; no embeddings needed.
- `TradingMemoryLog` stores final decisions and resolves outcomes on later same-ticker runs.
- Reflection alpha uses `_resolve_benchmark()` and labels alpha as `Alpha vs <benchmark>`.

## Chat Replay (`tradingagents chat`)

- Entry point: `@app.command() def chat(...)` in `cli/main.py`; all chat logic under `cli/chat/`.
- Key files: `manifest.py` (run_manifest.json read/write), `session.py` (JSONL persistence), `prompt.py` (system prompt builder), `agent.py` (LangGraph sub-graph + LLM factory), `repl.py` (prompt_toolkit REPL loop).
- `safe_ticker()` lives in `cli/chat/manifest.py` and is imported by `cli/main.py`; do not duplicate ticker-escaping logic elsewhere.
- `get_all_tools_for_asset_type(toolkit, config)` in `agent_utils.py` aggregates market + news + fundamentals + sentiment tools for the current asset type; use this instead of copy-pasting per-analyst tool lists.
- Chat LLM triple: `chat_llm_provider / chat_llm_model / chat_llm_effort` (default: `openai / gpt-4o / default`). Keep `chat_llm_effort` as `default` for non-reasoning models; only set to a named effort level when the model supports reasoning effort (o-series, claude-3-5+).
- `custom_openai` / `custom_anthropic` chat providers: `build_chat_llm()` reads `CUSTOM_OPENAI_BASE_URL` / `CUSTOM_OPENAI_API_KEY` (and Anthropic equivalents) directly from env — these are NOT in `DEFAULT_CONFIG`.
- Report directory layout written by `save_report_to_disk()`: `{results_dir}/{safe_ticker}/{date}/{1_analysts,2_research,3_trading,4_risk,5_portfolio}/`. `run_manifest.json` sits at `{results_dir}/{safe_ticker}/{date}/run_manifest.json`.
- Session JSONL: header line (type=header) + message lines (type=msg). `_repair_incomplete_tool_calls()` validates tool_call ids on load; if any expected id is missing, the whole turn is dropped.

## Development Hygiene

- Prefer minimal, focused edits; avoid formatting churn because this branch rebases against upstream.
- `DEFAULT_CONFIG.copy()` is a shallow copy — nested `data_vendors` dict is shared. Always use `copy.deepcopy(DEFAULT_CONFIG)` before mutating vendor keys.
- When adding analyst tools, update both `llm.bind_tools(tools)` and `TradingAgentsGraph._create_tool_nodes()` unless the agent is intentionally no-ToolNode like Sentiment.
- When an OKX endpoint turns out to require auth, prefer a graceful stub (placeholder string) over removing the function — leaves the door open for HMAC-signed wiring later. Document the stub at the function docstring AND in this file's OKX section.
- Use `git diff --check` before committing prompt/doc rewrites.
- After editing custom provider headers or model discovery, run `python -m pytest tests/test_headers_env.py tests/test_custom_model_discovery.py -v`.
- Commit only explicit source/doc files; leave `.DS_Store`, `plan/`, and build-worktree `reports/` untracked unless the user explicitly asks otherwise.
