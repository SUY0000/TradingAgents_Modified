from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def get_asset_type() -> str:
    from tradingagents.dataflows.config import get_config
    vendors = get_config().get("data_vendors", {})
    if (
        vendors.get("core_stock_apis") == "akshare"
        and vendors.get("technical_indicators") == "akshare"
    ):
        return "a_share"
    if (
        vendors.get("core_stock_apis") == "ccxt"
        and vendors.get("technical_indicators") == "ccxt"
    ):
        return "crypto"
    return "stock"


def get_asset_prompt_context() -> str:
    asset_type = get_asset_type()
    return {
        "stock": (
            "Asset lens: listed equity/ETF. Judge evidence through earnings power, "
            "valuation, sector rotation, institutional positioning, macro discount rates, "
            "and company-specific catalysts."
        ),
        "a_share": (
            "Asset lens: China mainland A-share. Judge evidence through policy tone, "
            "sector rotation, retail attention, northbound/main-force flows, margin balance, "
            "limit-up/down behavior, and domestic peer valuation."
        ),
        "crypto": (
            "Asset lens: crypto asset. Judge evidence through liquidity, leverage, funding/OI, "
            "token supply, protocol or adoption catalysts, regulatory headlines, macro risk appetite, "
            "and reflexive crowd positioning."
        ),
    }[asset_type]


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    asset_type = get_asset_type()
    asset_context = {
        "stock": "Treat it as a listed equity or ETF unless the reports prove otherwise.",
        "a_share": "Treat it as a China mainland A-share with exchange suffix preserved.",
        "crypto": "Treat it as a crypto asset: market/technical data may use the configured CCXT trading pair, while news and fundamentals use this ticker.",
    }[asset_type]
    return (
        f"The instrument to analyze is `{ticker}`. {asset_context} "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`). "
        f"{get_asset_prompt_context()}"
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


class Toolkit:
    """Thin wrapper that carries a config snapshot for tool routing.

    Passed to get_all_tools_for_asset_type() so callers can parameterise
    by asset type without touching the global config singleton.
    """
    def __init__(self, config: dict):
        self.config = config


def _get_asset_type_from_config(config: dict) -> str:
    """Derive asset type from a config dict (without reading global config)."""
    vendors = config.get("data_vendors", {})
    if (
        vendors.get("core_stock_apis") == "akshare"
        and vendors.get("technical_indicators") == "akshare"
    ):
        return "a_share"
    if (
        vendors.get("core_stock_apis") == "ccxt"
        and vendors.get("technical_indicators") == "ccxt"
    ):
        return "crypto"
    return "stock"


def get_tools_for_category(toolkit: "Toolkit", config: dict, category: str) -> list:
    """Return the tool list for one analyst category given the current asset type.

    category: "market" | "news" | "fundamentals" | "sentiment"
    """
    asset_type = _get_asset_type_from_config(config)
    is_crypto = asset_type == "crypto"
    is_a_share = asset_type == "a_share"

    if category == "market":
        from tradingagents.agents.utils.core_stock_tools import get_stock_data
        from tradingagents.agents.utils.technical_indicators_tools import get_indicators
        tools = [get_stock_data, get_indicators]
        if is_crypto:
            from tradingagents.agents.utils.crypto_market_tools import (
                get_crypto_funding_rate,
                get_crypto_open_interest,
                get_crypto_long_short_ratio,
                get_crypto_taker_volume,
                get_crypto_elite_long_short_ratio,
                get_crypto_aggregated_oi_volume,
                get_crypto_put_call_ratio,
                get_okx_ticker_snapshot,
                get_okx_perp_basis,
                get_okx_funding_rate_now,
                get_okx_open_interest_now,
                get_okx_liquidation_orders,
            )
            tools += [
                get_crypto_funding_rate,
                get_crypto_open_interest,
                get_crypto_long_short_ratio,
                get_crypto_taker_volume,
                get_crypto_elite_long_short_ratio,
                get_crypto_aggregated_oi_volume,
                get_crypto_put_call_ratio,
                get_okx_ticker_snapshot,
                get_okx_perp_basis,
                get_okx_funding_rate_now,
                get_okx_open_interest_now,
                get_okx_liquidation_orders,
            ]
        elif is_a_share:
            from tradingagents.agents.utils.cn_market_tools import (
                get_a_share_dragon_tiger,
                get_a_share_northbound_holding,
                get_a_share_main_capital_flow,
                get_a_share_limit_status,
                get_a_share_sector_performance,
                get_a_share_margin_balance,
            )
            tools += [
                get_a_share_dragon_tiger,
                get_a_share_northbound_holding,
                get_a_share_main_capital_flow,
                get_a_share_limit_status,
                get_a_share_sector_performance,
                get_a_share_margin_balance,
            ]
        return tools

    if category == "news":
        if is_crypto:
            from tradingagents.agents.utils.crypto_news_tools import (
                get_free_crypto_news,
                get_okx_exchange_announcements,
                get_okx_delivery_events,
            )
            return [get_free_crypto_news, get_okx_exchange_announcements, get_okx_delivery_events]
        else:
            from tradingagents.agents.utils.news_data_tools import get_news, get_global_news
            if is_a_share:
                return [get_news, get_global_news]
            from tradingagents.agents.utils.news_data_tools import get_insider_transactions
            return [get_news, get_global_news, get_insider_transactions]

    if category == "fundamentals":
        if is_crypto:
            from tradingagents.agents.utils.crypto_fundamental_tools import (
                get_token_profile,
                get_protocol_metrics,
            )
            return [get_token_profile, get_protocol_metrics]
        from tradingagents.agents.utils.fundamental_data_tools import (
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        )
        tools = [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement]
        if is_a_share:
            from tradingagents.agents.utils.fundamental_data_tools import (
                get_earnings_forecast,
                get_shareholder_count,
                get_valuation_comparison,
            )
            tools += [get_earnings_forecast, get_shareholder_count, get_valuation_comparison]
        return tools

    if category == "sentiment":
        if is_a_share:
            from tradingagents.agents.utils.cn_sentiment_tools import (
                get_a_share_hot_rank_history,
                get_a_share_research_reports,
                get_a_share_institutional_research,
            )
            return [
                get_a_share_hot_rank_history,
                get_a_share_research_reports,
                get_a_share_institutional_research,
            ]
        if is_crypto:
            from tradingagents.agents.utils.crypto_sentiment_tools import (
                get_crypto_smart_money,
                get_crypto_margin_leverage,
            )
            return [get_crypto_smart_money, get_crypto_margin_leverage]
        # stock: get_news is the only @tool-decorated sentiment source
        from tradingagents.agents.utils.news_data_tools import get_news
        return [get_news]

    return []


def get_all_tools_for_asset_type(toolkit: "Toolkit", config: dict) -> list:
    """Return deduplicated tools across all four analyst categories for the current asset type."""
    seen = set()
    tools = []
    for category in ("market", "news", "fundamentals", "sentiment"):
        for t in get_tools_for_category(toolkit, config, category):
            if id(t) not in seen:
                seen.add(id(t))
                tools.append(t)
    return tools
