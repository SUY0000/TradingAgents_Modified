"""Smoke tests for akshare vendor functions.

Run with: python tests/test_akshare_smoke.py
All functions should return non-empty strings without raising exceptions.
"""

from tradingagents.dataflows.akshare_data import (
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

SYMBOL = "600519.SH"   # Kweichow Moutai — highly liquid, stable A-share
START = "2026-04-01"
END = "2026-05-09"
CURR = "2026-05-09"


def run(name, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        assert result and len(result) > 20, f"Result too short: {result!r}"
        print(f"[OK] {name}: {result[:120].strip()}...")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


if __name__ == "__main__":
    run("get_akshare_stock_data",      get_akshare_stock_data,      SYMBOL, START, END)
    run("get_akshare_indicators",      get_akshare_indicators,      SYMBOL, "close_50_sma,rsi", CURR, 14)
    run("get_akshare_fundamentals",    get_akshare_fundamentals,    SYMBOL, CURR)
    run("get_akshare_balance_sheet",   get_akshare_balance_sheet,   SYMBOL, "annual", CURR)
    run("get_akshare_cashflow",        get_akshare_cashflow,        SYMBOL, "annual", CURR)
    run("get_akshare_income_statement",get_akshare_income_statement,SYMBOL, "annual", CURR)
    run("get_akshare_news",            get_akshare_news,            SYMBOL, CURR, 30)
    run("get_akshare_global_news",     get_akshare_global_news,     CURR, 7)
    run("get_akshare_insider_transactions", get_akshare_insider_transactions, SYMBOL, CURR)
    run("get_akshare_dragon_tiger",    get_akshare_dragon_tiger,    SYMBOL, START, END)
    run("get_akshare_northbound_holding", get_akshare_northbound_holding, SYMBOL, START, END)
    run("get_akshare_main_capital_flow",  get_akshare_main_capital_flow,  SYMBOL, START, END)
    run("get_akshare_limit_status",    get_akshare_limit_status,    SYMBOL, START, END)
    run("get_akshare_sector_performance", get_akshare_sector_performance, SYMBOL, START, END)
    run("get_akshare_margin_balance",  get_akshare_margin_balance,  SYMBOL, START, END)
