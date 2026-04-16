"""OKX data vendor implementation for advanced cryptocurrency market data.

Provides funding rates, open interest, long/short ratios, taker volume and other
advanced metrics from OKX exchange via direct REST API calls.

Config fields (read from tradingagents.dataflows.config):
    ccxt_exchange: Exchange id string (default "okx")
    ccxt_symbol:   Trading pair in CCXT format, e.g. "BTC/USDT"
                   If empty, falls back to the *symbol* argument.

API rate limits (enforced via @okx_request_limiter decorator):
    Public endpoints  (/api/v5/public/*):  10 req/2s → delay_ms=200
    Rubik stat endpoints (/api/v5/rubik/*): 5 req/2s → delay_ms=400
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Annotated, Optional
import pandas as pd

from .config import get_config
from .okx_common import (
    okx_request_limiter,
    OKXRateLimitError,
)

logger = logging.getLogger(__name__)

OKX_BASE_URL = "https://www.okx.com"


# ---------------------------------------------------------------------------
# Symbol conversion helpers
# ---------------------------------------------------------------------------

def _resolve_okx_symbol(symbol: str) -> str:
    """Return the OKX trading pair to use.

    If ccxt_symbol is set in config it takes precedence over the symbol argument.
    """
    config = get_config()
    return config.get("ccxt_symbol") or symbol


def _to_inst_id(symbol: str) -> str:
    """Convert symbol to OKX instId format (perpetual swap).

    Examples:
        "BTC/USDT"      -> "BTC-USDT-SWAP"
        "BTC/USDT:USDT" -> "BTC-USDT-SWAP"
        "BTC-USDT-SWAP" -> "BTC-USDT-SWAP"
        "BTC"           -> "BTC-USDT-SWAP"
    """
    sym = symbol.split(":")[0]  # Strip margin info
    if "-SWAP" in sym or "-FUTURES" in sym:
        return sym
    base_quote = sym.replace("/", "-")
    if "-" not in base_quote:
        base_quote = f"{base_quote}-USDT"
    return f"{base_quote}-SWAP"


def _to_ccy(symbol: str) -> str:
    """Extract base currency from symbol.

    Examples:
        "BTC/USDT" -> "BTC"
        "BTC-USDT-SWAP" -> "BTC"
        "BTC" -> "BTC"
    """
    sym = symbol.split(":")[0]
    sym = sym.replace("-SWAP", "").replace("-FUTURES", "")
    parts = sym.replace("/", "-").split("-")
    return parts[0].upper()


def _to_inst_family(symbol: str) -> str:
    """Convert symbol to OKX instFamily format (base-quote, no suffix).

    Examples:
        "BTC/USDT" -> "BTC-USDT"
        "BTC-USDT-SWAP" -> "BTC-USDT"
    """
    sym = symbol.split(":")[0]
    sym = sym.replace("-SWAP", "").replace("-FUTURES", "")
    return sym.replace("/", "-")


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def _date_to_ms(date_str: str) -> int:
    """Convert YYYY-MM-DD to UTC millisecond timestamp (start of day)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ms_to_dt(ms: int) -> str:
    """Convert ms timestamp to UTC datetime string (YYYY-MM-DD HH:MM:SS)."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ---------------------------------------------------------------------------
# Cache utilities
# ---------------------------------------------------------------------------

def _get_cache_dir() -> str:
    config = get_config()
    cache_dir = os.path.join(config.get("data_cache_dir", ""), "okx")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _cache_path(metric: str, symbol: str, start: str, end: str) -> str:
    safe_sym = symbol.replace("/", "_").replace(":", "_")
    return os.path.join(_get_cache_dir(), f"{safe_sym}-{metric}-{start}-{end}.csv")


def _load_cache(path: str, ttl_hours: float = 1.0) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl_hours * 3600:
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _save_cache(df: pd.DataFrame, path: str) -> None:
    try:
        df.to_csv(path, index=False)
    except Exception as e:
        logger.warning(f"Failed to save OKX cache to {path}: {e}")


# ---------------------------------------------------------------------------
# REST API request helpers
# ---------------------------------------------------------------------------

def _okx_request(path: str, params: dict, max_retries: int = 3) -> list:
    """Single GET request to OKX REST API with retry on network errors.

    Args:
        path: API path (e.g., "/api/v5/public/funding-rate-history")
        params: Query parameters dict
        max_retries: Max attempts on connection/timeout errors

    Returns:
        List of data items from the "data" field of the response

    Raises:
        ValueError: If OKX returns a non-zero error code
        requests.HTTPError: On HTTP 4xx/5xx after all retries
    """
    url = f"{OKX_BASE_URL}{path}"

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            body = resp.json()

            if body.get("code") != "0":
                raise ValueError(
                    f"OKX API error {body.get('code')}: {body.get('msg')}"
                )
            return body.get("data", [])

        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(
                    f"OKX request to {path} failed ({e.__class__.__name__}), "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries - 1})"
                )
                time.sleep(wait)
            else:
                raise


def _okx_fetch_all(
    path: str,
    params: dict,
    ts_field: Optional[str] = None,
    begin_ms: int = 0,
    inter_page_delay: float = 0.4,
    max_pages: int = 50,
) -> list:
    """Fetch all pages of OKX data for a time range using cursor pagination.

    OKX returns data in descending timestamp order (newest first). After each
    page, the oldest timestamp is used as the ``after`` cursor to fetch older
    records. Stops when fewer than ``limit`` records are returned or when the
    oldest record's timestamp reaches ``begin_ms``.

    Args:
        path: API endpoint path
        params: Base query parameters (should include begin/end if applicable)
        ts_field: Dict key for timestamp in response items (None for array responses)
        begin_ms: Stop when oldest record <= this timestamp
        inter_page_delay: Seconds to sleep between pages (respects rate limits)
        max_pages: Hard cap on pages to fetch

    Returns:
        Combined list of all data items across pages
    """
    all_data: list = []
    current_params = dict(params)
    current_params.setdefault("limit", "100")

    for _ in range(max_pages):
        data = _okx_request(path, current_params)
        if not data:
            break

        all_data.extend(data)

        # If we got fewer than limit, there are no more pages
        if len(data) < int(current_params["limit"]):
            break

        # Sleep between pages to stay within rate limits
        time.sleep(inter_page_delay)

        # Extract oldest timestamp for cursor-based pagination
        last_item = data[-1]
        last_ts = None
        if isinstance(last_item, list):
            last_ts = int(last_item[0])
        elif ts_field and isinstance(last_item, dict) and ts_field in last_item:
            last_ts = int(last_item[ts_field])
        elif isinstance(last_item, dict):
            for f in ("ts", "fundingTime", "timestamp"):
                if f in last_item:
                    last_ts = int(last_item[f])
                    break

        if last_ts is None:
            break  # Cannot determine cursor, stop

        if last_ts <= begin_ms:
            break

        current_params["after"] = str(last_ts)

    return all_data


# ---------------------------------------------------------------------------
# Tier 1 — Core metrics
# ---------------------------------------------------------------------------

@okx_request_limiter(delay_ms=200)
def get_okx_funding_rate(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Fetch historical funding rates for a perpetual swap from OKX.

    Endpoint: GET /api/v5/public/funding-rate-history (10 req/2s)

    Returns CSV with columns:
        timestamp, inst_id, funding_rate, realized_rate, method

    Funding rate is settled every 8 hours for USDT-margined swaps.
    Positive rate -> longs pay shorts (bearish pressure relief).
    Negative rate -> shorts pay longs (bullish pressure relief).

    Args:
        symbol: CCXT-format pair (e.g. "BTC/USDT") or base ccy ("BTC")
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    inst_id = _to_inst_id(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000  # inclusive end day

    cache_file = _cache_path("funding_rate", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/public/funding-rate-history",
            {"instId": inst_id, "begin": str(begin_ms), "end": str(end_ms)},
            ts_field="fundingTime",
            begin_ms=begin_ms,
            inter_page_delay=0.2,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX funding rate for {symbol}: {e}")
        return f"Error fetching OKX funding rate data: {e}"

    if not data:
        return (
            f"No funding rate data available for {symbol} "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        ts_ms = int(item.get("fundingTime", 0))
        rows.append(
            {
                "timestamp": _ms_to_dt(ts_ms),
                "inst_id": item.get("instId", inst_id),
                "funding_rate": float(item.get("fundingRate", 0)),
                "realized_rate": float(item.get("realizedRate", 0)),
                "method": item.get("method", ""),
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


@okx_request_limiter(delay_ms=400)
def get_okx_open_interest_history(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "4H",
    **kwargs,
) -> str:
    """Fetch open interest history for a cryptocurrency from OKX.

    Endpoint: GET /api/v5/rubik/stat/contracts/open-interest-history (5 req/2s)

    Returns CSV with columns:
        timestamp, open_interest_contracts, open_interest_ccy, open_interest_usd

    Rising OI with rising price confirms bullish trend.
    Rising OI with falling price confirms bearish trend.

    Args:
        symbol: CCXT-format pair or base currency
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 5m, 1H, 4H, 1D, 1W

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    inst_id = _to_inst_id(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"oi_history_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/rubik/stat/contracts/open-interest-history",
            {"instId": inst_id, "period": period, "begin": str(begin_ms), "end": str(end_ms)},
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX OI history for {symbol}: {e}")
        return f"Error fetching OKX open interest history: {e}"

    if not data:
        return (
            f"No open interest history data for {symbol} ({inst_id}) "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        # Response format: [ts, oi, oiCcy, oiUsd]
        if isinstance(item, list):
            ts_ms = int(item[0])
            oi = float(item[1])
            oi_ccy = float(item[2])
            oi_usd = float(item[3]) if len(item) > 3 else None
        else:
            ts_ms = int(item.get("ts", 0))
            oi = float(item.get("oi", 0))
            oi_ccy = float(item.get("oiCcy", 0))
            oi_usd = float(item["oiUsd"]) if item.get("oiUsd") else None
        rows.append(
            {
                "timestamp": _ms_to_dt(ts_ms),
                "open_interest_contracts": oi,
                "open_interest_ccy": oi_ccy,
                "open_interest_usd": oi_usd,
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


@okx_request_limiter(delay_ms=400)
def get_okx_long_short_ratio(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "4H",
    **kwargs,
) -> str:
    """Fetch long/short account ratio (all traders) from OKX.

    Endpoint: GET /api/v5/rubik/stat/contracts/long-short-account-ratio-contract (5 req/2s)

    Returns CSV with columns:
        timestamp, long_short_ratio

    ratio > 1 -> more long accounts than short (retail bullish bias).
    ratio < 1 -> more short accounts (retail bearish bias).
    Extreme readings often signal contrarian reversal points.

    Args:
        symbol: CCXT-format pair or base currency
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 5m, 1H, 4H, 1D, 1W

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    inst_id = _to_inst_id(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"ls_ratio_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/rubik/stat/contracts/long-short-account-ratio-contract",
            {"instId": inst_id, "period": period, "begin": str(begin_ms), "end": str(end_ms)},
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX L/S ratio for {symbol}: {e}")
        return f"Error fetching OKX long/short ratio: {e}"

    if not data:
        return (
            f"No long/short ratio data for {symbol} ({inst_id}) "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        if isinstance(item, list):
            ts_ms, ls = int(item[0]), float(item[1])
        else:
            ts_ms = int(item.get("ts", 0))
            ls = float(item.get("lsRatio", 1.0))
        rows.append({"timestamp": _ms_to_dt(ts_ms), "long_short_ratio": ls})

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


@okx_request_limiter(delay_ms=400)
def get_okx_taker_volume(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "4H",
    **kwargs,
) -> str:
    """Fetch contract taker buy/sell volume from OKX.

    Endpoint: GET /api/v5/rubik/stat/taker-volume-contract (5 req/2s)

    Returns CSV with columns:
        timestamp, taker_sell_vol, taker_buy_vol, buy_sell_ratio

    buy_sell_ratio > 1 -> aggressive buying pressure (bullish).
    buy_sell_ratio < 1 -> aggressive selling pressure (bearish).

    Args:
        symbol: CCXT-format pair or base currency
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 5m, 1H, 4H, 1D, 1W

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    inst_id = _to_inst_id(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"taker_vol_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/rubik/stat/taker-volume-contract",
            {
                "instId": inst_id,
                "period": period,
                "begin": str(begin_ms),
                "end": str(end_ms),
            },
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX taker volume for {symbol}: {e}")
        return f"Error fetching OKX taker volume: {e}"

    if not data:
        return (
            f"No taker volume data for {symbol} ({inst_id}) "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        # OKX response format: [ts, sellVol, buyVol]
        if isinstance(item, list):
            ts_ms = int(item[0])
            sell_vol = float(item[1])
            buy_vol = float(item[2])
        else:
            ts_ms = int(item.get("ts", 0))
            sell_vol = float(item.get("sellVol", 0))
            buy_vol = float(item.get("buyVol", 0))

        buy_sell_ratio = (buy_vol / sell_vol) if sell_vol > 0 else None
        rows.append(
            {
                "timestamp": _ms_to_dt(ts_ms),
                "taker_sell_vol": sell_vol,
                "taker_buy_vol": buy_vol,
                "buy_sell_ratio": buy_sell_ratio,
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Tier 2 — Important metrics
# ---------------------------------------------------------------------------

@okx_request_limiter(delay_ms=400)
def get_okx_elite_long_short_ratio(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "4H",
    **kwargs,
) -> str:
    """Fetch elite trader long/short ratios (account count + position size) from OKX.

    Calls two endpoints sequentially:
    - /api/v5/rubik/stat/contracts/long-short-account-ratio-contract-top-trader
    - /api/v5/rubik/stat/contracts/long-short-position-ratio-contract-top-trader

    Returns CSV with columns:
        timestamp, elite_account_ls_ratio, elite_position_ls_ratio

    Elite (top-trader) positioning often diverges from retail and leads price.
    Account ratio tracks number of traders; position ratio tracks notional size.

    Args:
        symbol: CCXT-format pair or base currency
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 5m, 1H, 4H, 1D, 1W

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    inst_id = _to_inst_id(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"elite_ls_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    base_params = {
        "instId": inst_id,
        "period": period,
        "begin": str(begin_ms),
        "end": str(end_ms),
    }

    try:
        account_data = _okx_fetch_all(
            "/api/v5/rubik/stat/contracts/long-short-account-ratio-contract-top-trader",
            base_params.copy(),
            begin_ms=begin_ms,
        )
        time.sleep(0.4)  # Respect rubik rate limit between two sequential calls
        position_data = _okx_fetch_all(
            "/api/v5/rubik/stat/contracts/long-short-position-ratio-contract-top-trader",
            base_params.copy(),
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX elite L/S ratio for {symbol}: {e}")
        return f"Error fetching OKX elite long/short ratio: {e}"

    def _parse_ls_map(raw: list) -> dict:
        result = {}
        for item in raw:
            if isinstance(item, list):
                result[int(item[0])] = float(item[1])
            else:
                result[int(item.get("ts", 0))] = float(item.get("lsRatio", 1.0))
        return result

    account_map = _parse_ls_map(account_data)
    position_map = _parse_ls_map(position_data)
    all_ts = sorted(set(account_map) | set(position_map))

    if not all_ts:
        return (
            f"No elite L/S ratio data for {symbol} ({inst_id}) "
            f"from {start_date} to {end_date}"
        )

    rows = [
        {
            "timestamp": _ms_to_dt(ts),
            "elite_account_ls_ratio": account_map.get(ts),
            "elite_position_ls_ratio": position_map.get(ts),
        }
        for ts in all_ts
    ]

    df = pd.DataFrame(rows)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


@okx_request_limiter(delay_ms=400)
def get_okx_aggregated_oi_volume(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "4H",
    **kwargs,
) -> str:
    """Fetch aggregated open interest and trading volume from OKX.

    Endpoint: GET /api/v5/rubik/stat/contracts/open-interest-volume (5 req/2s)

    Returns CSV with columns:
        timestamp, open_interest, volume

    Use OI + volume together for trend strength confirmation:
    OI up + Volume up -> trend continuation; OI down + Volume up -> potential reversal.

    Args:
        symbol: CCXT-format pair or base currency
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 5m, 1H, 4H, 1D, 1W

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    ccy = _to_ccy(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"agg_oi_vol_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/rubik/stat/contracts/open-interest-volume",
            {"ccy": ccy, "period": period, "begin": str(begin_ms), "end": str(end_ms)},
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX aggregated OI+volume for {symbol}: {e}")
        return f"Error fetching OKX aggregated OI+volume: {e}"

    if not data:
        return (
            f"No aggregated OI+volume data for {symbol} ({ccy}) "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        if isinstance(item, list):
            ts_ms, oi, vol = int(item[0]), float(item[1]), float(item[2])
        else:
            ts_ms = int(item.get("ts", 0))
            oi = float(item.get("oi", 0))
            vol = float(item.get("vol", 0))
        rows.append(
            {
                "timestamp": _ms_to_dt(ts_ms),
                "open_interest": oi,
                "volume": vol,
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Tier 3 — Advanced / optional metrics
# ---------------------------------------------------------------------------

@okx_request_limiter(delay_ms=400)
def get_okx_put_call_ratio(
    symbol: Annotated[str, "ticker symbol (ccxt_symbol in config overrides)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    period: str = "1D",
    **kwargs,
) -> str:
    """Fetch options put/call ratio from OKX.

    Endpoint: GET /api/v5/rubik/stat/option/open-interest-volume-ratio (5 req/2s)

    Returns CSV with columns:
        timestamp, oi_put_call_ratio, vol_put_call_ratio

    P/C ratio > 1 -> bearish sentiment (more puts than calls).
    P/C ratio < 1 -> bullish sentiment (more calls than puts).
    Extreme readings can signal sentiment exhaustion / contrarian opportunity.

    Args:
        symbol: CCXT-format pair or base currency (typically BTC or ETH)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD (inclusive)
        period: Granularity — 8H or 1D

    Returns:
        CSV string or error message string.
    """
    symbol = _resolve_okx_symbol(symbol)
    ccy = _to_ccy(symbol)
    begin_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date) + 86_400_000

    cache_file = _cache_path(f"pc_ratio_{period}", symbol, start_date, end_date)
    cached = _load_cache(cache_file)
    if cached is not None:
        return cached.to_csv(index=False)

    try:
        data = _okx_fetch_all(
            "/api/v5/rubik/stat/option/open-interest-volume-ratio",
            {"ccy": ccy, "period": period, "begin": str(begin_ms), "end": str(end_ms)},
            begin_ms=begin_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch OKX P/C ratio for {symbol}: {e}")
        return f"Error fetching OKX put/call ratio: {e}"

    if not data:
        return (
            f"No put/call ratio data for {symbol} ({ccy}) "
            f"from {start_date} to {end_date}"
        )

    rows = []
    for item in data:
        if isinstance(item, list):
            ts_ms = int(item[0])
            oi_ratio = float(item[1]) if len(item) > 1 else None
            vol_ratio = float(item[2]) if len(item) > 2 else None
        else:
            ts_ms = int(item.get("ts", 0))
            oi_ratio = float(item["oiRatio"]) if item.get("oiRatio") else None
            vol_ratio = float(item["volRatio"]) if item.get("volRatio") else None
        rows.append(
            {
                "timestamp": _ms_to_dt(ts_ms),
                "oi_put_call_ratio": oi_ratio,
                "vol_put_call_ratio": vol_ratio,
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    numeric_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[numeric_cols] = df[numeric_cols].round(4)
    _save_cache(df, cache_file)
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Backward-compatibility aliases (preserves any existing callers)
# ---------------------------------------------------------------------------

def get_okx_open_interest(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Alias for get_okx_open_interest_history (backward compatibility)."""
    return get_okx_open_interest_history(symbol, start_date, end_date, **kwargs)


def get_okx_mark_price(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    **kwargs,
) -> str:
    """Mark price OHLCV is covered by ccxt_data.py; redirects to aggregated OI+volume."""
    return get_okx_aggregated_oi_volume(symbol, start_date, end_date, **kwargs)
