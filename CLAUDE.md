# CLAUDE.md

TradingAgents is a LangGraph-based multi-agent trading framework. Agents produce one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.

Two entry points:
- `tradingagents` / `tradingagents analyze` — full multi-agent analysis pipeline
- `tradingagents chat` — interactive retrospective dialogue against a saved report

---

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

---

## Part A: Analyze (`tradingagents` / `tradingagents analyze`)

### Architecture

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

### Report Output

Reports save to `./reports/{safe_ticker}/{YYYYMMDD_HHMMSS}/`:
```
reports/BTC_USDT/20260527_143022/
├── run_manifest.json         # ticker, asset_type, data_vendors, analysis_date, …
├── message_tool.log          # LLM message + tool-call trace
└── reports/
    ├── 1_analysts/{market,sentiment,news,fundamentals}.md
    ├── 2_research/{bull,bear,manager}.md
    ├── 3_trading/trader.md
    ├── 4_risk/{aggressive,conservative,neutral}.md
    └── 5_portfolio/decision.md
```

`safe_ticker()` converts `/` `\` `:` to `_` (e.g. `BTC/USDT` → `BTC_USDT`), defined in `cli/chat/manifest.py`. Same-second reruns get `_2`, `_3` suffix via `_next_available_dir()`.

### Config / Data Routing

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

### Agent / Prompt Rules

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
- Avoid generic multi-agent boilerplate like "another assistant will help where you left off"; it weakens mandatory tool behavior.
- `get_news(ticker, ...)` is strict ticker-based, not free-text search; prompts must not ask for CEO names or sentiment keywords as query strings.
- `get_indicators(indicator=...)` accepts comma-separated indicators; prompt should request one call per timeframe, not one call per indicator.
- `sentiment_analyst.py` has no ToolNode: it prefetches data and makes one LLM call across all three asset paths (US stock = yfinance+StockTwits+Reddit; A-share = 3-layer akshare; crypto = F&G + CoinGecko votes). `trading_graph._create_tool_nodes()` must not register `social`. `crypto_sentiment_tools.py` exposes `get_crypto_smart_money` / `get_crypto_margin_leverage` as `@tool`s but they are not currently bound to any analyst — either wire them in or treat as dead code.
- market/news/fundamentals/sentiment prompts are split by stock/A股/crypto; update the relevant `_build_*system_message()` branch instead of mixing all assets into one long prompt.

Prompt/graph smoke test: after editing asset-specific prompts or ToolNode wiring, use a dummy LLM to initialize stock/A股/crypto configs and compile `TradingAgentsGraph` without API keys.

### Asset-Specific Gotchas

#### Crypto / CCXT / OKX

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
- `/public/economic-calendar` returns `50103 OK-ACCESS-KEY required`.
- `/finance/savings/public-borrow-info` returns 403 without auth.
These were discovered during endpoint exploration; no stubs exist for them in the codebase.

CCXT:
- CCXT cache key does not include exchange name; clear cache when switching `ccxt_exchange`.
- CCXT vendor only handles `get_stock_data` and `get_indicators` (registered as `get_ccxt_stock_data` / `get_ccxt_indicators`); all crypto news/fundamentals/sentiment go through the dedicated vendors above.

ENV:
- `COINGECKO_DEMO_API_KEY` — optional; missing → anonymous public endpoint (stricter IP throttling).
- Crypto news RSS, DefiLlama, Alternative.me, and current OKX public endpoints require no env vars.
- No OKX env vars currently used.

#### A-share / AkShare

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

### Memory / Reflection

- Memory uses BM25/offline matching; no embeddings needed.
- `TradingMemoryLog` stores final decisions and resolves outcomes on later same-ticker runs.
- Reflection alpha uses `_resolve_benchmark()` and labels alpha as `Alpha vs <benchmark>`.

---

## Part B: Chat Replay (`tradingagents chat`)

`tradingagents chat` loads a past report and lets the user discuss its findings with an
agent that has access to the full original report context plus **the same data tools**
(market / news / fundamentals / sentiment) for that asset type, so it can pull fresh data
and compare against the report's conclusions.

### CLI Entry Point

`@app.command() def chat()` in `cli/main.py` — **no CLI arguments** (no `--ticker`,
`--date`, no typer completion flags). Always enters the interactive report browser.

Flow:
1. Scan `Path.cwd() / "reports"` → `pick_report()` questionary list.
2. Load `run_manifest.json` → vendor / asset-type config; load all report markdown.
3. Run `setup_chat_llm_interactive()` to configure provider / model / effort / key.
4. Pick the most-recent session for this report (or create `{ts}-default.jsonl`).
5. Build the LangGraph chat sub-graph + enter REPL.

### Key Files

```
cli/chat/
├── __init__.py
├── manifest.py    # run_manifest.json read/write, safe_ticker, get_reports_dir, find_report_dir
├── browser.py     # interactive report picker (questionary.select)
├── llm_setup.py   # interactive LLM provider/model/effort/key selection for chat
├── session.py     # multi-session JSONL persistence
├── prompt.py      # system prompt builder for the chat agent
├── agent.py       # LangGraph sub-graph, chat LLM construction, rebuild_app_graph
└── repl.py        # prompt_toolkit REPL loop, slash command dispatcher, stream rendering
```

### LLM Configuration for Chat

Chat uses a **single** LLM triple (no quick/deep split):
- `chat_llm_provider` / `chat_llm_model` / `chat_llm_effort`
- Default: `openai / gpt-4o / default` (`tradingagents/default_config.py:75-77`)
- Env overrides: `TRADINGAGENTS_CHAT_LLM_PROVIDER`, `TRADINGAGENTS_CHAT_LLM_MODEL`, `TRADINGAGENTS_CHAT_LLM_EFFORT`
- `/model` persists the selection to `{cwd}/.env` via `dotenv.set_key` (mirrors `ensure_api_key`)
- `setup_chat_llm_interactive(config)` in `cli/chat/llm_setup.py` walks the user through provider/model/effort/key; has a fast-path when env is pre-configured. `/model` in REPL calls it with `force_interactive=True`.
- `/model` reuses the `deep` model pool (chat is reasoning-heavy); the original `"chat"` mode blew up with `KeyError` because `MODEL_OPTIONS` only has `quick`/`deep` keys.
- `_build_chat_kwargs()` in `agent.py` falls back to the provider's canonical env var when `config["llm_api_key"]` is absent — `setup_chat_llm_interactive()` populates `llm_api_key` as the primary path.
- `custom_openai` / `custom_anthropic`: `build_chat_llm()` reads `CUSTOM_OPENAI_BASE_URL` / `CUSTOM_OPENAI_API_KEY` directly from env — these are NOT in `DEFAULT_CONFIG`.

### Report Loading

`run_manifest.json` supplies:
- `ticker`, `company_of_interest`, `ccxt_symbol`, `benchmark_ticker`
- `asset_type`, `data_vendors`, `tool_vendors`
- `analysis_date`, `output_language`
- `report_files` — relative paths to each sub-report markdown

These override the `DEFAULT_CONFIG` copy for vendor routing but do NOT include LLM settings
(which follow the current CLI config). `safe_ticker()` and `get_reports_dir()` live in
`cli/chat/manifest.py`; do not duplicate ticker-escaping logic elsewhere.

The chat agent's system prompt receives all 10 report sections (aligned with
`portfolio_manager.py`'s context): 4 analyst reports (full text), research manager plan,
trader plan, risk debate history (3 debaters concatenated), portfolio manager final
decision, and `past_context` from `TradingMemoryLog`.

### Agent & Tool Binding

`build_chat_app()` in `agent.py` constructs a simple LangGraph sub-graph:

```
START → chat_node (LLM with bound tools) → conditional: tool_calls? → tools → chat_node
                                                                        → END
```

State: `{"messages": list}` — no checkpointer, state held in REPL.

Tools come from `get_all_tools_for_asset_type(toolkit, config)` in `agent_utils.py`, which
aggregates market + news + fundamentals + sentiment tools for the detected asset type.
Use this instead of copy-pasting per-analyst tool lists.

`rebuild_app_graph()` re-instantiates the LLM from config and re-compiles the graph — used
by `/model` and `/lang` to hot-swap without losing message history. REPL keeps
`state_messages` itself, so rebuilds are lossless.

`get_chat_tools(config)` returns the tool list on demand for the `/tools` slash command.

### Sessions

Multi-session per report. Files under `{report_dir}/sessions/{YYYYMMDD-HHMMSS}-{slug}.jsonl`.

Startup picks `latest_session_path(report_dir)` (most recent by mtime), creating a new
`{ts}-default.jsonl` if none exist. Old `default.jsonl` files (no timestamp prefix) load
via the same mtime sort and get a fresh prefix on first `/title` rename.

JSONL format:
- Line 0 (header): `{"type":"header","id":"<uuid>","title":"...","created_at":"...","report_ref":"..."}`
- Subsequent lines (messages): `{"type":"msg","role":"user|assistant|tool","ts":"...","content":"...",...}`
- Assistant messages additionally carry `model`, `effort`, and optional `tool_calls`.

`load_messages()` skips the header line and converts each `type=msg` line to a LangChain
message. `_repair_incomplete_tool_calls()` validates tool_call IDs on load; if any expected
ID is missing, the trailing user turn is dropped. Messages are stored and loaded as full
content — no truncation. `rewrite_header()` writes atomically via `.tmp` + `os.replace`.

Key helpers in `session.py` (all additive, `default_session_path` preserved for back-compat):
- `make_session_path(report_dir, title)` — create a timestamped path
- `list_sessions(report_dir)` — scan and sort by mtime
- `latest_session_path(report_dir)` — most recent entry
- `rename_session_file(path, new_title)` — preserve existing timestamp prefix
- `delete_session(path)` — unlink

### REPL & Slash Commands

Prompt-toolkit loop with rich Markdown streaming. `app_graph` held in `app_graph_ref = [graph]`;
`session_path` held in `session_path_ref = [path]` so the slash dispatcher can swap them.
`state_messages` is mutated via `.clear()` + `.extend(load_messages(...))` to preserve closure
references.

On startup and after `/sessions` or `/delete` switch, `_print_history()` echoes the most recent
20 messages as a compact log (`> user`, `● assistant`, `⏺ tool`). History older than 20 items
gets an omission hint. The full message content is always in `state_messages` for the agent.

Slash commands (`_handle_slash` in `repl.py`):

| Command | Action | Rebuilds graph? |
|---|---|---|
| `/help` | Print command table | No |
| `/tools` | List bound tools via `get_chat_tools()` | No |
| `/lang [LANG]` | Switch output language + rebuild | Yes |
| `/model` | Reconfigure LLM provider/model/effort + rebuild | Yes |
| `/sessions` | questionary.select → swap JSONL, reload messages | No |
| `/new [title]` | Create new session, clear messages | No |
| `/title <name>` | Rename current session file + header | No |
| `/delete` | Delete current session, switch to next | No |
| `/exit`, `/quit` | Exit REPL | — |

Graph-rebuilding commands (`/lang`, `/model`) call `rebuild_app_graph()` and assign
`app_graph_ref[0]`. Session-switching commands swap only the JSONL — same report, same tools,
same model — so no graph rebuild is needed. Unknown `/...` prints a hint and does NOT forward
to the LLM.

### System Prompt

Built by `build_system_prompt()` in `prompt.py`. Injects the full report context (10 sections),
`asset_prompt_context` (reuses `agent_utils`), language instruction, and tool names. The
prompt instructs the agent to distinguish between internal-logic critiques (no tools) and
post-report data verification (must call tools), and forbids issuing a new BUY/SELL decision.

`output_language` is read from config at graph build time (or manifest fallback), so `/lang`
rebuilds the graph with the new language instruction.

---

## LLM / Provider Notes (shared)

- OpenAI-compatible providers include OpenAI, custom_openai, xAI, DeepSeek, Qwen/Qwen-CN, GLM/GLM-CN, MiniMax/MiniMax-CN, Ollama, OpenRouter.
- `custom_openai` uses `CUSTOM_OPENAI_BASE_URL` / `CUSTOM_OPENAI_API_KEY`; `custom_anthropic` uses `CUSTOM_ANTHROPIC_BASE_URL` / `CUSTOM_ANTHROPIC_API_KEY`.
- `CUSTOM_OPENAI_HEADERS` / `CUSTOM_ANTHROPIC_HEADERS` are JSON object strings parsed by `headers_env.load_custom_headers()` and forwarded as LangChain `default_headers`.
- Custom provider model selection bypasses `model_catalog.py`; `cli/utils.select_custom_provider_model()` fetches `{CUSTOM_*_BASE_URL}/models` and falls back to manual entry.
- `custom_model_discovery.fetch_custom_models()` must tolerate `{"data": [...]}`, `{"models": [...]}`, top-level `[...]`, and empty `{"data": []}` responses.
- OpenAI/Anthropic effort menus share Default/Low/Medium/High/XHigh/Max with High as CLI default; select Default when a backend rejects effort fields.
- DeepSeek supports `deepseek_reasoning_effort` and `deepseek_thinking_enabled`; thinking mode is injected through `extra_body.thinking` in `DeepSeekChatOpenAI`.
- CLI interactive selection helpers live mostly in `cli/utils.py`; simple prompt wrappers and run assembly live in `cli/main.py`.

## Development Hygiene

- Prefer minimal, focused edits; avoid formatting churn because this branch rebases against upstream.
- `DEFAULT_CONFIG.copy()` is a shallow copy — nested `data_vendors` dict is shared. Always use `copy.deepcopy(DEFAULT_CONFIG)` before mutating vendor keys.
- When adding analyst tools, update both `llm.bind_tools(tools)` and `TradingAgentsGraph._create_tool_nodes()` unless the agent is intentionally no-ToolNode like Sentiment.
- When an OKX endpoint turns out to require auth, prefer a graceful stub (placeholder string) over removing the function — leaves the door open for HMAC-signed wiring later. Document the stub at the function docstring AND in this file's OKX section. (Two endpoints discovered as auth-gated — `/public/economic-calendar` and `/finance/savings/public-borrow-info` — were never stubbed; this rule was adopted after those were found.)
- Use `git diff --check` before committing prompt/doc rewrites.
- After editing custom provider headers or model discovery, run `python -m pytest tests/test_headers_env.py tests/test_custom_model_discovery.py -v`.
- Commit only explicit source/doc files; leave `.DS_Store`, `plan/`, and build-worktree `reports/` untracked unless the user explicitly asks otherwise.

---

## Upstream Merge Guide

Base: upstream `v0.2.5` (TauricResearch/TradingAgents@`a5cb7cb`). 50 commits, 85 files changed (+8773/-464).

When merging from upstream, the following areas have local modifications. Use this as a
conflict-resolution checklist — each section lists what we changed and which files are
affected.

### 1. A-Share / Chinese Market Support

New data vendors and tools for Chinese stocks (SSE/SZSE/BSE). No counterpart in upstream.

**New files** (no merge risk — upstream won't touch these):
```
tradingagents/dataflows/akshare_common.py      # shared AkShare HTTP helpers
tradingagents/dataflows/akshare_data.py         # AkShare market + fundamentals vendor
tradingagents/agents/utils/cn_market_tools.py   # A-share market tools (limit status, margin, concept board)
tradingagents/agents/utils/cn_sentiment_tools.py # retail hot-rank, sell-side research, buy-side visits
```

**Modified files** (merge risk — upstream may touch these):
```
tradingagents/dataflows/interface.py            # register_*() calls for akshare + cn_sentiment_data routes
tradingagents/default_config.py                 # cn_market_data, cn_sentiment_data vendor keys
tradingagents/agents/utils/agent_utils.py       # get_asset_type() A-share detection, asset_prompt_context
tradingagents/graph/trading_graph.py            # ToolNode wiring for cn_market/cn_sentiment tools
tradingagents/agents/analysts/sentiment_analyst.py   # A-share pre-fetch branch
tradingagents/agents/analysts/fundamentals_analyst.py # A-share extended fundamentals tools
cli/main.py                                     # a_share CLI config preset
```

### 2. Crypto Analyst Revamp

Replaced upstream's paid CryptoPanic + basic CCXT with free/open data stack. This is the
largest single change.

**New files** (no merge risk):
```
tradingagents/dataflows/okx_data.py             # OKX v5 REST (rubik + public + market)
tradingagents/dataflows/okx_common.py           # shared OKX HTTP helpers
tradingagents/dataflows/ccxt_data.py            # CCXT OHLCV + technical indicators (file-based cache)
tradingagents/dataflows/coingecko_data.py       # CoinGecko /coins/{id}
tradingagents/dataflows/defillama_data.py       # DeFiLlama protocol TVL + fees
tradingagents/dataflows/alternative_me_data.py  # Fear & Greed Index
tradingagents/dataflows/free_crypto_news_data.py # RSS-based free crypto news
tradingagents/dataflows/crypto_symbols.py       # CCXT ↔ display ticker mapping
tradingagents/agents/utils/crypto_market_tools.py    # 12 OKX market tools
tradingagents/agents/utils/crypto_news_tools.py      # crypto news tools
tradingagents/agents/utils/crypto_fundamental_tools.py # token profile + protocol metrics
tradingagents/agents/utils/crypto_sentiment_tools.py  # smart money / margin (defined but not wired)
```

**Modified files** (merge risk):
```
tradingagents/dataflows/interface.py            # register_*() for all new crypto vendors
tradingagents/default_config.py                 # crypto_market_data, crypto_news, crypto_fundamentals keys
tradingagents/graph/trading_graph.py            # ToolNode wiring for crypto tools
tradingagents/graph/setup.py                    # graph edge adjustments for crypto
tradingagents/llm_clients/factory.py            # CCXT cache key fix
.env.example                                    # CRYPTOPANIC_API_KEY removed, COINGECKO_DEMO_API_KEY added
```

**Key design decisions** (do not regress):
- Single ticker source: `ccxt_symbol` (e.g. `BTC/USDT`) → `ccxt_to_base()` → all vendor lookups.
  Upstream had dual yfinance + CCXT input; we removed yfinance for crypto (`7361e60`).
- `crypto_symbols.py` is the single ticker conversion source; do not parse tickers ad-hoc.
- CoinGecko `DEMO_API_KEY` is optional; anonymous falls back to public endpoint.
- OKX public endpoints only (no HMAC auth); two stubbed endpoints documented in code.
- DeFiLlama current TVL must be pulled from historical array's last element.

### 3. Prompt Refactoring — Asset-Specific Splits

Every agent prompt was split into stock / A-share / crypto branches. This touches all 10
agent files. Upstream changes to prompts will conflict heavily.

**Modified files** (HIGH merge risk — core agent logic):
```
tradingagents/agents/analysts/market_analyst.py
tradingagents/agents/analysts/news_analyst.py
tradingagents/agents/analysts/sentiment_analyst.py
tradingagents/agents/analysts/fundamentals_analyst.py
tradingagents/agents/researchers/bull_researcher.py
tradingagents/agents/researchers/bear_researcher.py
tradingagents/agents/managers/research_manager.py
tradingagents/agents/managers/portfolio_manager.py
tradingagents/agents/trader/trader.py
tradingagents/agents/risk_mgmt/aggressive_debator.py
tradingagents/agents/risk_mgmt/conservative_debator.py
tradingagents/agents/risk_mgmt/neutral_debator.py
tradingagents/agents/utils/agent_utils.py       # get_asset_type(), get_asset_prompt_context(), language instruction
```

**Merge strategy**: If upstream changes a prompt, apply the same change to all three
branches (stock / A-share / crypto) within that agent. The `_build_*_system_message()`
pattern is consistent across agents.

### 4. LLM / Provider Enhancements

**New files** (no merge risk):
```
tradingagents/llm_clients/custom_model_discovery.py  # /models endpoint fetching
tradingagents/llm_clients/headers_env.py              # CUSTOM_*_HEADERS JSON parsing
```

**Modified files** (merge risk):
```
tradingagents/llm_clients/openai_client.py       # custom provider headers, DeepSeek thinking
tradingagents/llm_clients/anthropic_client.py     # custom provider headers
tradingagents/llm_clients/factory.py              # provider routing, custom provider model selection
tradingagents/llm_clients/validators.py           # expanded effort options
tradingagents/default_config.py                   # per-role quick/deep effort split
cli/main.py                                       # custom provider CLI flow
cli/utils.py                                      # select_custom_provider_model()
```

**Key changes**:
- Effort split into `quick_llm_effort` / `deep_llm_effort` (was single `llm_effort`)
- `custom_openai` / `custom_anthropic` support `CUSTOM_*_BASE_URL`, `CUSTOM_*_API_KEY`, `CUSTOM_*_HEADERS`
- DeepSeek supports `reasoning_effort` and `thinking_enabled` via `extra_body`
- Custom model discovery tolerates `{data: [...]}`, `{models: [...]}`, `[...]`, and empty responses
- `ChatOpenAI` / `ChatAnthropic` constructors pass `default_headers` from env
- **`**kwargs` added to all legacy vendor functions** (10 files) for LangChain tool-calling compatibility. Affected files:

  ```
  tradingagents/dataflows/alpha_vantage_fundamentals.py   # +**kwargs on 4 functions
  tradingagents/dataflows/alpha_vantage_indicator.py      # +**kwargs
  tradingagents/dataflows/alpha_vantage_news.py           # +**kwargs on 3 functions
  tradingagents/dataflows/alpha_vantage_stock.py          # +**kwargs
  tradingagents/dataflows/y_finance.py                    # +**kwargs on 7 functions
  tradingagents/dataflows/yfinance_news.py                # +**kwargs on 2 functions
  tradingagents/agents/utils/core_stock_tools.py          # +timeframe, +**kwargs
  tradingagents/agents/utils/fundamental_data_tools.py    # +3 A-share tools, +**kwargs
  tradingagents/agents/utils/news_data_tools.py           # +ticker param, +**kwargs
  tradingagents/agents/utils/technical_indicators_tools.py # +timeframe, comma-sep support
  ```

  If upstream changes function signatures in these files, preserve the `**kwargs` and
  our extra parameters (`timeframe`, `ticker`).

### 5. Chat Replay Feature (`tradingagents chat`)

Entirely new subcommand. No upstream counterpart.

**New files** (no merge risk):
```
cli/chat/__init__.py        # package
cli/chat/manifest.py        # run_manifest.json read/write, safe_ticker, report dir helpers
cli/chat/browser.py         # interactive report picker (questionary)
cli/chat/llm_setup.py       # interactive LLM provider/model/effort/key selection
cli/chat/session.py         # multi-session JSONL persistence
cli/chat/prompt.py          # system prompt builder (injects full report context)
cli/chat/agent.py           # LangGraph sub-graph, chat LLM construction, rebuild_app_graph
cli/chat/repl.py            # prompt_toolkit REPL loop, slash command dispatcher
```

**Modified files** (merge risk):
```
cli/main.py                                   # chat subcommand registration
tradingagents/default_config.py               # chat_llm_provider/model/effort config triple
tradingagents/agents/utils/agent_utils.py     # Toolkit class, get_all_tools_for_asset_type()
```

**Key design decisions**:
- Chat uses a **single** LLM triple (no quick/deep split): `chat_llm_provider/model/effort`
- `/model` persists to `{cwd}/.env` via `dotenv.set_key`; reuses `deep` model pool
- Report output unified under `./reports/{safe_ticker}/{YYYYMMDD_HHMMSS}/`
- Multi-session JSONL files under `{report_dir}/sessions/`
- `safe_ticker()` converts `/` `\` `:` to `_`; same-second reruns get `_2`, `_3` suffix

### 6. Bug Fixes & Hardening (scattered)

These are small, localized changes unlikely to cause merge issues, but note them:

```
tradingagents/dataflows/utils.py               # get_global_news ticker type annotation fix
tradingagents/dataflows/interface.py           # questionary Choice(None) fix
tradingagents/graph/trading_graph.py           # sentiment analyst graph alignment, config deepcopy
```

### 7. Housekeeping

```
cli/main.py                         # splash screen rebranded for fork
.env.example                        # removed CRYPTOPANIC_API_KEY, added new keys
pyproject.toml                      # dependency additions (akshare, ccxt, questionary, prompt_toolkit, rich, dotenv)
```

### 8. Tests

New test infrastructure (no upstream tests existed):
```
pytest.ini
tests/conftest.py
tests/__init__.py
tests/TESTING_STRATEGY.md
tests/test_headers_env.py
tests/test_custom_model_discovery.py
tests/test_custom_llm_providers.py
tests/test_akshare_smoke.py
tests/test_safe_ticker_component.py
tests/unit/__init__.py
tests/unit/dataflows/__init__.py
tests/unit/dataflows/test_crypto_revamp_regressions.py
tests/unit/dataflows/test_ccxt_data_template.py
tests/unit/utils/__init__.py
tests/fixtures/__init__.py
tests/fixtures/mock_ccxt.py
tests/fixtures/test_data.py
tests/integration/__init__.py
tests/integration/test_ccxt_integration_template.py
tests/performance/__init__.py
tests/performance/test_ccxt_performance_template.py
tests/compatibility/__init__.py
```

### Merge Procedure

1. `git fetch upstream && git merge upstream/main --no-commit --no-ff`
2. Resolve conflicts by category (use the lists above to identify what each side changed):
   - **New files** (our additions): never conflict; no action needed.
   - **Agent prompts** (Section 3): if upstream changed a prompt, apply the same change to
     all three asset branches in that file.
   - **`default_config.py`**: if upstream added config keys, merge them alongside our new keys.
   - **`interface.py`**: if upstream added vendor routes, register them alongside ours.
   - **`trading_graph.py` / `setup.py`**: if upstream changed graph structure, adapt our
     ToolNode registrations and edge wiring.
   - **`cli/main.py`**: if upstream changed the Typer app, preserve our `chat` subcommand
     and custom provider flow.
   - **`agent_utils.py`**: if upstream added helpers, keep our `Toolkit`, `get_asset_type()`,
     `get_asset_prompt_context()`, and `get_all_tools_for_asset_type()`.
3. After resolving, run the prompt/graph smoke test with a dummy LLM for stock, A-share,
   and crypto configs to catch wiring errors.
4. `git commit` then `pip install -e .` in the build worktree.
