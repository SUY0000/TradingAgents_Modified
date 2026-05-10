"""AKShare data vendor for A-share (China mainland) stock markets.

Symbol format (external): 600519.SH / 000001.SZ / 430047.BJ
Internal conversion via _resolve_a_share_symbol() before each akshare call.

Config fields: none specific (uses data_cache_dir from global config).
"""

import os
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Annotated, Literal

import pandas as pd
from stockstats import wrap

from .config import get_config
from .stockstats_utils import _clean_dataframe
from .ccxt_data import best_ind_params


# ---------------------------------------------------------------------------
# Symbol format helpers
# ---------------------------------------------------------------------------

def _resolve_a_share_symbol(
    symbol: str,
    fmt: Literal["6digit", "exchange_prefix", "baostock"] = "6digit",
) -> str:
    """Convert external ticker (600519.SH) to the format required by a given akshare API.

    Args:
        symbol: Ticker in "XXXXXX.EX" form, e.g. "600519.SH", "000001.SZ".
        fmt: Target format:
            "6digit"         → "600519"    (most OHLCV / financial statement APIs)
            "exchange_prefix"→ "SH600519"  (some fund-flow APIs)
            "baostock"       → "sh.600519" (reserved for future baostock use)
    """
    if "." in symbol:
        code, exchange = symbol.rsplit(".", 1)
        exchange = exchange.upper()
    else:
        code = symbol
        exchange = "SH"

    if fmt == "6digit":
        return code
    elif fmt == "exchange_prefix":
        return f"{exchange}{code}"
    elif fmt == "baostock":
        return f"{exchange.lower()}.{code}"
    return code


def _get_exchange(symbol: str) -> str:
    """Extract exchange suffix from ticker: 'SH', 'SZ', or 'BJ'."""
    if "." in symbol:
        return symbol.rsplit(".", 1)[1].upper()
    return "SH"


def _throttle() -> None:
    """Sleep 0.5 s before each akshare call to avoid IP-level soft throttling."""
    time.sleep(0.5)


def _ak_date(date_str: str) -> str:
    """Convert YYYY-MM-DD → YYYYMMDD (no dashes) as required by some akshare APIs."""
    return date_str.replace("-", "")


# ---------------------------------------------------------------------------
# OHLCV with file-based caching
# ---------------------------------------------------------------------------

def _load_akshare_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch A-share daily OHLCV with 5-year look-back and file-based cache.

    Caches per symbol; rows after curr_date are dropped to prevent
    look-ahead bias consistent with yfinance / CCXT vendors.
    """
    import akshare as ak

    config = get_config()
    code = _resolve_a_share_symbol(symbol, "6digit")
    curr_date_dt = pd.to_datetime(curr_date)

    today = pd.Timestamp.today()
    start_date = today - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    cache_dir = config.get("data_cache_dir", "")
    os.makedirs(cache_dir, exist_ok=True)
    safe_symbol = symbol.replace(".", "_")
    cache_file = os.path.join(
        cache_dir,
        f"{safe_symbol}-AKSHARE-data-{start_str}-{end_str}.csv",
    )

    if os.path.exists(cache_file):
        data = pd.read_csv(cache_file, on_bad_lines="skip", encoding="utf-8")
    else:
        _throttle()
        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=_ak_date(start_str),
            end_date=_ak_date(end_str),
            adjust="qfq",
        )
        col_map = {
            "日期": "Date", "开盘": "Open", "最高": "High",
            "最低": "Low", "收盘": "Close", "成交量": "Volume",
        }
        raw = raw.rename(columns=col_map)
        raw["Adj Close"] = raw["Close"]
        keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in raw.columns]
        data = raw[keep]
        data.to_csv(cache_file, index=False, encoding="utf-8")

    data = _clean_dataframe(data)
    data = data[data["Date"] <= curr_date_dt]
    return data


# ---------------------------------------------------------------------------
# Core 4-category vendor functions
# ---------------------------------------------------------------------------

def get_akshare_stock_data(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH or 000001.SZ"],
    start_date: Annotated[str, "Start date, yyyy-mm-dd"],
    end_date: Annotated[str, "End date, yyyy-mm-dd"],
    **kwargs,
) -> str:
    """Fetch A-share daily OHLCV price data (qfq forward-adjusted) via akshare."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    data = _load_akshare_ohlcv(symbol, end_date)

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    data = data[(data["Date"] >= start_dt) & (data["Date"] <= end_dt)]

    if len(data) > 60:
        data = data.tail(60)

    if data.empty:
        return f"No data found for '{symbol}' between {start_date} and {end_date}"

    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        if col in data.columns:
            data[col] = data[col].round(2)
    if "Volume" in data.columns:
        data["Volume"] = data["Volume"].round(0).astype("int64")

    csv_string = data.to_csv(index=False)
    header = (
        f"# A-share data for {symbol} from {start_date} to {end_date}\n"
        f"# Source: akshare (qfq forward-adjusted)\n"
        f"# Total records: {len(data)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + csv_string


def get_akshare_indicators(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    indicator: Annotated[str, "Technical indicator(s), comma-separated"],
    curr_date: Annotated[str, "Current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 14,
    **kwargs,
) -> str:
    """Calculate technical indicators for an A-share using stockstats on akshare OHLCV."""
    indicators = [ind.strip() for ind in indicator.split(",")]

    for ind in indicators:
        if ind not in best_ind_params:
            raise ValueError(
                f"Indicator '{ind}' not supported. Choose from: {list(best_ind_params.keys())}"
            )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    data = _load_akshare_ohlcv(symbol, curr_date)
    df = wrap(data)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    result_parts = []
    for ind in indicators:
        df[ind]  # trigger stockstats calculation

        date_values = []
        current_dt = curr_date_dt
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            matching = df[df["Date"] == date_str]
            if not matching.empty:
                val = matching[ind].values[0]
                date_values.append((date_str, "N/A" if pd.isna(val) else str(round(float(val), 4))))
            current_dt -= relativedelta(days=1)

        ind_str = "\n".join(f"{d}: {v}" for d, v in date_values)
        result_parts.append(
            f"## {ind} values from {before.strftime('%Y-%m-%d')} to {curr_date} ({symbol}):\n\n"
            f"{ind_str}\n\n{best_ind_params.get(ind, '')}"
        )

    return "\n\n---\n\n".join(result_parts)


def get_akshare_fundamentals(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"],
    **kwargs,
) -> str:
    """Fetch A-share fundamental valuation metrics (PE, PB, PS, dividend yield) via akshare."""
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    result = f"## A-Share Fundamentals for {symbol} (as of {curr_date})\n\n"

    try:
        _throttle()
        info_df = ak.stock_individual_info_em(symbol=code)
        if not info_df.empty:
            result += "### Company Information\n"
            for _, row in info_df.iterrows():
                result += f"- {row.iloc[0]}: {row.iloc[1]}\n"
            result += "\n"
    except Exception as e:
        result += f"Company info unavailable: {e}\n\n"

    try:
        _throttle()
        val_df = ak.stock_a_indicator_lg(symbol=code)
        if not val_df.empty:
            curr_dt = pd.to_datetime(curr_date)
            if "trade_date" in val_df.columns:
                val_df["trade_date"] = pd.to_datetime(val_df["trade_date"], errors="coerce")
                val_df = val_df[val_df["trade_date"] <= curr_dt]
            result += "### Valuation Metrics (recent 30 trading days)\n"
            result += val_df.tail(30).to_string(index=False) + "\n"
    except Exception as e:
        result += f"Valuation metrics unavailable: {e}\n"

    return result


def _financial_stmt(symbol: str, fetch_fn, label: str) -> str:
    """Shared helper for balance sheet / cashflow / income statement fetching."""
    # akshare financial statement APIs require exchange_prefix format: SH600519 / SZ000001
    ex_code = _resolve_a_share_symbol(symbol, "exchange_prefix")
    try:
        _throttle()
        df = fetch_fn(symbol=ex_code)
        if df is None or df.empty:
            return f"No {label} data for {symbol}"
        # Wide format: rows = report periods, keep key metric columns (first 20)
        display = df.iloc[:, :20] if df.shape[1] > 20 else df
        return f"## {label} for {symbol} (most recent periods)\n\n{display.to_string(index=False)}\n"
    except Exception as e:
        return f"Error fetching {label} for {symbol}: {str(e)}"


def get_akshare_balance_sheet(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    freq: Annotated[str, "Frequency ('annual' or 'quarterly')"] = "annual",
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"] = "",
    **kwargs,
) -> str:
    """Fetch A-share balance sheet (资产负债表) via akshare 东方财富."""
    import akshare as ak
    return _financial_stmt(symbol, ak.stock_balance_sheet_by_report_em, "Balance Sheet")


def get_akshare_cashflow(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    freq: Annotated[str, "Frequency ('annual' or 'quarterly')"] = "annual",
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"] = "",
    **kwargs,
) -> str:
    """Fetch A-share cash flow statement (现金流量表) via akshare 东方财富."""
    import akshare as ak
    return _financial_stmt(symbol, ak.stock_cash_flow_sheet_by_report_em, "Cash Flow Statement")


def get_akshare_income_statement(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    freq: Annotated[str, "Frequency ('annual' or 'quarterly')"] = "annual",
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"] = "",
    **kwargs,
) -> str:
    """Fetch A-share income statement (利润表) via akshare 东方财富."""
    import akshare as ak
    return _financial_stmt(symbol, ak.stock_profit_sheet_by_report_em, "Income Statement")


def get_akshare_news(
    ticker: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 7,
    **kwargs,
) -> str:
    """Fetch A-share company news via akshare 东方财富."""
    import akshare as ak

    code = _resolve_a_share_symbol(ticker, "6digit")
    try:
        _throttle()
        df = ak.stock_news_em(symbol=code)
        if df.empty:
            return f"No news found for {ticker}"

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=look_back_days)

        date_col = next((c for c in df.columns if "时间" in c or "日期" in c), None)
        if date_col:
            df["_dt"] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[(df["_dt"] >= start_dt) & (df["_dt"] <= curr_dt + relativedelta(days=1))]

        if df.empty:
            return f"No news found for {ticker} in the last {look_back_days} days before {curr_date}"

        title_col = next((c for c in df.columns if "标题" in c), df.columns[0])
        content_col = next((c for c in df.columns if "内容" in c), None)

        news_str = ""
        for _, row in df.head(20).iterrows():
            title = row.get(title_col, "No title")
            date_str = str(row.get(date_col, "")) if date_col else ""
            news_str += f"### {title}\n"
            if date_str:
                news_str += f"Date: {date_str}\n"
            if content_col and pd.notna(row.get(content_col)):
                news_str += f"{str(row[content_col])[:300]}...\n"
            news_str += "\n"

        return f"## {ticker} News, from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n{news_str}"
    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"


def get_akshare_global_news(
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 7,
    **kwargs,
) -> str:
    """Fetch A-share macro/economic news via akshare (百度财经)."""
    import akshare as ak

    try:
        _throttle()
        df = ak.news_economic_baidu()
        if df.empty:
            return f"No global news found for {curr_date}"

        news_str = ""
        for _, row in df.head(20).iterrows():
            title = str(row.iloc[0]) if len(row) > 0 else "No title"
            summary = str(row.iloc[1])[:300] if len(row) > 1 else ""
            news_str += f"### {title}\n"
            if summary and summary != "nan":
                news_str += f"{summary}...\n"
            news_str += "\n"

        return f"## Global Market News (A-share context), as of {curr_date}:\n\n{news_str}"
    except Exception as e:
        return f"Error fetching global news: {str(e)}"


def get_akshare_insider_transactions(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    curr_date: Annotated[str, "Current date, YYYY-mm-dd"],
    **kwargs,
) -> str:
    """Fetch A-share major shareholder / executive stake change records via CNINFO."""
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    # Look back 1 year from curr_date
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - relativedelta(years=1)
    try:
        _throttle()
        df = ak.stock_share_change_cninfo(
            symbol=code,
            start_date=_ak_date(start_dt.strftime("%Y-%m-%d")),
            end_date=_ak_date(curr_date),
        )
        if df is None or df.empty:
            return f"No major shareholder stake change data for {symbol} in the past year"
        return (
            f"## Major Shareholder / Executive Stake Changes for {symbol} (past 12 months)\n\n"
            f"{df.head(20).to_string(index=False)}\n"
        )
    except Exception as e:
        return f"Error fetching insider transactions for {symbol}: {str(e)}"


# ---------------------------------------------------------------------------
# A-share specific microstructure: 6 tools
# ---------------------------------------------------------------------------

def get_akshare_dragon_tiger(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Fetch Dragon-Tiger List (龙虎榜) historical appearances for an A-share stock.

    The Dragon-Tiger List records institutional and hot-money (游资) buy/sell
    activity on dates when a stock triggers the exchange's abnormal-fluctuation
    alert (e.g. ≥3 consecutive limit-ups, or price swing >15% intraday).
    """
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    try:
        _throttle()
        # Returns dates when the stock appeared on the Dragon-Tiger List
        df = ak.stock_lhb_stock_detail_date_em(symbol=code)
        if df is None or df.empty:
            return f"No Dragon-Tiger List appearances on record for {symbol}"

        # Filter to the requested date range
        date_col = next((c for c in df.columns if "交易日" in c or "日期" in c), df.columns[-1])
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[
            (df[date_col] >= pd.to_datetime(start_date)) &
            (df[date_col] <= pd.to_datetime(end_date))
        ]

        if df.empty:
            return f"No Dragon-Tiger List appearances for {symbol} between {start_date} and {end_date}"

        return (
            f"## Dragon-Tiger List Appearances for {symbol} ({start_date} to {end_date})\n"
            f"({len(df)} appearance(s) — triggered by abnormal price/volume activity)\n\n"
            f"{df.to_string(index=False)}\n"
        )
    except Exception as e:
        return f"Dragon-Tiger list data unavailable for {symbol}: {str(e)}"


def get_akshare_northbound_holding(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Fetch northbound (Stock Connect) holding changes for an A-share stock.

    Shows Hong Kong-registered foreign capital's holdings via Shanghai-HK
    and Shenzhen-HK Stock Connect. Rising holdings signal foreign accumulation;
    falling signals distribution. A key indicator of smart-money sentiment.
    """
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    try:
        _throttle()
        df = ak.stock_hsgt_individual_em(symbol=code)
        if df.empty:
            return f"No northbound holding data for {symbol}"

        date_col = next((c for c in df.columns if "日期" in c or "date" in c.lower()), None)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[
                (df[date_col] >= pd.to_datetime(start_date)) &
                (df[date_col] <= pd.to_datetime(end_date))
            ]

        if df.empty:
            return f"No northbound holding changes for {symbol} between {start_date} and {end_date}"

        return (
            f"## Northbound (Stock Connect) Holdings for {symbol} ({start_date} to {end_date})\n\n"
            f"{df.to_string(index=False)}\n"
        )
    except Exception as e:
        return f"Northbound holding data unavailable for {symbol}: {str(e)}"


def get_akshare_main_capital_flow(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Fetch main-force capital flow (主力资金流向) for an A-share stock.

    Breaks net inflow into tiers: super-large (超大单 ≥1M CNY), large (大单
    100k-1M), medium (中单 10k-100k), small (小单 <10k). Persistent positive
    main-force net inflow indicates institutional accumulation. Units: CNY.
    """
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    exchange = _get_exchange(symbol)
    market = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exchange, "sh")

    try:
        _throttle()
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df.empty:
            return f"No capital flow data for {symbol}"

        date_col = next((c for c in df.columns if "日期" in c or "date" in c.lower()), None)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[
                (df[date_col] >= pd.to_datetime(start_date)) &
                (df[date_col] <= pd.to_datetime(end_date))
            ]

        if df.empty:
            return f"No capital flow data for {symbol} between {start_date} and {end_date}"

        return (
            f"## Main Capital Flow for {symbol} ({start_date} to {end_date})\n"
            f"(Positive = net buy; Negative = net sell; Units: CNY)\n\n"
            f"{df.to_string(index=False)}\n"
        )
    except Exception as e:
        return f"Capital flow data unavailable for {symbol}: {str(e)}"


def get_akshare_limit_status(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Detect limit-up (涨停) / limit-down (跌停) events for an A-share stock.

    Computed from OHLCV daily price changes: ≥+9.9% = limit-up trigger,
    ≤-9.9% = limit-down trigger. STAR Market / ChiNext new listings use ±20%
    limits; the threshold here is conservative to catch both regimes.
    Frequent limit-ups signal strong momentum; limit-downs may signal panic or
    fundamental deterioration.
    """
    data = _load_akshare_ohlcv(symbol, end_date)

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    data = data[(data["Date"] >= start_dt) & (data["Date"] <= end_dt)].copy()

    if data.empty:
        return f"No OHLCV data for {symbol} between {start_date} and {end_date}"

    data = data.sort_values("Date").reset_index(drop=True)
    data["pct_change"] = data["Close"].pct_change() * 100

    limit_up = data[data["pct_change"] >= 9.9]
    limit_down = data[data["pct_change"] <= -9.9]

    result = f"## Limit-Up/Down Events for {symbol} ({start_date} to {end_date})\n"
    result += "(Detected from daily close-to-close change: ≥+9.9% = limit-up; ≤-9.9% = limit-down)\n\n"

    if not limit_up.empty:
        result += f"**Limit-Up Events ({len(limit_up)}):**\n"
        for _, row in limit_up.iterrows():
            result += f"  - {row['Date'].strftime('%Y-%m-%d')}: +{row['pct_change']:.2f}%\n"
    else:
        result += "No limit-up events in this period.\n"

    if not limit_down.empty:
        result += f"\n**Limit-Down Events ({len(limit_down)}):**\n"
        for _, row in limit_down.iterrows():
            result += f"  - {row['Date'].strftime('%Y-%m-%d')}: {row['pct_change']:.2f}%\n"
    else:
        result += "\nNo limit-down events in this period.\n"

    return result


def get_akshare_sector_performance(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Fetch the stock's Shenwan (申万) L1 industry sector OHLCV performance.

    Resolves the stock's Shenwan Level-1 industry then fetches the sector
    index OHLCV for the period. Use for sector rotation analysis and
    relative-strength comparison: if the stock outperforms its sector,
    it has stock-specific alpha.
    """
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    try:
        _throttle()
        info_df = ak.stock_individual_info_em(symbol=code)
        sector_name = None
        if not info_df.empty:
            for _, row in info_df.iterrows():
                key = str(row.iloc[0]) if len(row) > 0 else ""
                if "行业" in key:
                    sector_name = str(row.iloc[1]) if len(row) > 1 else None
                    break

        if not sector_name:
            return f"Could not determine Shenwan industry sector for {symbol}"

        _throttle()
        df = ak.stock_board_industry_hist_em(
            symbol=sector_name,
            start_date=_ak_date(start_date),
            end_date=_ak_date(end_date),
            period="日k",
            adjust="",
        )

        if df.empty:
            return f"No sector data for '{sector_name}' (industry of {symbol})"

        return (
            f"## Sector Performance: {sector_name} (Shenwan L1 industry of {symbol})\n"
            f"Period: {start_date} to {end_date}\n\n"
            f"{df.to_string(index=False)}\n"
        )
    except Exception as e:
        return f"Sector performance data unavailable for {symbol}: {str(e)}"


def get_akshare_margin_balance(
    symbol: Annotated[str, "A-share ticker, e.g. 600519.SH"],
    start_date: Annotated[str, "Start date, YYYY-mm-dd"],
    end_date: Annotated[str, "End date, YYYY-mm-dd"],
) -> str:
    """Fetch margin finance and short-selling balance (融资融券) for an A-share stock.

    融资余额 (margin financing balance): leveraged long positions; rising signals
    bullish sentiment and leverage build-up (also a liquidation risk).
    融券余额 (short-selling balance): rising signals bearish positioning.
    Data sampled weekly to limit API calls. SSE stocks use Shanghai exchange
    data; SZSE stocks use Shenzhen exchange data.
    """
    import akshare as ak

    code = _resolve_a_share_symbol(symbol, "6digit")
    exchange = _get_exchange(symbol)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    all_rows = []
    current_dt = start_dt
    while current_dt <= end_dt:
        # SSE and SZSE margin APIs require YYYYMMDD format (no dashes)
        date_str = current_dt.strftime("%Y%m%d")
        try:
            _throttle()
            if exchange == "SZ":
                df = ak.stock_margin_detail_szse(date=date_str)
            else:
                df = ak.stock_margin_detail_sse(date=date_str)

            if not df.empty:
                code_col = next(
                    (c for c in df.columns if "代码" in c or "证券代码" in c), None
                )
                if code_col and code in df[code_col].astype(str).values:
                    row = df[df[code_col].astype(str) == code].copy()
                    row["查询日期"] = current_dt.strftime("%Y-%m-%d")
                    all_rows.append(row)
        except Exception:
            pass
        current_dt += relativedelta(days=7)  # weekly sampling

    if not all_rows:
        return f"No margin balance data for {symbol} between {start_date} and {end_date}"

    result_df = pd.concat(all_rows, ignore_index=True)
    return (
        f"## Margin Balance (融资融券) for {symbol} ({start_date} to {end_date})\n"
        f"(Weekly sampling; units: CNY)\n\n"
        f"{result_df.to_string(index=False)}\n"
    )
