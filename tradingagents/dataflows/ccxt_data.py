"""CCXT data vendor implementation for cryptocurrency markets.

Provides OHLCV data and technical indicators from crypto exchanges
via the CCXT library. OKX is the default exchange.

Config fields (read from tradingagents.dataflows.config):
    ccxt_exchange: Exchange id string (default "okx")
    ccxt_symbol:   Trading pair in CCXT format, e.g. "BTC/USDT"
                   If empty, falls back to the *symbol* argument.
"""

import os
import warnings
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Annotated

import pandas as pd
from stockstats import wrap

from .config import get_config
from .stockstats_utils import _clean_dataframe

# ---------------------------------------------------------------------------
# Indicator descriptions (same set as yfinance for consistency)
# ---------------------------------------------------------------------------
best_ind_params = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
    ),
}


def _resolve_ccxt_symbol(symbol: str) -> str:
    """Return the CCXT trading pair to use.

    If ``ccxt_symbol`` is set in config it takes precedence over the
    *symbol* argument so the LLM can keep calling tools with the
    short ticker while the CCXT vendor transparently uses the full pair.
    """
    config = get_config()
    return config.get("ccxt_symbol") or symbol


def _get_env_proxy(name: str) -> str | None:
    return os.environ.get(name) or os.environ.get(name.lower())


def _get_exchange():
    """Create a CCXT exchange instance from config."""
    import ccxt

    config = get_config()
    exchange_id = config.get("ccxt_exchange", "okx")
    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(
            f"CCXT exchange '{exchange_id}' not found. "
            f"Install a version of ccxt that supports it."
        )

    proxies = {}
    all_proxy = _get_env_proxy("ALL_PROXY")
    http_proxy = _get_env_proxy("HTTP_PROXY") or all_proxy
    https_proxy = _get_env_proxy("HTTPS_PROXY") or all_proxy
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    exchange_options = {"proxies": proxies} if proxies else {}
    return exchange_class(exchange_options)


def _validate_timeframe(exchange, timeframe: str) -> str:
    """Validate if timeframe is supported, fallback to '1d' if not."""
    if not exchange.has.get('fetchOHLCV', False):
        raise ValueError(f"Exchange {exchange.id} does not support OHLCV data")

    # 1. Exact match with keys
    if timeframe in exchange.timeframes:
        return timeframe

    # 2. Exact match with values
    for tf_key, tf_value in exchange.timeframes.items():
        if timeframe == tf_value:
            return tf_key

    # 3. Case-insensitive match (but preserve M/m distinction)
    # For minutes vs months: 'm' is minutes, 'M' is months
    timeframe_lower = timeframe.lower()

    for tf_key, tf_value in exchange.timeframes.items():
        # Compare lowercase versions, but handle 'M' specially
        key_lower = tf_key.lower()
        value_lower = tf_value.lower()

        # Only match if both are same case-insensitive representation
        if timeframe_lower == key_lower or timeframe_lower == value_lower:
            # Additional check: if timeframe contains 'M' (uppercase) and key contains 'm' (lowercase),
            # don't match (different units)
            if 'M' in timeframe and 'm' in tf_key:
                continue  # Skip: M (month) vs m (minute) mismatch
            if 'm' in timeframe and 'M' in tf_key:
                continue  # Skip: m (minute) vs M (month) mismatch
            return tf_key

    # Fallback to '1d' with warning
    warnings.warn(f"Timeframe '{timeframe}' not supported by {exchange.id}. "
                  f"Supported: {list(exchange.timeframes.keys())}. "
                  f"Falling back to '1d'.", UserWarning)
    return '1d'


def _timeframe_to_ms(timeframe: str) -> int:
    """Convert CCXT timeframe string to milliseconds."""
    if not timeframe:
        raise ValueError("Empty timeframe string")

    unit = timeframe[-1]  # Keep original case
    value_str = timeframe[:-1]
    value = int(value_str) if value_str else 1

    # Handle uppercase M (months) separately from lowercase m (minutes)
    if unit == 'M':  # months (uppercase M, approx 30 days)
        return value * 30 * 24 * 60 * 60 * 1000

    unit_lower = unit.lower()

    if unit_lower == 'm':  # minutes
        return value * 60 * 1000
    elif unit_lower == 'h':  # hours
        return value * 60 * 60 * 1000
    elif unit_lower == 'd':  # days
        return value * 24 * 60 * 60 * 1000
    elif unit_lower == 'w':  # weeks
        return value * 7 * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"Unsupported timeframe unit: {timeframe}")


# ---------------------------------------------------------------------------
# OHLCV data loading with caching
# ---------------------------------------------------------------------------

def _load_ccxt_ohlcv(symbol: str, curr_date: str, timeframe: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data from CCXT exchange, with file-based caching.

    Downloads up to N years of candles up to *curr_date* and caches per symbol.
    Rows after *curr_date* are dropped to prevent look-ahead bias.

    Args:
        symbol: Ticker symbol
        curr_date: Current date in YYYY-mm-dd format
        timeframe: Timeframe string, e.g., '1d', '1h', '4h'. Default is '1d'.
    """
    config = get_config()
    ccxt_symbol = _resolve_ccxt_symbol(symbol)
    curr_date_dt = pd.to_datetime(curr_date)

    # Get exchange and validate timeframe
    exchange = _get_exchange()
    validated_timeframe = _validate_timeframe(exchange, timeframe)

    # Adjust lookback period based on timeframe
    # Classify by unit: minutes (m), hours (h), days/weeks/months (d/w/M)
    unit = validated_timeframe[-1]  # Last character

    if unit == 'm':  # minutes (lowercase m)
        lookback_years = 1  # High-frequency data: 1 year
    elif unit.lower() == 'h':  # hours (case-insensitive)
        lookback_years = 2  # Medium-frequency data: 2 years
    else:
        lookback_years = 5  # Low-frequency data: 5 years (default: days, weeks, months)

    # Determine date range (N years look-back from today)
    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=lookback_years)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today_date.strftime("%Y-%m-%d")

    # Safe filename: replace / with _, and handle timeframe
    safe_name = ccxt_symbol.replace("/", "_")
    safe_timeframe = validated_timeframe.replace("/", "_").replace("\\", "_")
    cache_dir = config.get("data_cache_dir", "")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(
        cache_dir,
        f"{safe_name}-{safe_timeframe}-CCXT-data-{start_str}-{end_str}.csv",
    )

    if os.path.exists(cache_file):
        data = pd.read_csv(cache_file, on_bad_lines="skip")
    else:
        since_ms = int(start_date.timestamp() * 1000)
        all_candles = []
        while True:
            candles = exchange.fetch_ohlcv(
                ccxt_symbol, validated_timeframe, since=since_ms, limit=1000
            )
            if not candles:
                break
            all_candles.extend(candles)
            # Move *since* to the timestamp of the last candle + timeframe duration
            timeframe_ms = _timeframe_to_ms(validated_timeframe)
            since_ms = candles[-1][0] + timeframe_ms
            if since_ms > int(today_date.timestamp() * 1000):
                break

        if not all_candles:
            raise RuntimeError(
                f"No OHLCV data returned for {ccxt_symbol} from CCXT "
                f"(timeframe: {validated_timeframe})"
            )

        data = pd.DataFrame(
            all_candles,
            columns=["Date", "Open", "High", "Low", "Close", "Volume"],
        )
        data["Date"] = pd.to_datetime(data["Date"], unit="ms")
        data["Adj Close"] = data["Close"]  # crypto has no corporate adjustments
        data.to_csv(cache_file, index=False)

    data = _clean_dataframe(data)

    # Filter to curr_date to prevent look-ahead bias
    data = data[data["Date"] <= curr_date_dt]
    return data


# ---------------------------------------------------------------------------
# Public vendor API
# ---------------------------------------------------------------------------

def get_ccxt_stock_data(
    symbol: Annotated[str, "ticker symbol (short name, ccxt_symbol overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    timeframe: Annotated[str, "Timeframe string, e.g., '1d', '1h', '4h'"] = "1d",
    **kwargs,
) -> str:
    """Fetch OHLCV price data from a CCXT exchange (default: OKX).

    Returns a CSV string with the same columns as the yfinance output
    (Date, Open, High, Low, Close, Adj Close, Volume).

    Args:
        timeframe: CCXT timeframe string (e.g., '1m', '1h', '1d', '1w').
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    ccxt_symbol = _resolve_ccxt_symbol(symbol)
    exchange_id = get_config().get("ccxt_exchange", "okx")

    # Use end_date as curr_date to load data up to that point
    data = _load_ccxt_ohlcv(symbol, end_date, timeframe)

    # Filter to the requested date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    data = data[(data["Date"] >= start_dt) & (data["Date"] <= end_dt)]

    # Safety cap: prevent excessive token consumption from overly large date ranges
    _MAX_ROWS_BY_TIMEFRAME = {
        "1h": 168,   # 7 days × 24h
        "4h": 84,    # 14 days × 6
        "1d": 60,    # 60 days
        "1w": 26,    # 26 weeks
    }
    max_rows = _MAX_ROWS_BY_TIMEFRAME.get(timeframe, 500)
    if len(data) > max_rows:
        data = data.tail(max_rows)

    if data.empty:
        return f"No data found for '{ccxt_symbol}' between {start_date} and {end_date}"

    # Round numerical values for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    if "Volume" in data.columns:
        data["Volume"] = data["Volume"].round(0).astype("int64")

    csv_string = data.to_csv(index=False)

    header = f"# Crypto data for {ccxt_symbol} from {start_date} to {end_date}\n"
    header += f"# Exchange: {exchange_id} (via CCXT)\n"
    header += f"# Timeframe: {timeframe}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


def get_ccxt_indicators(
    symbol: Annotated[str, "ticker symbol (short name, ccxt_symbol overrides)"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "The current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 14,
    timeframe: Annotated[str, "Timeframe string, e.g., '1d', '1h', '4h'"] = "1d",
    **kwargs,
) -> str:
    """Calculate a technical indicator using CCXT-sourced OHLCV data.

    Uses stockstats for indicator calculation (same library as the yfinance
    vendor), ensuring indicator values are consistent across vendors.

    Args:
        timeframe: CCXT timeframe string (e.g., '1m', '1h', '1d', '1w').
    """
    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. "
            f"Please choose from: {list(best_ind_params.keys())}"
        )

    ccxt_symbol = _resolve_ccxt_symbol(symbol)
    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        indicator_data = _get_ccxt_indicator_bulk(symbol, indicator, curr_date, timeframe)

        current_dt = curr_date_dt
        date_values = []
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            if date_str in indicator_data:
                date_values.append((date_str, indicator_data[date_str]))
            # Skip non-trading days — reduces token waste on sparse timeframes (e.g. 1w)
            current_dt = current_dt - relativedelta(days=1)

        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"

    except Exception as e:
        print(f"Error getting CCXT indicator data: {e}")
        ind_string = ""
        current_dt = curr_date_dt
        while current_dt >= before:
            ind_string += f"{current_dt.strftime('%Y-%m-%d')}: Error - {e}\n"
            current_dt = current_dt - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date} "
        f"({ccxt_symbol}, timeframe: {timeframe}):\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def _get_ccxt_indicator_bulk(
    symbol: str,
    indicator: str,
    curr_date: str,
    timeframe: str = "1d",
) -> dict:
    """Bulk calculation of a single indicator across all available dates.

    Same pattern as ``y_finance._get_stock_stats_bulk``.
    """
    data = _load_ccxt_ohlcv(symbol, curr_date, timeframe)
    df = wrap(data)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    df[indicator]  # trigger stockstats calculation

    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)

    return result_dict
