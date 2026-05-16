"""Ticker-to-vendor-ID mapping for crypto data sources.

All public functions accept any of these input formats:
  - CCXT spot:    "BTC/USDT"
  - CCXT linear:  "ETH/USDT:USDT"
  - OKX instId:   "BTC-USDT-SWAP"
  - Base only:    "BTC"

The map is keyed by uppercase base currency so lookups work regardless
of quote currency or suffix.
"""

# Keyed by uppercase base currency (e.g. "BTC", "ETH")
CRYPTO_SYMBOL_MAP = {
    "BTC":   {"cg_id": "bitcoin",       "defillama_slug": None},
    "ETH":   {"cg_id": "ethereum",      "defillama_slug": "lido"},
    "SOL":   {"cg_id": "solana",        "defillama_slug": None},
    "BNB":   {"cg_id": "binancecoin",   "defillama_slug": None},
    "XRP":   {"cg_id": "ripple",        "defillama_slug": None},
    "DOGE":  {"cg_id": "dogecoin",      "defillama_slug": None},
    "ADA":   {"cg_id": "cardano",       "defillama_slug": None},
    "AVAX":  {"cg_id": "avalanche-2",   "defillama_slug": "avalanche"},
    "UNI":   {"cg_id": "uniswap",       "defillama_slug": "uniswap-v3"},
    "LINK":  {"cg_id": "chainlink",     "defillama_slug": None},
    "LTC":   {"cg_id": "litecoin",      "defillama_slug": None},
    "MATIC": {"cg_id": "matic-network", "defillama_slug": "polygon"},
    "DOT":   {"cg_id": "polkadot",      "defillama_slug": None},
    "TRX":   {"cg_id": "tron",          "defillama_slug": None},
    "ATOM":  {"cg_id": "cosmos",        "defillama_slug": None},
}


def ccxt_to_base(symbol: str) -> str:
    """Extract the base currency from any CCXT/OKX symbol format.

    Examples:
        "BTC/USDT"       -> "BTC"
        "ETH/USDT:USDT"  -> "ETH"
        "BTC-USDT-SWAP"  -> "BTC"
        "BTC"            -> "BTC"
    """
    sym = symbol.split(":")[0]                          # strip margin suffix
    sym = sym.replace("-SWAP", "").replace("-FUTURES", "")
    parts = sym.replace("/", "-").split("-")
    return parts[0].upper()


def get_cg_id(symbol: str) -> str:
    """Return CoinGecko coin ID for any CCXT/OKX symbol or base currency."""
    base = ccxt_to_base(symbol)
    info = CRYPTO_SYMBOL_MAP.get(base)
    if info:
        return info["cg_id"]
    return base.lower()


def get_defillama_slug(symbol: str) -> str | None:
    """Return DefiLlama protocol slug, or None if not a DeFi protocol."""
    base = ccxt_to_base(symbol)
    info = CRYPTO_SYMBOL_MAP.get(base)
    if info:
        return info.get("defillama_slug")
    return None


def get_okx_ccy(symbol: str) -> str:
    """Return OKX currency code (uppercase base) for any CCXT/OKX symbol."""
    return ccxt_to_base(symbol)


def ccxt_to_display_ticker(ccxt_symbol: str) -> str:
    """Derive a human-readable display ticker from a CCXT symbol.

    Used as company_of_interest in graph state so reports reference
    a stable identifier rather than the internal CCXT pair format.

    Examples:
        "BTC/USDT"       -> "BTC/USDT"
        "ETH/USDT:USDT"  -> "ETH/USDT"  (margin suffix stripped)
        "BTC-USDT-SWAP"  -> "BTC/USDT"   (OKX instId normalised)
    """
    sym = ccxt_symbol.split(":")[0]                     # strip margin suffix
    sym = sym.replace("-SWAP", "").replace("-FUTURES", "")
    # Normalise OKX instId dashes to CCXT slash only for BASE-QUOTE pairs
    parts = sym.split("-")
    if len(parts) == 2:
        return f"{parts[0]}/{parts[1]}"
    return sym.replace("-", "/")
