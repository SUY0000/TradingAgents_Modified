"""LangChain tools for crypto news analyst.

Four tools: OKX announcements, delivery events, economic calendar, and CryptoPanic news.
These replace the generic yfinance + global_news tools for the crypto news analyst path.
"""

from langchain_core.tools import tool
from typing import Annotated


@tool
def get_crypto_news_cryptopanic(
    currency: Annotated[str, "Uppercase currency code, e.g. 'BTC', 'ETH'"],
    curr_date: Annotated[str, "Analysis date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days to look back for news (default 7)"] = 7,
    limit: Annotated[int, "Max posts to return (default 30)"] = 30,
) -> str:
    """Fetch recent crypto news from CryptoPanic with community vote labels.

    CryptoPanic aggregates crypto news from multiple sources and lets the
    community vote on importance. The `important` vote count signals that
    crypto-native traders found this price-relevant. Positive/negative votes
    reflect directional sentiment on each headline.

    Returns headlines with kind (news/media/analysis), publication date,
    positive votes, negative votes, and important flags.
    """
    from tradingagents.dataflows.cryptopanic_data import get_cryptopanic_news
    from tradingagents.dataflows.crypto_symbols import get_cp_currency
    currency_code = get_cp_currency(currency) if "-" in currency else currency.upper()
    return get_cryptopanic_news(currency_code, curr_date, look_back_days=look_back_days, limit=limit)


@tool
def get_okx_exchange_announcements(
    symbol: Annotated[str, "Crypto ticker or currency, e.g. 'BTC-USD' or 'BTC'"],
    curr_date: Annotated[str, "Analysis date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days to scan for relevant announcements (default 14)"] = 14,
) -> str:
    """Fetch OKX exchange announcements relevant to this crypto asset.

    OKX announcements include: new listings, delistings, trading suspensions,
    contract specification changes, system maintenance, and rule updates.
    Exchange-level events directly affect liquidity, tradability, and price.

    Pass the currency code (e.g. 'BTC') or full ticker (e.g. 'BTC-USD').
    """
    from tradingagents.dataflows.okx_data import get_okx_announcements, _to_ccy
    ccy = _to_ccy(symbol) if ("/" in symbol or "-" in symbol) else symbol.upper()
    return get_okx_announcements(ccy, curr_date, look_back_days=look_back_days)


@tool
def get_okx_delivery_events(
    symbol: Annotated[str, "Crypto ticker or currency, e.g. 'BTC-USD' or 'BTC'"],
    inst_type: Annotated[str, "Contract type: FUTURES (default) or OPTION"] = "FUTURES",
) -> str:
    """Fetch recent futures delivery and options exercise events from OKX.

    Delivery events are price catalysts: contracts settle at index price,
    which can create significant buying/selling pressure as expiry approaches.
    Use to identify if a major contract expiry is imminent (within 7 days)
    or just occurred (post-expiry positioning reset).
    """
    from tradingagents.dataflows.okx_data import get_okx_delivery_exercise, _to_ccy
    ccy = _to_ccy(symbol) if ("/" in symbol or "-" in symbol) else symbol.upper()
    return get_okx_delivery_exercise(inst_type, ccy)


@tool
def get_okx_macro_calendar(
    curr_date: Annotated[str, "Analysis date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days of calendar context (default 7)"] = 7,
) -> str:
    """Fetch crypto-relevant macro economic calendar events from OKX.

    Includes CPI, FOMC, NFP, and other macro events that historically
    move crypto markets. High-importance events (3/3) in the next 48 hours
    often trigger volatility regardless of direction.
    """
    from tradingagents.dataflows.okx_data import get_okx_economic_calendar
    return get_okx_economic_calendar(curr_date, look_back_days=look_back_days)
