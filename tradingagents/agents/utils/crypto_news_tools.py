"""LangChain tools for crypto news analyst.

Free crypto news uses public RSS feeds; OKX tools cover exchange announcements
and delivery events.
"""

from langchain_core.tools import tool
from typing import Annotated


@tool
def get_free_crypto_news(
    currency: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
    curr_date: Annotated[str, "Analysis date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days to look back for news (default 7)"] = 7,
    limit: Annotated[int, "Max posts to return (default 30)"] = 30,
) -> str:
    """Fetch recent crypto news from public RSS feeds without API keys."""
    from tradingagents.dataflows.crypto_symbols import ccxt_to_base
    from tradingagents.dataflows.free_crypto_news_data import get_free_crypto_news as fetch_news
    return fetch_news(ccxt_to_base(currency), curr_date, look_back_days=look_back_days, limit=limit)


@tool
def get_okx_exchange_announcements(
    symbol: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
    curr_date: Annotated[str, "Analysis date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days to scan for relevant announcements (default 14)"] = 14,
) -> str:
    """Fetch OKX exchange announcements relevant to this crypto asset.

    OKX announcements include: new listings, delistings, trading suspensions,
    contract specification changes, system maintenance, and rule updates.
    Exchange-level events directly affect liquidity, tradability, and price.
    """
    from tradingagents.dataflows.okx_data import get_okx_announcements, _to_ccy
    ccy = _to_ccy(symbol)
    return get_okx_announcements(ccy, curr_date, look_back_days=look_back_days)


@tool
def get_okx_delivery_events(
    symbol: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
    inst_type: Annotated[str, "Contract type: FUTURES (default) or OPTION"] = "FUTURES",
) -> str:
    """Fetch recent futures delivery and options exercise events from OKX.

    Delivery events are price catalysts: contracts settle at index price,
    which can create significant buying/selling pressure as expiry approaches.
    Use to identify if a major contract expiry is imminent (within 7 days)
    or just occurred (post-expiry positioning reset).
    """
    from tradingagents.dataflows.okx_data import get_okx_delivery_exercise, _to_ccy
    ccy = _to_ccy(symbol)
    return get_okx_delivery_exercise(inst_type, ccy)
