from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol.
    Uses the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing comprehensive fundamental data
    """
    return route_to_vendor("get_fundamentals", ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol.
    Uses the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing balance sheet data
    """
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol.
    Uses the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing cash flow statement data
    """
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve income statement data for a given ticker symbol.
    Uses the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing income statement data
    """
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


@tool
def get_earnings_forecast(
    ticker: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Retrieve earnings forecast / performance pre-announcement (业绩预告) for an A-share.

    Scans the most recent quarterly report periods and returns any management
    pre-announcements covering net profit expectations, YoY change magnitude,
    announcement type (预增/续盈/略增/扭亏/预减/续亏), and management explanation.
    Only available in A-share mode (akshare vendor).
    """
    return route_to_vendor("get_earnings_forecast", ticker, curr_date)


@tool
def get_shareholder_count(
    ticker: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Retrieve shareholder count history (股东户数) for an A-share.

    Declining shareholder count with rising price signals institutional concentration
    (positive — 'smart money' accumulating). Rising shareholder count signals retail
    dispersion. Includes per-share and total market values, total share count, and
    QoQ change ratios. Only available in A-share mode (akshare vendor).
    """
    return route_to_vendor("get_shareholder_count", ticker, curr_date)


@tool
def get_valuation_comparison(
    ticker: Annotated[str, "A-share ticker, e.g. '600519.SH' or '000001.SZ'"],
    curr_date: Annotated[str, "Current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Retrieve peer valuation comparison within the Shenwan industry (同行估值对标).

    Returns PE/PB/PS/PEG and EV/EBITDA metrics for the target company,
    its industry median and average, and key sector peers. Use to assess whether
    the stock trades at a premium or discount relative to its peer group.
    Only available in A-share mode (akshare vendor).
    """
    return route_to_vendor("get_valuation_comparison", ticker, curr_date)