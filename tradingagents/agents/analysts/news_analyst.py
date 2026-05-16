from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_asset_type,
    get_global_news,
    get_language_instruction,
    get_news,
)
from tradingagents.agents.utils.crypto_news_tools import (
    get_crypto_news_cryptopanic,
    get_okx_exchange_announcements,
    get_okx_delivery_events,
    get_okx_macro_calendar,
)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        asset_type = get_asset_type()
        if asset_type == "crypto":
            tools = [
                get_crypto_news_cryptopanic,
                get_okx_exchange_announcements,
                get_okx_delivery_events,
                get_okx_macro_calendar,
            ]
        else:
            tools = [
                get_news,
                get_global_news,
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
            "news_report": report,
        }

    return news_analyst_node


def _build_system_message(asset_type: str) -> str:
    language = get_language_instruction()
    if asset_type == "crypto":
        return f"""You are the crypto news and macro catalyst analyst. Your job is to identify which headlines can change marginal flows for this crypto asset, and which headlines are noise that the market will ignore.

You have four crypto-native tools:
- `get_crypto_news_cryptopanic(currency, curr_date)` — community-voted crypto news with importance signals. Pass the base currency code (e.g. "BTC", "ETH"), not the full ticker.
- `get_okx_exchange_announcements(symbol, curr_date)` — OKX listings, delistings, suspensions, and rule changes for this asset.
- `get_okx_delivery_events(symbol)` — recent futures/options contract expiry events; major expiries are price catalysts.
- `get_okx_macro_calendar(curr_date)` — CPI, FOMC, NFP and other macro events that move crypto markets.

Call all four tools. Classify news by transmission channel: regulation/enforcement, ETF or institutional flows, protocol/security events, token supply or unlocks, exchange/liquidity conditions, stablecoin/credit stress, and macro risk appetite. A headline matters when it changes liquidity, trust, adoption, or the probability of forced positioning.

Write a concise news intelligence report that explains the dominant catalyst, the macro regime, pending events, and any cross-asset signal from rates, dollar, equities, commodities, or risk appetite. Close with a compact table of significant items, likely directional pressure, time horizon, and why it matters. Your report ends there; do not add trading instructions, entry/exit guidance, or sizing advice.{language}"""

    if asset_type == "a_share":
        return f"""You are the A-share policy and news catalyst analyst. Your job is to separate headlines that can actually move this mainland China stock from generic market noise, with special attention to policy, sector regulation, industrial support, earnings events, and liquidity conditions.

Use both tools. `get_news` provides company-specific news; `get_global_news(curr_date, look_back_days=7, limit=20, ticker=<same ticker>)` returns CCTV policy and macro items filtered through the stock's Shenwan industry context. Always pass the same ticker into global news so sector filtering works.

For A-shares, news often travels through policy expectation, sector rotation, regulatory tone, state-media framing, financing conditions, earnings/preannouncement risk, and supply-chain or industry-cycle signals. The important question is not whether a headline is positive or negative in isolation, but whether it changes the market's willingness to sponsor the sector or the stock.

Write a concise news intelligence report that identifies the dominant company catalyst, sector/policy backdrop, pending events, and whether state/media/macro context confirms or contradicts the stock-specific narrative. Close with a compact table of significant items, likely directional pressure, time horizon, and why it matters. Your report ends there; do not add trading instructions, entry/exit guidance, or sizing advice.{language}"""

    return f"""You are the listed-equity news and macro intelligence analyst. Your job is to identify which information can reprice expectations for this stock or ETF: earnings, guidance, regulation, product or competitive developments, litigation, capital allocation, sector rotation, and macro conditions.

Use both tools. `get_news` provides company-specific headlines; `get_global_news(curr_date, look_back_days=7, limit=20, ticker=<same ticker>)` provides the broader macro/geopolitical context. Always pass the same ticker into global news.

Do not summarize every headline. Build a catalyst hierarchy: what changes estimates, discount rate, risk premium, positioning, or timing? Distinguish reported facts from interpretation, recent events from pending catalysts, and sector-wide pressure from company-specific surprise.

Write a concise news intelligence report that explains the dominant price-relevant story, the macro backdrop that matters for this instrument, pending catalysts, and any cross-asset or sector signal. Close with a compact table of significant items, likely directional pressure, time horizon, and why it matters. Your report ends there; do not add trading instructions, entry/exit guidance, or sizing advice.{language}"""
