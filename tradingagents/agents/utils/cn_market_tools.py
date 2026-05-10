"""LangChain tools for A-share (China mainland) market microstructure data.

These tools are only loaded when the market analyst detects an A-share context
(core_stock_apis == "akshare" AND technical_indicators == "akshare").
They expose akshare-sourced data — Dragon-Tiger List, northbound holdings,
main capital flow, limit-up/down status, sector performance, and margin balance
— as callable LangChain tools.

All tools route through route_to_vendor() using the "cn_market_data" category,
which defaults to the "akshare" vendor defined in default_config.py.
"""

from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_a_share_dragon_tiger(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch Dragon-Tiger List (龙虎榜) historical appearances for an A-share stock.

    The Dragon-Tiger List is triggered when a stock meets abnormal-fluctuation
    criteria (e.g. ≥3 consecutive limit-ups, intraday swing >15%, or unusual
    volume). It records the dates when the stock appeared on the list.
    Frequent appearances signal active hot-money (游资) or institutional activity.
    Absence from the list in a period indicates no abnormal flags — typical for
    large-cap blue chips.
    """
    return route_to_vendor("get_dragon_tiger", symbol, start_date, end_date)


@tool
def get_a_share_northbound_holding(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch northbound (Stock Connect) holding changes for an A-share stock.

    Tracks Hong Kong-registered foreign capital's positions via the
    Shanghai-HK (沪港通) and Shenzhen-HK (深港通) Stock Connect programs.
    - Consistently rising northbound holdings: foreign institutional accumulation
    - Consistently falling holdings: foreign distribution / risk-off
    - Northbound is considered "smart money"; its direction often leads price.
    Note: Not all A-shares are eligible for Stock Connect (check Connect List).
    """
    return route_to_vendor("get_northbound_holding", symbol, start_date, end_date)


@tool
def get_a_share_main_capital_flow(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch main-force capital flow (主力资金流向) for an A-share stock.

    Breaks net inflow/outflow into order-size tiers (units: CNY):
    - 超大单 (super-large, ≥1M): institutional block trades
    - 大单 (large, 100k–1M): active traders / small institutions
    - 中单 (medium, 10k–100k): semi-active retail
    - 小单 (small, <10k): passive retail
    Persistent positive net inflow in super-large + large tiers indicates
    institutional accumulation. Retail-heavy inflow with institutional outflow
    is a classic distribution pattern.
    """
    return route_to_vendor("get_main_capital_flow", symbol, start_date, end_date)


@tool
def get_a_share_limit_status(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Detect limit-up (涨停) / limit-down (跌停) events for an A-share stock.

    A-shares have daily price limits: ±10% for Main Board (主板), ±20% for
    STAR Market (科创板) and ChiNext (创业板), ±30% for newly listed stocks.
    Limit-up = close-to-close gain ≥+9.9%; limit-down = loss ≤-9.9%.
    - Multiple consecutive limit-ups: strong momentum, often sector-rotation driven
    - Limit-down: panic selling, or response to negative news / fundamentals
    - A single limit-up in otherwise flat trading: possible one-time catalyst
    """
    return route_to_vendor("get_limit_status", symbol, start_date, end_date)


@tool
def get_a_share_sector_performance(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch the stock's Shenwan (申万) Level-1 industry sector performance.

    Resolves the stock's Shenwan L1 industry classification (e.g., 食品饮料,
    医药生物, 电子), then fetches the sector index's OHLCV for comparison.
    Use for:
    - Sector rotation detection: is this sector gaining or losing relative to market?
    - Relative strength: does the stock outperform its sector peers (stock-specific alpha)?
    - Sector momentum context: a stock rising with its sector has systemic tailwind;
      a stock falling while its sector rises has stock-specific headwind.
    """
    return route_to_vendor("get_sector_performance", symbol, start_date, end_date)


@tool
def get_a_share_margin_balance(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch margin finance and short-selling balance (融资融券) for an A-share stock.

    融资余额 (margin financing): outstanding leveraged long exposure.
    融券余额 (margin short-selling): outstanding borrowed-share short exposure.
    - Rising 融资余额: leveraged bulls accumulating (bullish, but adds liquidation risk)
    - Falling 融资余额: de-leveraging (bearish sentiment or forced liquidations)
    - Rising 融券余额: institutional short interest building (bearish signal)
    Sampled weekly to limit API calls. Available only for SSE/SZSE eligible stocks.
    """
    return route_to_vendor("get_margin_balance", symbol, start_date, end_date)
