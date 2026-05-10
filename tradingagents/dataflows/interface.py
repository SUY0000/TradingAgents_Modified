from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .ccxt_data import (
    get_ccxt_stock_data,
    get_ccxt_indicators,
)
from .akshare_data import (
    get_akshare_stock_data,
    get_akshare_indicators,
    get_akshare_fundamentals,
    get_akshare_balance_sheet,
    get_akshare_cashflow,
    get_akshare_income_statement,
    get_akshare_news,
    get_akshare_global_news,
    get_akshare_insider_transactions,
    get_akshare_dragon_tiger,
    get_akshare_northbound_holding,
    get_akshare_main_capital_flow,
    get_akshare_limit_status,
    get_akshare_sector_performance,
    get_akshare_margin_balance,
)
from .okx_data import (
    get_okx_funding_rate,
    get_okx_open_interest_history,
    get_okx_long_short_ratio,
    get_okx_taker_volume,
    get_okx_elite_long_short_ratio,
    get_okx_aggregated_oi_volume,
    get_okx_put_call_ratio,
)

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "crypto_market_data": {
        "description": "Crypto-specific market microstructure data (OKX only): funding rates, open interest, long/short ratios, taker volume, elite trader ratios, put/call ratio",
        "tools": [
            "get_funding_rate",
            "get_open_interest",
            "get_long_short_ratio",
            "get_taker_volume",
            "get_elite_long_short_ratio",
            "get_aggregated_oi_volume",
            "get_put_call_ratio",
        ]
    },
    "cn_market_data": {
        "description": "A-share specific microstructure data (akshare only): Dragon-Tiger list, northbound holdings, main capital flow, limit-up/down status, sector performance, margin balance",
        "tools": [
            "get_dragon_tiger",
            "get_northbound_holding",
            "get_main_capital_flow",
            "get_limit_status",
            "get_sector_performance",
            "get_margin_balance",
        ]
    },
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "ccxt",
    "akshare",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "ccxt": get_ccxt_stock_data,
        "akshare": get_akshare_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "ccxt": get_ccxt_indicators,
        "akshare": get_akshare_indicators,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "akshare": get_akshare_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "akshare": get_akshare_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "akshare": get_akshare_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "akshare": get_akshare_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
        "akshare": get_akshare_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "akshare": get_akshare_insider_transactions,
    },
    # cn_market_data — akshare only
    "get_dragon_tiger": {
        "akshare": get_akshare_dragon_tiger,
    },
    "get_northbound_holding": {
        "akshare": get_akshare_northbound_holding,
    },
    "get_main_capital_flow": {
        "akshare": get_akshare_main_capital_flow,
    },
    "get_limit_status": {
        "akshare": get_akshare_limit_status,
    },
    "get_sector_performance": {
        "akshare": get_akshare_sector_performance,
    },
    "get_margin_balance": {
        "akshare": get_akshare_margin_balance,
    },
    # crypto_market_data — OKX only
    "get_funding_rate": {
        "okx": get_okx_funding_rate,
    },
    "get_open_interest": {
        "okx": get_okx_open_interest_history,
    },
    "get_long_short_ratio": {
        "okx": get_okx_long_short_ratio,
    },
    "get_taker_volume": {
        "okx": get_okx_taker_volume,
    },
    "get_elite_long_short_ratio": {
        "okx": get_okx_elite_long_short_ratio,
    },
    "get_aggregated_oi_volume": {
        "okx": get_okx_aggregated_oi_volume,
    },
    "get_put_call_ratio": {
        "okx": get_okx_put_call_ratio,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Only rate limits trigger fallback

    raise RuntimeError(f"No available vendor for '{method}'")