from langchain_core.tools import tool
from typing import Annotated, Optional
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    return route_to_vendor("get_news", ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[Optional[int], "Days to look back; omit to use the configured default"] = None,
    limit: Annotated[Optional[int], "Max articles to return; omit to use the configured default"] = None,
    ticker: Annotated[str, "Ticker symbol of the stock being analyzed (used for sector-filtered policy news in A-share mode)"] = None,
) -> str:
    """
    Retrieve global / macro news data.
    In A-share mode (akshare vendor), news is sourced from CCTV daily transcripts
    and filtered by the stock's Shenwan industry sector keywords so that only
    policy and macro items relevant to this sector are returned.
    In US-stock / crypto mode, returns general global macro news.
    Uses the configured news_data vendor. Defaults for look_back_days and
    limit come from DEFAULT_CONFIG when not specified.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back; omit to inherit config
        limit (int): Maximum number of articles to return; omit to inherit config
        ticker (str): Ticker of the stock being analyzed (pass the same ticker used for get_news)
    Returns:
        str: A formatted string containing global/sector news data
    """
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit, ticker=ticker)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker)
