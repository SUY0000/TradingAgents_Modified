"""OKX data vendor implementation for advanced cryptocurrency market data.

Provides funding rates, open interest, mark prices, and other advanced metrics
from OKX exchange via CCXT library.

Config fields (read from tradingagents.dataflows.config):
    ccxt_exchange: Exchange id string (default "okx")
    ccxt_symbol:   Trading pair in CCXT format, e.g. "BTC/USDT"
                   If empty, falls back to the *symbol* argument.
"""

import os
import time
from datetime import datetime
from typing import Annotated
import pandas as pd

from .config import get_config
from .okx_common import (
    okx_retry,
    okx_request_limiter,
    _get_okx_exchange,
    OKXRateLimitError,
    parse_okx_timestamp,
    format_okx_date,
)

# ---------------------------------------------------------------------------
# Cache and utility functions
# ---------------------------------------------------------------------------

def _get_cache_dir() -> str:
    """Get OKX cache directory, creating if needed."""
    config = get_config()
    cache_dir = os.path.join(config.get("data_cache_dir", ""), "okx")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _get_cache_key(metric: str, symbol: str, timeframe: str = None) -> str:
    """Generate cache key for OKX data."""
    safe_symbol = symbol.replace("/", "_")
    if timeframe:
        return f"{safe_symbol}-{metric}-{timeframe}.csv"
    return f"{safe_symbol}-{metric}.csv"


def _load_cached_data(cache_key: str, ttl_minutes: int = 5) -> pd.DataFrame:
    """Load cached data if it exists and is not expired.

    Args:
        cache_key: Cache file name
        ttl_minutes: Time-to-live in minutes (default 5 for current data)

    Returns:
        DataFrame if cache is valid, else None
    """
    cache_dir = _get_cache_dir()
    cache_file = os.path.join(cache_dir, cache_key)

    if os.path.exists(cache_file):
        file_mtime = os.path.getmtime(cache_file)
        if time.time() - file_mtime < ttl_minutes * 60:
            try:
                return pd.read_csv(cache_file)
            except Exception:
                return None
    return None


def _save_to_cache(data: pd.DataFrame, cache_key: str):
    """Save data to cache file."""
    cache_dir = _get_cache_dir()
    cache_file = os.path.join(cache_dir, cache_key)
    data.to_csv(cache_file, index=False)


def _resolve_okx_symbol(symbol: str) -> str:
    """Return the OKX trading pair to use.

    If ccxt_symbol is set in config it takes precedence over the
    symbol argument.
    """
    config = get_config()
    return config.get("ccxt_symbol") or symbol


# ---------------------------------------------------------------------------
# Public vendor API
# ---------------------------------------------------------------------------

@okx_request_limiter(delay_ms=200)
def get_okx_funding_rate(
    symbol: Annotated[str, "ticker symbol (short name, ccxt_symbol overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Fetch current and historical funding rates from OKX.

    Returns a CSV string with funding rate data including:
    - timestamp
    - funding rate (decimal)
    - next funding time
    - realized rate (if available)

    Args:
        symbol: Trading pair symbol (e.g., "BTC")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        **kwargs: Additional parameters passed through

    Returns:
        CSV string with funding rate data
    """
    # Implementation will use CCXT's fetchFundingRate and fetchFundingRateHistory
    # This is a placeholder implementation
    return "OKX funding rate data (placeholder)"


@okx_request_limiter(delay_ms=200)
def get_okx_open_interest(
    symbol: Annotated[str, "ticker symbol (short name, ccxt_symbol overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Fetch open interest data from OKX.

    Returns a CSV string with open interest data including:
    - timestamp
    - open interest in contracts (oi)
    - open interest in coin (oiCcy)
    - open interest in USD (oiUsd)

    Args:
        symbol: Trading pair symbol (e.g., "BTC")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        **kwargs: Additional parameters passed through

    Returns:
        CSV string with open interest data
    """
    # Implementation will use CCXT's fetchOpenInterest
    # This is a placeholder implementation
    return "OKX open interest data (placeholder)"


@okx_request_limiter(delay_ms=200)
def get_okx_mark_price(
    symbol: Annotated[str, "ticker symbol (short name, ccxt_symbol overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Fetch mark price data from OKX.

    Returns a CSV string with mark price candlestick data including:
    - timestamp
    - open, high, low, close prices
    - confirmation status

    Args:
        symbol: Trading pair symbol (e.g., "BTC")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        **kwargs: Additional parameters passed through

    Returns:
        CSV string with mark price data
    """
    # Implementation will use OKX-specific mark price endpoints
    # This is a placeholder implementation
    return "OKX mark price data (placeholder)"


# ---------------------------------------------------------------------------
# Additional utility functions (not exposed as tools directly)
# ---------------------------------------------------------------------------

def get_okx_funding_rate_current(
    symbol: str,
    **kwargs,
) -> dict:
    """Get current funding rate for a symbol.

    Returns current funding rate data as a dictionary.
    """
    # Placeholder implementation
    return {}


def get_okx_open_interest_current(
    symbol: str,
    inst_type: str = "SWAP",
    **kwargs,
) -> dict:
    """Get current open interest for a symbol.

    Args:
        symbol: Trading pair
        inst_type: Instrument type (SWAP, FUTURES, OPTION)

    Returns:
        Dictionary with open interest data
    """
    # Placeholder implementation
    return {}