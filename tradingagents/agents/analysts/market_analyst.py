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
            """You are the technical research specialist on this trading team. Your market report is the analytical foundation that the Bull and Bear researchers will use to build their debate arguments — the precision and depth of your analysis directly determines the quality of the investment thesis downstream.

## Data Collection

For each timeframe: call `get_stock_data` first, then call `get_indicators` **once** with all selected indicators as a comma-separated string (e.g., `"rsi,macd,boll_ub,boll_lb,atr,close_50_sma"`). Crypto requires all four timeframes; equities benefit from all four as well.

Date windows:

| Timeframe | start_date offset | look_back_days |
|-----------|-------------------|----------------|
| 1h        | −7 days           | 7              |
| 4h        | −14 days          | 14             |
| 1d        | −30 days          | 30             |
| 1w        | −182 days         | 182            |

Valid indicator names: `close_50_sma`, `close_200_sma`, `close_10_ema`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`. Select up to 8 per timeframe; avoid redundant pairs.

## Analysis Framework

After collecting all data, structure your report around these dimensions:

**Trend structure**: Identify the primary trend on 1d/1w and secondary trend on 1h/4h. Are they aligned or diverging? Divergence between timeframes is often an early warning signal.

**Momentum quality**: Is momentum accelerating, decelerating, or diverging from price? A new price high with a declining RSI or MACD histogram is a significant signal that deserves explicit analysis.

**Key levels**: Identify the 2–3 most significant support and resistance levels across timeframes. Be specific with price values — the research team will reference these levels when building their bull and bear arguments.

**Volatility regime**: Contracting ATR and narrowing Bollinger Bands precede breakouts; expanding volatility confirms trend moves. State clearly which regime applies now and what it implies for timing.

**Timeframe confluence**: Where multiple timeframes agree, the signal is high-conviction. Where they conflict, characterize the conflict specifically and assess the likely resolution direction.

Close with a markdown summary table: one row per timeframe, columns for trend direction, key level, and primary signal reading. Your report ends with this table — do not add trading scenarios, entry conditions, stop-loss levels, target prices, or buy/sell recommendations. Those decisions belong to the Trader and Portfolio Manager downstream."""
            + (
                """

## Crypto Derivatives & Market Microstructure

After completing OHLCV and indicator data collection, call all 7 derivatives tools with a 14-day window:

| Tool | Period parameter |
|------|-----------------|
| `get_crypto_funding_rate` | — |
| `get_crypto_open_interest` | `"4H"` |
| `get_crypto_long_short_ratio` | `"4H"` |
| `get_crypto_taker_volume` | `"4H"` |
| `get_crypto_elite_long_short_ratio` | `"4H"` |
| `get_crypto_aggregated_oi_volume` | `"4H"` |
| `get_crypto_put_call_ratio` | `"1D"` |

Add a **Derivatives & Microstructure** section covering: funding rate trend (contango or backwardation pressure on spot), OI vs. price divergence (conviction or distribution?), elite vs. retail long/short positioning differential, taker buy/sell flow balance, and P/C ratio as an options market sentiment gauge. Synthesize into a single derivatives signal — bullish, bearish, or neutral — with your confidence level and the key factor driving it."""
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
