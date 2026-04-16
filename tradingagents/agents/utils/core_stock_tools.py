from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    timeframe: Annotated[str, "Timeframe for data (e.g., '1h', '4h', '1d', '1w'). Default is '1d'"] = "1d",
    **kwargs
) -> str:
    """
    Retrieve price data (OHLCV) for a given ticker symbol.
    Uses the configured core_stock_apis vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM, BTC/USDT
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
        timeframe (str): Timeframe for data (e.g., '1h', '4h', '1d', '1w'). Default is '1d'
    Returns:
        str: A formatted dataframe containing the price data for the specified ticker symbol in the specified date range.
    """
    return route_to_vendor("get_stock_data", symbol, start_date, end_date, timeframe=timeframe, **kwargs)
