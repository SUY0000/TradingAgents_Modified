"""CryptoPanic v2 news vendor — crypto news with community voting labels."""

import os
import logging
import time

import requests

logger = logging.getLogger(__name__)

_CACHE: dict = {}
_CACHE_TTL = 900  # 15 minutes


def _cache_key(*parts) -> str:
    return "|".join(str(p) for p in parts)


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _CACHE_TTL


def get_cryptopanic_news(currency: str, curr_date: str, look_back_days: int = 7, limit: int = 30) -> str:
    """Fetch recent crypto news from CryptoPanic with community vote labels.

    Args:
        currency: Uppercase currency code, e.g. "BTC"
        curr_date: Analysis date in yyyy-mm-dd format
        look_back_days: Days to look back for news (max 7 for free tier)
        limit: Max number of posts to return

    Returns:
        Formatted text block with headlines, votes, and kind labels.
    """
    key = _cache_key("cryptopanic", currency, curr_date, look_back_days)
    if key in _CACHE and _is_fresh(_CACHE[key]["ts"]):
        return _CACHE[key]["data"]

    api_key = os.environ.get("CRYPTOPANIC_API_KEY", "")
    if not api_key:
        result = (
            f"[CryptoPanic] No API key configured (CRYPTOPANIC_API_KEY). "
            f"CryptoPanic v2 requires auth_token in all requests. "
            f"Register at https://cryptopanic.com/developers/api to get a key."
        )
        _CACHE[key] = {"ts": time.time(), "data": result}
        return result

    api_plan = os.environ.get("CRYPTOPANIC_API_PLAN", "developer")
    api_base = f"https://cryptopanic.com/api/{api_plan}/v2"

    params = {
        "auth_token": api_key,
        "currencies": currency.upper(),
        "public": "true",
        "kind": "news",
        "regions": "en",
    }

    try:
        resp = requests.get(f"{api_base}/posts/", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("CryptoPanic request failed: %s", exc)
        result = f"[CryptoPanic] Data unavailable: {exc}"
        _CACHE[key] = {"ts": time.time(), "data": result}
        return result

    results = data.get("results", [])[:limit]
    if not results:
        result = "[CryptoPanic] No recent news found."
        _CACHE[key] = {"ts": time.time(), "data": result}
        return result

    lines = [f"CryptoPanic News — {currency} (last {look_back_days}d, up to {limit} items):"]
    for item in results:
        title = item.get("title", "")
        kind = item.get("kind", "news")
        published = item.get("published_at", "")[:10]
        votes = item.get("votes", {})
        positive = votes.get("positive", 0)
        negative = votes.get("negative", 0)
        important = votes.get("important", 0)
        lines.append(
            f"[{published}] [{kind.upper()}] {title} "
            f"(+{positive}/-{negative}/!{important})"
        )

    result = "\n".join(lines)
    _CACHE[key] = {"ts": time.time(), "data": result}
    return result
