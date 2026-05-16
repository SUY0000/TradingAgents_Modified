"""Alternative.me Fear & Greed Index vendor."""

import logging
import time
from datetime import datetime, timezone

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
        resp = requests.get(
            f"{_API_BASE}/fng/",
            params={"limit": look_back_days, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Fear & Greed API request failed: %s", exc)
        result = f"[Fear&Greed] Data unavailable: {exc}"
        _CACHE[cache_key] = {"ts": time.time(), "data": result}
        return result

    entries = data.get("data", [])
    if not entries:
        result = "[Fear&Greed] No data returned."
        _CACHE[cache_key] = {"ts": time.time(), "data": result}
        return result

    latest = entries[0]
    latest_val = latest.get("value", "N/A")
    latest_label = latest.get("value_classification", "N/A")

    # Recent 7-day summary
    recent = entries[:7]
    avg_7d = sum(int(e.get("value", 0)) for e in recent) / max(len(recent), 1)
    avg_30d = sum(int(e.get("value", 0)) for e in entries) / max(len(entries), 1)

    # Build compact history (last 14 days)
    hist_lines = []
    for entry in entries[:14]:
        ts = entry.get("timestamp", "")
        try:
            date_str = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            date_str = ts
        val = entry.get("value", "?")
        label = entry.get("value_classification", "")
        hist_lines.append(f"  {date_str}: {val} ({label})")

    lines = [
        f"Fear & Greed Index (Crypto, {look_back_days}d history):",
        f"  Latest: {latest_val} — {latest_label}",
        f"  Avg 7d: {avg_7d:.0f}  Avg 30d: {avg_30d:.0f}",
        "  14-day history:",
    ] + hist_lines

    result = "\n".join(lines)
    _CACHE[cache_key] = {"ts": time.time(), "data": result}
    return result
