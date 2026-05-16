"""LangChain tools for crypto fundamentals analyst.

Two tools covering crypto-native fundamentals:
- Token profile (CoinGecko): supply schedule, developer activity, community
- Protocol metrics (DefiLlama): TVL, fees, revenue for DeFi protocols
"""

from langchain_core.tools import tool
from typing import Annotated


@tool
def get_token_profile(
    ticker: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
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
    ticker: Annotated[str, "CCXT symbol or base currency, e.g. 'UNI/USDT', 'ETH/USDT:USDT', 'UNI'"],
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
