"""LangChain tools for crypto sentiment analyst.

These two tools are called via ToolNode for crypto sentiment (if needed in future).
F&G and CoinGecko data are pre-fetched (no @tool) and injected into the prompt.
"""

from langchain_core.tools import tool
from typing import Annotated


@tool
def get_crypto_smart_money(
    ticker: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
) -> str:
    """Fetch OKX copy-trading lead trader positioning as a smart money signal.

    Aggregates the top 5 lead traders on OKX for this asset:
    - Current position direction (LONG/SHORT)
    - Number of copy traders following each lead
    - 7-day PnL performance
    - Win rate

    Lead traders on OKX are professional or semi-professional traders with
    verified track records. Their positioning provides a 'smart money' signal
    separate from retail crowd behavior.
    """
    from tradingagents.dataflows.crypto_symbols import get_okx_ccy
    from tradingagents.dataflows.okx_data import get_okx_smart_money
    ccy = get_okx_ccy(ticker)
    return get_okx_smart_money(ccy)


@tool
def get_crypto_margin_leverage(
    ticker: Annotated[str, "CCXT symbol or base currency, e.g. 'BTC/USDT', 'ETH/USDT:USDT', 'BTC'"],
    period: Annotated[str, "Granularity: 5m, 1H, 4H, 1D (default 1D)"] = "1D",
) -> str:
    """Fetch OKX margin loan ratio — retail leverage usage indicator.

    The margin loan ratio measures long margin loans vs. short margin loans:
    - Ratio rising above 1: retail increasingly borrowing to go long (leverage buildup)
    - Ratio falling below 1: retail borrowing to short (crowded short)
    - Extreme high ratio with rising price: crowded long, reversal risk
    - Ratio resetting lower after a high reading: deleveraging in progress

    This is a direct measure of retail leverage usage, complementing the
    long/short account ratio which measures positioning but not leverage.
    """
    from tradingagents.dataflows.crypto_symbols import get_okx_ccy
    from tradingagents.dataflows.okx_data import get_okx_margin_loan_ratio
    ccy = get_okx_ccy(ticker)
    return get_okx_margin_loan_ratio(ccy, period=period)
