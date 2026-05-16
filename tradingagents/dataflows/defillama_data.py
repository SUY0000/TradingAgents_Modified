"""DefiLlama vendor — DeFi protocol TVL, fees, and revenue."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.llama.fi"
_CACHE: dict = {}
_CACHE_TTL = 600  # 10 minutes


def _cache_key(*parts) -> str:
    return "|".join(str(p) for p in parts)


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _CACHE_TTL


def get_defillama_protocol(slug: str) -> str:
    """Return DeFi protocol TVL, fees, and revenue as a text block.

    Args:
        slug: DefiLlama protocol slug, e.g. "uniswap-v3"

    Returns:
        Formatted text block or graceful degradation message.
    """
    if not slug:
        return "[DefiLlama] Not a DeFi protocol — no TVL/fees data available."

    key = _cache_key("defillama", slug)
    if key in _CACHE and _is_fresh(_CACHE[key]["ts"]):
        return _CACHE[key]["data"]

    result = _fetch_protocol_metrics(slug)
    _CACHE[key] = {"ts": time.time(), "data": result}
    return result


def _get(url: str, timeout: int = 25) -> requests.Response:
    """GET with one retry on timeout."""
    for attempt in range(2):
        try:
            return requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            if attempt == 0:
                logger.debug("DefiLlama timeout on %s, retrying", url)
                continue
            raise


def _fetch_protocol_metrics(slug: str) -> str:
    # Fetch protocol TVL
    try:
        resp = _get(f"{_API_BASE}/protocol/{slug}")
        if resp.status_code == 404:
            return f"[DefiLlama] Protocol '{slug}' not found — may not be tracked."
        resp.raise_for_status()
        proto = resp.json()
    except Exception as exc:
        logger.warning("DefiLlama protocol request failed for %s: %s", slug, exc)
        return f"[DefiLlama] Data unavailable for {slug}: {exc}"

    name = proto.get("name", slug)
    tvl = proto.get("tvl", "N/A")
    category = proto.get("category", "N/A")
    chains = proto.get("chains", [])[:5]

    # Fetch fees/revenue
    fees_info = ""
    try:
        f_resp = _get(f"{_API_BASE}/summary/fees/{slug}")
        if f_resp.status_code == 200:
            fdata = f_resp.json()
            fees_24h = fdata.get("total24h", "N/A")
            fees_7d = fdata.get("total7d", "N/A")
            revenue_24h = fdata.get("revenue24h", "N/A")
            fees_info = (
                f"  Fees 24h: ${fees_24h}  7d: ${fees_7d}  Revenue 24h: ${revenue_24h}"
            )
    except Exception as exc:
        logger.debug("DefiLlama fees request failed for %s: %s", slug, exc)
        fees_info = "  Fees: unavailable"

    lines = [
        f"DefiLlama Protocol Metrics — {name} ({slug}):",
        f"  Category: {category}",
        f"  TVL: ${tvl:,.0f}" if isinstance(tvl, (int, float)) else f"  TVL: {tvl}",
        f"  Active Chains: {', '.join(chains)}",
        fees_info,
    ]
    return "\n".join(lines)
