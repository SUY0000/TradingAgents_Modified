"""LangChain tools for crypto fundamentals analyst.

Three tools covering crypto-native fundamentals:
- Token profile (CoinGecko): supply schedule, developer activity, community
- Protocol metrics (DefiLlama): TVL, fees, revenue for DeFi protocols
- Public borrow info (OKX): lending rate + depth as capital cost signal
"""

from langchain_core.tools import tool
from typing import Annotated


@tool
def get_token_profile(
    ticker: Annotated[str, "yfinance-style ticker, e.g. 'BTC-USD', 'ETH-USD', 'UNI-USD'"],
) -> str:
    """Fetch token supply, developer activity, and community data from CoinGecko.

    Returns crypto-native fundamentals:
    - Supply schedule: circulating, total, max supply; FDV; market cap
    - Developer health: GitHub stars, forks, commits (4-week), contributors
    - Community size: Twitter followers, Reddit subscribers, Telegram users
    - Price context: 7d and 30d price change

    Use to assess supply discipline (inflation risk, unlock pressure), developer
    activity as a proxy for protocol durability, and community as an adoption signal.
    """
    from tradingagents.dataflows.crypto_symbols import get_cg_id
    from tradingagents.dataflows.coingecko_data import get_coingecko_fundamentals_block
    cg_id = get_cg_id(ticker)
    return get_coingecko_fundamentals_block(cg_id)


@tool
def get_protocol_metrics(
    ticker: Annotated[str, "yfinance-style ticker, e.g. 'UNI-USD', 'ETH-USD'"],
) -> str:
    """Fetch DeFi protocol TVL, fees, and revenue from DefiLlama.

    Returns:
    - Total Value Locked (TVL): capital deployed in the protocol
    - Protocol fees (24h, 7d): revenue from user activity
    - Protocol revenue: fees retained by the protocol (not distributed to LPs)

    Use to assess real economic activity. For non-DeFi tokens (BTC, XRP),
    this tool returns a graceful 'not a DeFi protocol' message — call it
    anyway; the absence itself is informative.
    """
    from tradingagents.dataflows.crypto_symbols import get_defillama_slug
    from tradingagents.dataflows.defillama_data import get_defillama_protocol
    slug = get_defillama_slug(ticker)
    return get_defillama_protocol(slug)


@tool
def get_public_borrow(
    ticker: Annotated[str, "yfinance-style ticker, e.g. 'BTC-USD', 'ETH-USD'"],
) -> str:
    """Fetch OKX savings lending rate and available borrow depth for this asset.

    The OKX savings pool rate reflects the cost of borrowing this asset:
    - High borrow rate + low available amount: strong short demand or supply scarcity
    - Low borrow rate + high available amount: borrowing demand is weak

    In crypto, elevated borrow rates for an asset often coincide with short-selling
    pressure or yield-farming demand, both of which affect price dynamics.
    """
    from tradingagents.dataflows.crypto_symbols import get_okx_ccy
    from tradingagents.dataflows.okx_data import get_okx_public_borrow
    ccy = get_okx_ccy(ticker)
    return get_okx_public_borrow(ccy)
