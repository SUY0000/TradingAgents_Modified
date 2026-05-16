"""Alternative.me Fear & Greed Index vendor."""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.alternative.me"
_CACHE: dict = {}
_CACHE_TTL = 43200  # 12 hours


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _CACHE_TTL


def get_fear_greed_block(curr_date: str, look_back_days: int = 30) -> str:
    """Return Fear & Greed Index history as a text block.

    Args:
        curr_date: Analysis date (used for cache key only, API always returns latest)
        look_back_days: Number of days to return (up to 90)

    Returns:
        Formatted text block with daily F&G index values.
    """
    cache_key = f"fg|{curr_date}|{look_back_days}"
    if cache_key in _CACHE and _is_fresh(_CACHE[cache_key]["ts"]):
        return _CACHE[cache_key]["data"]

    try:
        end_date = datetime.strptime(curr_date, "%Y-%m-%d").date()
    except ValueError:
        result = f"[Fear&Greed] Invalid analysis date: {curr_date}."
        _CACHE[cache_key] = {"ts": time.time(), "data": result}
        return result

    request_limit = max(look_back_days + 30, 90)
    try:
        resp = requests.get(
            f"{_API_BASE}/fng/",
            params={"limit": request_limit, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Fear & Greed API request failed: %s", exc)
        result = f"[Fear&Greed] Data unavailable: {exc}"
        _CACHE[cache_key] = {"ts": time.time(), "data": result}
        return result

    start_date = end_date - timedelta(days=look_back_days - 1)
    entries = []
    for entry in data.get("data", []):
        try:
            entry_date = datetime.fromtimestamp(
                int(entry.get("timestamp", "")), tz=timezone.utc
            ).date()
        except Exception:
            continue
        if start_date <= entry_date <= end_date:
            entries.append((entry_date, entry))

    entries.sort(key=lambda item: item[0], reverse=True)
    if not entries:
        result = f"[Fear&Greed] No data available for {start_date} to {end_date}."
        _CACHE[cache_key] = {"ts": time.time(), "data": result}
        return result

    latest = entries[0][1]
    latest_val = latest.get("value", "N/A")
    latest_label = latest.get("value_classification", "N/A")

    recent = entries[:7]
    avg_7d = sum(int(e.get("value", 0)) for _, e in recent) / max(len(recent), 1)
    avg_period = sum(int(e.get("value", 0)) for _, e in entries) / max(len(entries), 1)

    hist_lines = []
    for entry_date, entry in entries[:14]:
        val = entry.get("value", "?")
        label = entry.get("value_classification", "")
        hist_lines.append(f"  {entry_date:%Y-%m-%d}: {val} ({label})")

    lines = [
        f"Fear & Greed Index (Crypto, {start_date} to {end_date}):",
        f"  Latest as of {end_date}: {latest_val} — {latest_label}",
        f"  Avg 7d: {avg_7d:.0f}  Avg period: {avg_period:.0f}",
        "  Recent history:",
    ] + hist_lines

    result = "\n".join(lines)
    _CACHE[cache_key] = {"ts": time.time(), "data": result}
    return result
