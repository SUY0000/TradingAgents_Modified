from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_language_instruction,
    get_stock_data,
)
from tradingagents.dataflows.config import get_config
from tradingagents.agents.utils.crypto_market_tools import (
    get_crypto_funding_rate,
    get_crypto_open_interest,
    get_crypto_long_short_ratio,
    get_crypto_taker_volume,
    get_crypto_elite_long_short_ratio,
    get_crypto_aggregated_oi_volume,
    get_crypto_put_call_ratio,
)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        config = get_config()
        vendors = config.get("data_vendors", {})
        is_crypto = (
            vendors.get("core_stock_apis") == "ccxt"
            and vendors.get("technical_indicators") == "ccxt"
        )

        tools = [get_stock_data, get_indicators]
        if is_crypto:
            tools += [
                get_crypto_funding_rate,
                get_crypto_open_interest,
                get_crypto_long_short_ratio,
                get_crypto_taker_volume,
                get_crypto_elite_long_short_ratio,
                get_crypto_aggregated_oi_volume,
                get_crypto_put_call_ratio,
            ]

        system_message = (
            """You are a market analyst. Collect all required data via tools, then write a comprehensive research report.

## Data Collection

For each timeframe, call `get_stock_data` first, then call `get_indicators` **once** with all selected indicators passed as a single comma-separated string (e.g., `"rsi,macd,boll_ub,boll_lb,atr,close_50_sma"`). For crypto (symbol contains '/'), all four timeframes are required; for other assets, multiple timeframes are recommended.

Use these exact date windows (wider ranges don't improve analysis quality):

| Timeframe | start_date offset | look_back_days |
|-----------|-------------------|----------------|
| 1h        | −7 days           | 7              |
| 4h        | −14 days          | 14             |
| 1d        | −30 days          | 30             |
| 1w        | −26 weeks (−182d) | 182            |

OKX metrics: same 14-day window as 4h timeframe.

## Technical Indicators

For each `get_indicators` call, select up to **8 complementary** indicators appropriate for that timeframe. Use exact names as parameters — wrong names will cause tool call failures.

| Category | Indicators (exact parameter names) |
|----------|-------------------------------------|
| Moving Averages | `close_50_sma`, `close_200_sma`, `close_10_ema` |
| MACD | `macd`, `macds`, `macdh` |
| Momentum | `rsi` |
| Volatility | `boll`, `boll_ub`, `boll_lb`, `atr` |
| Volume | `vwma` |

Avoid redundant indicators (e.g., don't select both RSI and StochRSI). The same indicator set may be reused across timeframes, or adjusted per timeframe as market context dictates.

## Report Requirements

Your report must include:
- **Multi-Timeframe Analysis**: for each timeframe summarize trend direction and key indicator readings; then identify trend resonance (where TFs agree), key S/R level convergence, and any conflicting signals
- **Trading Synthesis**: primary trend (1d/1w), entry/exit timing context (1h/4h), risk assessment for cross-TF conflicts
- **Markdown Summary Table** at the end"""
            + (
                """

## MANDATORY: Crypto Derivatives & On-Chain Tools

Call **all 7** tools before writing the report:

| Tool | Additional Parameters | Window |
|------|-----------------------|--------|
| `get_crypto_funding_rate` | symbol, start_date, end_date | 14d |
| `get_crypto_open_interest` | ..., period="4H" | 14d |
| `get_crypto_long_short_ratio` | ..., period="4H" | 14d |
| `get_crypto_taker_volume` | ..., period="4H" | 14d |
| `get_crypto_elite_long_short_ratio` | ..., period="4H" | 14d |
| `get_crypto_aggregated_oi_volume` | ..., period="4H" | 14d |
| `get_crypto_put_call_ratio` | ..., period="1D" | 14d |

Report must include a **"Derivatives & On-Chain Metrics"** section covering: funding rate trend, OI vs price divergence, all-trader vs elite L/S ratio, taker flow, P/C ratio, and an integrated derivatives signal.

**Pre-Report Checklist — do NOT write the report until ALL are complete:**
- [ ] get_stock_data (1h, 4h, 1d, 1w)
- [ ] get_indicators (1h, 4h, 1d, 1w)
- [ ] get_crypto_funding_rate
- [ ] get_crypto_open_interest
- [ ] get_crypto_long_short_ratio
- [ ] get_crypto_taker_volume
- [ ] get_crypto_elite_long_short_ratio
- [ ] get_crypto_aggregated_oi_volume
- [ ] get_crypto_put_call_ratio"""
                if is_crypto
                else ""
            )
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Tools available: {tool_names}.\n\n"
                    "{system_message}\n\n"
                    "Current date: {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
