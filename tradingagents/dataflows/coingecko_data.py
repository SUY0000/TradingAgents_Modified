"""CoinGecko Demo API vendor — shared HTTP for fundamentals and sentiment."""

import os
import logging
import time

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.coingecko.com/api/v3"
_CACHE: dict = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_key(*parts) -> str:
    return "|".join(str(p) for p in parts)


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _CACHE_TTL


def _fetch_coin(cg_id: str) -> dict:
    """Fetch /coins/{id} once and cache. Returns raw JSON dict."""
    key = _cache_key("cg_coin", cg_id)
    if key in _CACHE and _is_fresh(_CACHE[key]["ts"]):
        return _CACHE[key]["data"]

    api_key = os.environ.get("COINGECKO_DEMO_API_KEY", "")
    headers = {}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "true",
        "sparkline": "false",
    }

    try:
        resp = requests.get(f"{_API_BASE}/coins/{cg_id}", params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("CoinGecko request failed for %s: %s", cg_id, exc)
        data = {}

    _CACHE[key] = {"ts": time.time(), "data": data}
    return data


def get_coingecko_fundamentals_block(cg_id: str) -> str:
    """Return supply, developer, and market data block for fundamentals analyst."""
    data = _fetch_coin(cg_id)
    if not data:
        return f"[CoinGecko] Data unavailable for {cg_id}."

    name = data.get("name", cg_id)
    market = data.get("market_data", {})
    dev = data.get("developer_data", {})
    community = data.get("community_data", {})

    circ = market.get("circulating_supply", "N/A")
    total = market.get("total_supply", "N/A")
    max_s = market.get("max_supply", "N/A")
    mcap = market.get("market_cap", {}).get("usd", "N/A")
    fdv = market.get("fully_diluted_valuation", {}).get("usd", "N/A")
    vol24h = market.get("total_volume", {}).get("usd", "N/A")
    price_chg_7d = market.get("price_change_percentage_7d", "N/A")
    price_chg_30d = market.get("price_change_percentage_30d", "N/A")

    stars = dev.get("stars", "N/A")
    forks = dev.get("forks", "N/A")
    commits_4w = dev.get("commit_count_4_weeks", "N/A")
    contributors = dev.get("pull_request_contributors", "N/A")
    issues_closed = dev.get("closed_issues", "N/A")
    issues_open = dev.get("open_issues", "N/A")

    twitter_followers = community.get("twitter_followers", "N/A")
    reddit_subscribers = community.get("reddit_subscribers", "N/A")
    telegram_users = community.get("telegram_channel_user_count", "N/A")

    desc = (data.get("description", {}) or {}).get("en", "")[:300]

    lines = [
        f"CoinGecko Fundamentals — {name} ({cg_id}):",
        f"  Market Cap: ${mcap:,}" if isinstance(mcap, (int, float)) else f"  Market Cap: {mcap}",
        f"  FDV: ${fdv:,}" if isinstance(fdv, (int, float)) else f"  FDV: {fdv}",
        f"  24h Volume: ${vol24h:,}" if isinstance(vol24h, (int, float)) else f"  24h Volume: {vol24h}",
        f"  Price Chg 7d: {price_chg_7d}%  30d: {price_chg_30d}%",
        f"  Circulating Supply: {circ}  Total: {total}  Max: {max_s}",
        f"  GitHub: {stars} stars / {forks} forks / {commits_4w} commits(4w) / {contributors} contributors",
        f"  Issues: {issues_open} open / {issues_closed} closed",
        f"  Community: Twitter {twitter_followers} / Reddit {reddit_subscribers} / Telegram {telegram_users}",
    ]
    if desc:
        lines.append(f"  Description: {desc}...")

    return "\n".join(lines)


def get_coingecko_sentiment_block(cg_id: str) -> str:
    """Return platform vote and community engagement block for sentiment analyst."""
    data = _fetch_coin(cg_id)
    if not data:
        return f"[CoinGecko] Sentiment data unavailable for {cg_id}."

    name = data.get("name", cg_id)
    community = data.get("community_data", {})
    sentiment_up = data.get("sentiment_votes_up_percentage", "N/A")
    sentiment_down = data.get("sentiment_votes_down_percentage", "N/A")
    watchlist = data.get("watchlist_portfolio_users", "N/A")

    twitter = community.get("twitter_followers", "N/A")
    reddit_subs = community.get("reddit_subscribers", "N/A")
    reddit_active = community.get("reddit_accounts_active_48h", "N/A")
    telegram = community.get("telegram_channel_user_count", "N/A")

    lines = [
        f"CoinGecko Sentiment — {name} ({cg_id}):",
        f"  Platform Votes: {sentiment_up}% bullish / {sentiment_down}% bearish",
        f"  Watchlist Users: {watchlist}",
        f"  Twitter Followers: {twitter}",
        f"  Reddit: {reddit_subs} subscribers / {reddit_active} active (48h)",
        f"  Telegram: {telegram} users",
    ]
    return "\n".join(lines)
