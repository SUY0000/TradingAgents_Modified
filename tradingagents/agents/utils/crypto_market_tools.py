"""LangChain tools for OKX crypto market microstructure data.

These tools are only loaded when the market analyst detects a crypto (CCXT) context.
They expose OKX REST API data — funding rates, open interest, long/short ratios,
taker volume, elite trader ratios, and put/call ratio — as callable LangChain tools.

All tools route through route_to_vendor() using the "crypto_market_data" category,
which defaults to the "okx" vendor defined in default_config.py.
"""

from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_crypto_funding_rate(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch historical funding rates for a crypto perpetual swap from OKX.

    Funding rate is settled every 8 hours. Indicates cost of holding leveraged positions:
    - Positive rate: longs pay shorts (market is bullishly biased)
    - Negative rate: shorts pay longs (market is bearishly biased)
    Persistently high/low rates signal crowded trades and potential reversals.

    Returns CSV with columns: timestamp, inst_id, funding_rate, realized_rate, method
    """
    return route_to_vendor("get_funding_rate", symbol, start_date, end_date)


@tool
def get_crypto_open_interest(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D, 1W (default 4H)"] = "4H",
) -> str:
    """Fetch open interest history for a crypto contract from OKX.

    Open interest = total number of outstanding contracts held by market participants.
    - OI rising + price rising: trend confirmation (bullish)
    - OI rising + price falling: trend confirmation (bearish)
    - OI falling + price rising: potential reversal (short covering)
    - OI falling + price falling: potential bottom (long liquidation exhausted)

    Returns CSV with columns: timestamp, open_interest_contracts, open_interest_ccy
    """
    return route_to_vendor("get_open_interest", symbol, start_date, end_date, period=period)


@tool
def get_crypto_long_short_ratio(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D, 1W (default 4H)"] = "4H",
) -> str:
    """Fetch long/short account ratio for all traders from OKX.

    Measures the ratio of accounts holding long vs short positions.
    - Ratio > 1: more accounts are long (retail bullish bias — potential contrarian short)
    - Ratio < 1: more accounts are short (retail bearish bias — potential contrarian long)
    Extreme readings (e.g. ratio > 2 or < 0.5) often precede reversals.

    Returns CSV with columns: timestamp, long_short_ratio
    """
    return route_to_vendor("get_long_short_ratio", symbol, start_date, end_date, period=period)


@tool
def get_crypto_taker_volume(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D, 1W (default 4H)"] = "4H",
) -> str:
    """Fetch contract taker buy/sell volume from OKX.

    Taker volume measures aggressive order flow — market orders that consume liquidity.
    - buy_sell_ratio > 1: more aggressive buying (bulls dominating)
    - buy_sell_ratio < 1: more aggressive selling (bears dominating)
    Use alongside price action to confirm momentum or spot divergences.

    Returns CSV with columns: timestamp, taker_sell_vol, taker_buy_vol, buy_sell_ratio
    """
    return route_to_vendor("get_taker_volume", symbol, start_date, end_date, period=period)


@tool
def get_crypto_elite_long_short_ratio(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D, 1W (default 4H)"] = "4H",
) -> str:
    """Fetch elite (top-trader) long/short ratios from OKX — both account count and position size.

    Elite traders are OKX's top 5% by account equity. Their positioning often diverges
    from retail and tends to lead price direction.
    - elite_account_ls_ratio: ratio of elite accounts long vs short
    - elite_position_ls_ratio: ratio of elite notional position long vs short
    When elite_position_ls_ratio diverges from retail long_short_ratio, follow the elite.

    Returns CSV with columns: timestamp, elite_account_ls_ratio, elite_position_ls_ratio
    """
    return route_to_vendor(
        "get_elite_long_short_ratio", symbol, start_date, end_date, period=period
    )


@tool
def get_crypto_aggregated_oi_volume(
    symbol: Annotated[str, "Crypto trading pair, e.g. 'BTC/USDT' or 'BTC'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D, 1W (default 4H)"] = "4H",
) -> str:
    """Fetch aggregated open interest and trading volume from OKX.

    Combines OI and volume into a single dataset for trend analysis:
    - OI up + Volume up: strong trend continuation
    - OI up + Volume down: weakening momentum, potential reversal
    - OI down + Volume up: aggressive position closing, potential reversal
    - OI down + Volume down: sideways/consolidation

    Returns CSV with columns: timestamp, open_interest, volume
    """
    return route_to_vendor(
        "get_aggregated_oi_volume", symbol, start_date, end_date, period=period
    )


@tool
def get_crypto_put_call_ratio(
    symbol: Annotated[str, "Crypto asset, typically 'BTC' or 'ETH'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: Annotated[str, "Granularity: 8H or 1D (default 1D)"] = "1D",
) -> str:
    """Fetch options put/call ratio from OKX.

    The put/call ratio measures options market sentiment:
    - P/C ratio > 1: more put buying than calls (bearish hedging/speculation)
    - P/C ratio < 1: more call buying (bullish sentiment)
    - Extreme high P/C (e.g. > 1.5): potential contrarian bullish signal (fear exhaustion)
    - Extreme low P/C (e.g. < 0.5): potential contrarian bearish signal (complacency)

    Returns CSV with columns: timestamp, oi_put_call_ratio, vol_put_call_ratio
    """
    return route_to_vendor("get_put_call_ratio", symbol, start_date, end_date, period=period)
