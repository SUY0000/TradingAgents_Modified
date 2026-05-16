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


        
