"""LangChain tools for A-share (China mainland) sentiment / social-layer data.

These tools are only loaded when the social analyst detects an A-share context
(core_stock_apis == "akshare" AND technical_indicators == "akshare").
They expose akshare-sourced data — retail attention rank, sell-side research
reports, and institutional on-site research visits — as callable LangChain tools.

All tools route through route_to_vendor() using the "cn_sentiment_data" category,
which defaults to the "akshare" vendor.
"""

from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_a_share_hot_rank_history(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back (default 30)"] = 30,
) -> str:
    """Fetch East Money retail-investor attention rank history (人气排名) for an A-share.

    Returns a daily time-series of this stock's popularity ranking among all
    A-share tickers on East Money (东方财富). A lower rank number indicates
    higher retail attention. Tracks new-fan ratio (新晋粉丝) vs loyal-fan ratio
    (铁杆粉丝). Use to gauge retail-investor interest and crowding dynamics.
    """
    return route_to_vendor("get_hot_rank_history", symbol, curr_date, look_back_days)


@tool
def get_a_share_research_reports(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back (default 90)"] = 90,
) -> str:
    """Fetch sell-side analyst research reports for an A-share (券商研报).

    Returns report titles, issuing institution, East Money rating (买入/增持/中性/减持),
    earnings forecasts (EPS / PE for upcoming 2–3 years), and publication date.
    Use to gauge sell-side consensus and identify recent rating upgrades/downgrades
    or target-price revisions.
    """
    return route_to_vendor("get_research_reports", symbol, curr_date, look_back_days)


@tool
def get_a_share_institutional_research(
    symbol: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back (default 180)"] = 180,
) -> str:
    """Fetch buy-side / institutional on-site research activities for an A-share (机构调研).

    Shows which institutions (funds, brokerages, private equity) visited the company,
    reception date, number of visiting institutions, format (现场参观/电话会议/etc.),
    and company contact personnel. Frequent high-count institutional visits ahead of
    a price move often signal early institutional accumulation. Low visitation suggests
    limited institutional interest.
    """
    return route_to_vendor("get_institutional_research", symbol, curr_date, look_back_days)
