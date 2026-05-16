"""Free crypto news via public RSS feeds."""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from re import escape, search, sub

import requests

logger = logging.getLogger(__name__)

_CACHE: dict = {}
_CACHE_TTL = 900
_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]
_KEYWORDS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "ether", "eth"],
    "SOL": ["solana", "sol"],
    "BNB": ["bnb", "binance coin"],
    "XRP": ["xrp", "ripple"],
    "DOGE": ["dogecoin", "doge"],
    "ADA": ["cardano", "ada"],
    "AVAX": ["avalanche", "avax"],
    "UNI": ["uniswap", "uni"],
    "LINK": ["chainlink", "link"],
    "LTC": ["litecoin", "ltc"],
    "MATIC": ["polygon", "matic"],
    "DOT": ["polkadot", "dot"],
    "TRX": ["tron", "trx"],
    "ATOM": ["cosmos", "atom"],
}
_MACRO_KEYWORDS = [
    "fed", "federal reserve", "fomc", "cpi", "inflation", "rates", "treasury",
    "dollar", "etf", "sec", "cftc", "regulation", "lawsuit", "stablecoin",
    "liquidity", "risk assets",
]


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _CACHE_TTL


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    if child is None or child.text is None:
        return ""
    return _clean(child.text)


def _clean(value: str) -> str:
    return sub(r"\s+", " ", sub(r"<[^>]+>", " ", unescape(value))).strip()


def _matches_keyword(haystack: str, keyword: str) -> bool:
    if keyword.isalpha() and len(keyword) <= 4:
        return search(rf"(?<![A-Za-z0-9]){escape(keyword)}(?![A-Za-z0-9])", haystack) is not None
    return keyword in haystack


def _article_matches(title: str, description: str, base: str) -> bool:
    haystack = f"{title} {description}".lower()
    asset_keywords = _KEYWORDS.get(base.upper(), [base.lower()])
    macro_match = any(_matches_keyword(haystack, keyword) for keyword in _MACRO_KEYWORDS)
    asset_match = any(_matches_keyword(haystack, keyword) for keyword in asset_keywords)
    return asset_match or (base.upper() in {"BTC", "ETH"} and macro_match)


def get_free_crypto_news(base_currency: str, curr_date: str, look_back_days: int = 7, limit: int = 30) -> str:
    """Fetch recent crypto news from public RSS feeds without API keys."""
    base = base_currency.upper()
    key = f"rss|{base}|{curr_date}|{look_back_days}|{limit}"
    if key in _CACHE and _is_fresh(_CACHE[key]["ts"]):
        return _CACHE[key]["data"]

    try:
        end_date = datetime.strptime(curr_date, "%Y-%m-%d").date()
    except ValueError:
        result = f"[Free crypto RSS] Invalid analysis date: {curr_date}."
        _CACHE[key] = {"ts": time.time(), "data": result}
        return result
    start_date = end_date - timedelta(days=look_back_days - 1)

    articles = []
    errors = []
    for source, url in _FEEDS:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "TradingAgents/crypto-news"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as exc:
            logger.warning("Free crypto RSS request failed for %s: %s", source, exc)
            errors.append(f"{source}: {exc}")
            continue

        for item in root.findall(".//item"):
            title = _text(item, "title")
            description = _text(item, "description")
            link = _text(item, "link")
            published = _parse_date(_text(item, "pubDate") or _text(item, "published"))
            if not title or published is None:
                continue
            if not (start_date <= published.date() <= end_date):
                continue
            if not _article_matches(title, description, base):
                continue
            articles.append((published, source, title, link))

    articles.sort(key=lambda row: row[0], reverse=True)
    deduped = []
    seen = set()
    for article in articles:
        key_title = article[2].lower()
        if key_title in seen:
            continue
        seen.add(key_title)
        deduped.append(article)
        if len(deduped) >= limit:
            break

    if not deduped:
        result = f"[Free crypto RSS] No matching news for {base} from {start_date} to {end_date}."
        if errors:
            result += " Feed errors: " + "; ".join(errors[:3])
        _CACHE[key] = {"ts": time.time(), "data": result}
        return result

    lines = [f"Free Crypto RSS News — {base} ({start_date} to {end_date}, up to {limit} items):"]
    for published, source, title, link in deduped:
        link_suffix = f" — {link}" if link else ""
        lines.append(f"[{published:%Y-%m-%d}] [{source}] {title}{link_suffix}")

    result = "\n".join(lines)
    _CACHE[key] = {"ts": time.time(), "data": result}
    return result
