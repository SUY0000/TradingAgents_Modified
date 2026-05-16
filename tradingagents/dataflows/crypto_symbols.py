"""Ticker-to-vendor-ID mapping for crypto data sources."""

# Maps yfinance ticker (BTC-USD) to vendor-specific identifiers
CRYPTO_SYMBOL_MAP = {
    "BTC-USD":  {"cg_id": "bitcoin",  "cp_currency": "BTC",  "defillama_slug": None,          "okx_ccy": "BTC"},
    "ETH-USD":  {"cg_id": "ethereum", "cp_currency": "ETH",  "defillama_slug": "lido",         "okx_ccy": "ETH"},
    "SOL-USD":  {"cg_id": "solana",   "cp_currency": "SOL",  "defillama_slug": None,           "okx_ccy": "SOL"},
    "BNB-USD":  {"cg_id": "binancecoin", "cp_currency": "BNB", "defillama_slug": None,         "okx_ccy": "BNB"},
    "XRP-USD":  {"cg_id": "ripple",   "cp_currency": "XRP",  "defillama_slug": None,           "okx_ccy": "XRP"},
    "DOGE-USD": {"cg_id": "dogecoin", "cp_currency": "DOGE", "defillama_slug": None,           "okx_ccy": "DOGE"},
    "ADA-USD":  {"cg_id": "cardano",  "cp_currency": "ADA",  "defillama_slug": None,           "okx_ccy": "ADA"},
    "AVAX-USD": {"cg_id": "avalanche-2", "cp_currency": "AVAX", "defillama_slug": "avalanche", "okx_ccy": "AVAX"},
    "UNI-USD":  {"cg_id": "uniswap",  "cp_currency": "UNI",  "defillama_slug": "uniswap-v3",   "okx_ccy": "UNI"},
    "LINK-USD": {"cg_id": "chainlink", "cp_currency": "LINK", "defillama_slug": None,          "okx_ccy": "LINK"},
    "LTC-USD":  {"cg_id": "litecoin", "cp_currency": "LTC",  "defillama_slug": None,           "okx_ccy": "LTC"},
    "MATIC-USD":{"cg_id": "matic-network", "cp_currency": "MATIC", "defillama_slug": "polygon","okx_ccy": "MATIC"},
    "DOT-USD":  {"cg_id": "polkadot", "cp_currency": "DOT",  "defillama_slug": None,           "okx_ccy": "DOT"},
    "TRX-USD":  {"cg_id": "tron",     "cp_currency": "TRX",  "defillama_slug": None,           "okx_ccy": "TRX"},
    "ATOM-USD": {"cg_id": "cosmos",   "cp_currency": "ATOM", "defillama_slug": None,           "okx_ccy": "ATOM"},
}


def _extract_base(ticker: str) -> str:
    """Extract base symbol from yfinance ticker like 'BTC-USD' -> 'BTC'."""
    return ticker.split("-")[0].upper()


def get_cg_id(ticker: str) -> str:
    """Return CoinGecko coin ID for the given yfinance ticker."""
    info = CRYPTO_SYMBOL_MAP.get(ticker)
    if info:
        return info["cg_id"]
    base = _extract_base(ticker)
    return base.lower()


def get_cp_currency(ticker: str) -> str:
    """Return CryptoPanic currency code for the given yfinance ticker."""
    info = CRYPTO_SYMBOL_MAP.get(ticker)
    if info:
        return info["cp_currency"]
    return _extract_base(ticker)


def get_defillama_slug(ticker: str) -> str | None:
    """Return DefiLlama protocol slug, or None if not a DeFi protocol."""
    info = CRYPTO_SYMBOL_MAP.get(ticker)
    if info:
        return info.get("defillama_slug")
    return None


def get_okx_ccy(ticker: str) -> str:
    """Return OKX currency code for the given yfinance ticker."""
    info = CRYPTO_SYMBOL_MAP.get(ticker)
    if info:
        return info["okx_ccy"]
    return _extract_base(ticker)
