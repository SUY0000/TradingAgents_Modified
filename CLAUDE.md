# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents is a multi-agent LLM financial trading framework built on LangGraph. It simulates a trading firm with specialized agents (analysts, researchers, traders, risk managers) that collaborate through structured debate to produce trading decisions. Decisions are one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.

## Fork 工作流与双 Worktree 开发规范

本项目是从上游开源仓库 fork 而来，遵循"双 worktree 隔离"开发模式。任何代码改动都必须遵守下列规则。

### 仓库布局

```
开发 worktree:  .../<ProjectName>/         ← git 操作 + 代码编辑
构建 worktree:  .../<ProjectName>_Build/   ← 编译 + 打包 + 安装
                                                          （detached HEAD，不参与提交）
```

两个目录共享同一个 `.git`，但工作区独立。命名约定：构建 worktree 与开发 worktree 同级，目录名加 `_Build` 后缀。

### Remote 设定

- `origin` → 用户的 fork（push 目标）
- `upstream` → 上游官方仓库（只 fetch，不 push）

### 一次性初始化命令

```bash
cd .../<ProjectName>
git remote add upstream <official-repo-url>
git checkout -b feat/<feature-name>
git push -u origin feat/<feature-name>
git worktree add --detach .../<ProjectName>_Build feat/<feature-name>
```

### 三条铁律（违反即停下汇报）

1. **不在构建 worktree 编辑源码**。构建 worktree 是 detached HEAD，编辑容易丢失。
2. **不在开发 worktree 跑 `*install` 或 `*build`**。开发 worktree 必须保持 `git status` clean。
3. **构建 worktree 切分支永远用 `--detach`**。同一分支不能同时 checkout 在两个 worktree。

### 命令分流表

| 操作 | 命令 | 在哪个 worktree |
|------|------|----------------|
| 编辑代码 | (编辑器) | 开发 |
| `git commit` / `rebase` / `cherry-pick` | git 命令 | 开发 |
| 同步 upstream | 见下方流程 | 开发 |
| `push` 到 fork | `git push origin <branch>` | 开发 |
| 类型检查 / 单元测试 | `bun run typecheck` / `bun test` 等 | 开发 |
| 安装依赖 | `bun install` (或项目对应命令) | 构建 |
| 编译 / 打包 / 出包 | `bun run build` 等 | 构建 |
| 安装产物到本机 | `cp -r dist/... /Applications/` 等 | 构建 |
| 清理构建产物 | `git clean -fxd` 或针对性 `rm -rf` | 构建 |

### 跨 Worktree 同步代码

每次在开发 worktree commit 后，构建 worktree 必须显式拉取最新 commit：

```bash
cd .../<ProjectName>_Build
git fetch . <branch-name>             # 从本地 .git 拉，不需要先 push
git switch --detach FETCH_HEAD
bun install                           # 仅当 package.json 变了
bun run build                         # 重新构建
```

注意 `git fetch .` 中的 `.` 表示本地仓库 —— 这避免了"先 push 到 GitHub 再 pull 回来"的冗余路径。

### 同步上游官方更新（标准流程）

每周或重大版本发布后执行：

```bash
cd .../<ProjectName>     # 必须在开发 worktree
git fetch upstream
git checkout main
git merge --ff-only upstream/main
git push origin main
git checkout feat/<feature-name>
git rebase main                        # 解决冲突
git push --force-with-lease origin feat/<feature-name>
```

之后构建 worktree 用上一节的同步命令拉取 rebase 后的新 commit。

### 冲突处理决策

- **rebase 顺利**：force-with-lease 推送，进入下一阶段
- **冲突可控**：手动解决，`git add` + `git rebase --continue`
- **冲突大面积爆发**：`git rebase --abort`，从最新 main 创建新分支，对照开发计划文档**重新实施**（这是为什么开发计划必须作为可重放规格保存）

### Git 干净度铁规

- 开发 worktree 的 `git status` **必须**永远是 `nothing to commit, working tree clean` 后才能 rebase / 同步 upstream
- `node_modules`、`dist/`、`build/`、`out/`、`.turbo/`、`target/`、`*.tsbuildinfo` 必须在 `.gitignore` 或 `.git/info/exclude` 里
- 不确定时先 `git clean -nxd`（dry-run）预览，再决定是否 `-fxd` 实删

### 改动最小化原则（降低 rebase 冲突）

为了让上游同步尽可能无冲突：

1. 改动尽量集中、聚焦在最少的文件
2. 不顺手重构周边代码，即使看到优化空间
3. 不在功能 commit 里夹带 lint / 格式化 / 注释润色
4. 每次 rebase 前先 `git diff upstream/main -- <你改过的文件>` 看上游动了什么

### 给 AI Agent 的硬性要求

执行任何代码改动前：

1. 用 `git worktree list` 确认当前所在 worktree
2. 不在错误的 worktree 跑会留下产物的命令
3. commit 前 `git status` 自检，不把构建产物或临时文件提交进去
4. rebase 后强推必须用 `--force-with-lease`，禁用 `--force`
5. 不主动 `git push` 到 main 分支或上游仓库


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
- **Agent pipeline 职责边界原则**: 每层 agent 只做本层的判断，不替下游决策。Analysts → 客观市场状态描述（禁止输出 "Trading Implications/Synthesis" 或 entry/stop/sizing 建议）；Bull/Bear → 举证说理（不做结论）；Research Manager → 综合辩论出方向性研究结论（不是最终投资决策，是给 Trader 的 brief）；Trader → 将 RM 的研究结论**执行参数化**（entry/stop/target/sizing），不独立重评投资逻辑；Risk Debators → 只辩论风险参数（仓位大小/止损位置/对冲），不重新评估投资方向；Portfolio Manager → 唯一的最终决策者。
- **Analyst prompt 模板一致性**: 四个 analyst 的 `ChatPromptTemplate` 外层均应使用同一模式：`"Tools available: {tool_names}.\n\n{system_message}\n\nCurrent date: {current_date}. {instrument_context}"`；news/social/fundamentals 曾有带 "Call ALL required tools / Do NOT output until..." 的不同外层，导致禁令重复且格式不统一。实际的工具调用门控由代码 `if len(result.tool_calls) == 0` 负责，prompt 中的禁令语句是冗余的。
- **Analyst prompt 中的合法 vs. 越界语言**: `"bullish/bearish/neutral"`（市场状态描述）合法；`"Trading Implications"`、`"Trading Synthesis"`、`"entry zone"`、`"stop-loss placement"`、`"risk/reward assessment"`（交易判断）越界——这些词汇会引导 analyst 代替 Trader/PM 做决策。
- **每层 agent 的越界语言（贯穿全链）**: 上一条 analyst 越界词规则同样适用于下游层。Bull/Bear researchers 越界词：`entry`、`risk/reward for entry`、`entry timing`（researcher 论证方向，不论证时机）；Risk debators 越界词：`entry zone`、`entry price levels`、`target price`（risk 层只动 size/stop/staging/hedging，入场价是 Trader 的参数）；Research Manager 越界词：`price levels for entry`、`position size in shares/%`（RM 给研究简报，不给执行参数）。每层 agent 只用本层语言。

### Development Workflow

- **Edit 工具前置要求**: 调用 `Edit` 前必须用 `Read` 工具（非 `rtk read`）读取目标文件，否则报 "File has not been read yet" 错误；`rtk read` 不满足此前置条件。
- **供应商参数传递**: 供应商实现使用`**kwargs`接受额外参数，确保向后兼容。新参数可安全添加到工具层，非相关供应商会忽略这些参数。
- **工具层修改模式**: 修改工具函数时，添加参数并通过`route_to_vendor()`传递。CCXT支持`timeframe`参数用于多时间周期数据获取。
- **CLI 函数分工**: `select_*` 交互选择函数放 `cli/utils.py`（questionary）；简单文本输入 `get_*` 放 `cli/main.py`（`typer.prompt`）；`create_question_box()` 提供展示框，prompt 函数只做裸输入。`main.py` 中的 `get_ticker`/`get_analysis_date` 本地定义有意覆盖 `from cli.utils import *` 导入的同名函数。
- **`data_vendors` 键名**: 精确键名为 `core_stock_apis`、`technical_indicators`、`news_data`、`fundamental_data`、`crypto_market_data`；误用 `news`/`fundamentals` 等错误键名会静默无效（`set_config()` 深合并不报错）。
- **加密货币双 ticker 约定**: CLI 加密模式同时采集两个 ticker——yfinance 格式（如 `BTC-USD`，用于新闻/基本面，同时作为 `propagate()` 的主 ticker）与 CCXT 格式（如 `BTC/USDT`，写入 `config["ccxt_symbol"]`，用于行情/技术面）。
