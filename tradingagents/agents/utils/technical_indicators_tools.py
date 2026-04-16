from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "one or more technical indicators, comma-separated (e.g. 'rsi,macd,boll'). Pass all desired indicators for a timeframe in a single call."],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
    timeframe: Annotated[str, "Timeframe for data (e.g., '1d', '4h', '1h'). Default is '1d'"] = "1d",
) -> str:
    """
    Retrieve one or more technical indicators for a given ticker symbol.
    Pass multiple indicators as a comma-separated string in a single call to minimize round-trips.
    Uses the configured technical_indicators vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        indicator (str): One or more indicator names, comma-separated, e.g. 'rsi,macd,boll,atr'
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
        timeframe (str): Timeframe for data (e.g., '1h', '4h', '1d', '1w'). Default is '1d'
    Returns:
        str: A formatted dataframe containing the technical indicators for the specified ticker symbol and indicators.
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    indicators = [i.strip().lower() for i in indicator.split(",") if i.strip()]
    results = []
    for ind in indicators:
        try:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days, timeframe=timeframe))
        except ValueError as e:
            results.append(str(e))
    return "\n\n".join(results)