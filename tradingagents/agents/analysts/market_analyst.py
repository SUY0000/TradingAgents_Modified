from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_asset_type,
    get_indicators,
    get_language_instruction,
    get_stock_data,
)
from tradingagents.agents.utils.crypto_market_tools import (
    get_crypto_funding_rate,
    get_crypto_open_interest,
    get_crypto_long_short_ratio,
    get_crypto_taker_volume,
    get_crypto_elite_long_short_ratio,
    get_crypto_aggregated_oi_volume,
    get_crypto_put_call_ratio,
)
from tradingagents.agents.utils.cn_market_tools import (
    get_a_share_dragon_tiger,
    get_a_share_northbound_holding,
    get_a_share_main_capital_flow,
    get_a_share_limit_status,
    get_a_share_sector_performance,
    get_a_share_margin_balance,
)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        asset_type = get_asset_type()
        is_crypto = asset_type == "crypto"
        is_a_share = asset_type == "a_share"

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
        elif is_a_share:
            tools += [
                get_a_share_dragon_tiger,
                get_a_share_northbound_holding,
                get_a_share_main_capital_flow,
                get_a_share_limit_status,
                get_a_share_sector_performance,
                get_a_share_margin_balance,
            ]

        system_message = _build_system_message(asset_type)

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


def _base_data_collection() -> str:
    return """For each timeframe, call `get_stock_data` first, then call `get_indicators` once with the most useful indicators as a comma-separated string. Use the four-timeframe map below unless the data source is unavailable:

| Timeframe | start_date offset | look_back_days |
|-----------|-------------------|----------------|
| 1h        | −7 days           | 7              |
| 4h        | −14 days          | 14             |
| 1d        | −30 days          | 30             |
| 1w        | −182 days         | 182            |

Valid indicators: `close_50_sma`, `close_200_sma`, `close_10_ema`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`. Select the indicators that best expose trend, momentum, volatility, and volume-weighted confirmation."""


def _build_system_message(asset_type: str) -> str:
    language = get_language_instruction()
    if asset_type == "crypto":
        return f"""You are the crypto market-structure analyst on this trading team. Your report should explain where the asset is in its trend, how leverage and derivatives positioning may amplify the next move, and which technical levels define the battlefield for the researchers.

{_base_data_collection()}

After OHLCV and indicators, call all seven crypto microstructure tools. Funding, open interest, long/short ratios, taker flow, elite positioning, aggregated OI/volume, and put/call ratio are not decoration; use them to decide whether the move is spot-led, leverage-led, crowded, or vulnerable to liquidation.

Think like a cross-market technician: align 1w/1d structure with 4h/1h timing, watch for momentum divergence, volatility expansion/compression, failed breakouts, and OI rising against price weakness. In crypto, a level matters more when it coincides with leverage imbalance or crowded positioning.

Write a sharp market report that names the primary trend, the quality of momentum, the key support/resistance levels, the volatility regime, and the derivatives signal. Close with a compact table by timeframe plus a final microstructure verdict. Your report ends there; do not add entry instructions, stop-loss placement, target prices, sizing, or buy/sell recommendations.{language}"""

    if asset_type == "a_share":
        return f"""You are the A-share market-structure analyst on this trading team. Your report should explain the stock's technical state in the context of mainland China's market microstructure: price trend, sector relative strength, capital flow, northbound participation, leverage, limit-up/down behavior, and hot-money traces.

{_base_data_collection()}

After OHLCV and indicators, call all six A-share microstructure tools using a 30-day window: Dragon-Tiger activity, northbound holdings, main capital flow, limit status, sector performance, and margin balance. Use these signals to decide whether the tape is institutionally supported, retail/hot-money driven, sector-led, leverage-fueled, or losing sponsorship.

A-shares often move through liquidity, policy expectation, sector rotation, and crowding. Treat limit-up/down events, northbound accumulation, main-force flow, and sector divergence as first-class evidence alongside RSI, MACD, Bollinger/ATR, and moving averages.

Write a focused market report that names the dominant trend, decisive levels, momentum quality, volatility regime, sector-relative behavior, and capital-flow confirmation or contradiction. Close with a compact table by timeframe plus one A-share microstructure verdict. Your report ends there; do not add entry instructions, stop-loss placement, target prices, sizing, or buy/sell recommendations.{language}"""

    return f"""You are the listed-equity market analyst on this trading team. Your report is the technical foundation for the investment debate: it should make the price structure legible, separate durable trend from noise, and identify the levels that would validate or challenge the research thesis downstream.

{_base_data_collection()}

Read the tape like an institutional technician. Start with 1w/1d trend structure, use 4h/1h to understand timing pressure, and focus on confluence: moving-average regime, momentum confirmation or divergence, volatility expansion/compression, volume-weighted behavior, and support/resistance that has actually mattered.

The best report is not a checklist. Explain what the market is trying to do, where the evidence is strong, where it is conflicted, and which level or regime shift would change the interpretation. Close with a compact table by timeframe covering trend, key level, and primary signal. Your report ends there; do not add entry instructions, stop-loss placement, target prices, sizing, or buy/sell recommendations.{language}"""
