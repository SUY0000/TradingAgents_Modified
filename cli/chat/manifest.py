"""run_manifest.json 读写工具。

Manifest 记录一次分析运行的标的相关参数，供 `tradingagents chat` 恢复上下文。
LLM 配置（provider/model/effort）**不**写入 manifest，始终跟随当前 CLI 配置。
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path


def safe_ticker(ticker: str) -> str:
    """把 ticker 中不适合作文件名的字符替换为下划线（BTC/USDT → BTC_USDT）。"""
    parts = Path(ticker).parts
    if Path(ticker).is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Invalid ticker path component: {ticker}")
    return ticker.replace("/", "_").replace("\\", "_").replace(":", "_")


def get_reports_dir() -> Path:
    """Return the reports directory anchored at the current working directory.

    All chat-CLI report I/O (auto-save target, chat browser scan root) goes
    through this helper so the policy is centralized. Policy: strictly
    `Path.cwd() / "reports"` — no walk-up to project root.
    """
    return Path.cwd() / "reports"


def _next_available_dir(base: Path, name: str) -> Path:
    """If base/name exists, return base/{name}_2, _3, ... until a free slot is found."""
    candidate = base / name
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = base / f"{name}_{i}"
        if not candidate.exists():
            return candidate
        i += 1


def find_report_dir(results_dir: Path, ticker: str, date: str) -> Path:
    """Find the most-recent timestamp directory for *ticker* on *date*.

    Scans {results_dir}/{safe_ticker(ticker)}/*/run_manifest.json and filters
    by manifest["analysis_date"] == date.  Returns the directory of the most
    recently created matching report (largest timestamp directory name).

    Raises FileNotFoundError if the ticker directory or a matching date is not
    found.
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise FileNotFoundError(str(exc)) from exc

    ticker_dir = Path(results_dir) / safe_ticker(ticker)
    if not ticker_dir.exists():
        raise FileNotFoundError(
            f"No reports for ticker '{ticker}': directory not found at {ticker_dir}\n"
            f"Check --ticker; run `tradingagents` first to generate a report."
        )

    matches = []
    for manifest_path in ticker_dir.glob("*/run_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if manifest.get("analysis_date") == date:
            matches.append(manifest_path.parent)

    if not matches:
        raise FileNotFoundError(
            f"No report for ticker '{ticker}' on date '{date}'.\n"
            f"Check --date; run `tradingagents` first to generate a report."
        )

    # Pick the latest by lexicographic directory name (timestamps sort correctly)
    return sorted(matches, key=lambda p: p.name, reverse=True)[0]


def write_run_manifest(
    save_path: Path,
    selections: dict,
    config: dict,
    final_state: dict,
) -> None:
    """写 {save_path}/run_manifest.json。

    save_path 是 results_dir（即 ./reports/{safe_ticker}/{timestamp}/）。
    """
    ticker = selections.get("ticker", "")
    analysis_date = selections.get("analysis_date", "")

    # 读取 asset_type 和 ccxt_symbol
    vendors = config.get("data_vendors", {})
    core = vendors.get("core_stock_apis", "yfinance")
    tech = vendors.get("technical_indicators", "yfinance")
    if core == "akshare" and tech == "akshare":
        asset_type = "a_share"
    elif core == "ccxt" and tech == "ccxt":
        asset_type = "crypto"
    else:
        asset_type = "stock"

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(tz=timezone.utc).astimezone().isoformat(),
        "analysis_date": analysis_date,

        "ticker": ticker,
        "ticker_safe": safe_ticker(ticker),
        "company_of_interest": selections.get("company_of_interest", ticker),
        "ccxt_symbol": config.get("ccxt_symbol") or None if asset_type == "crypto" else None,
        "benchmark_ticker": config.get("benchmark_ticker") or None,

        "asset_type": asset_type,
        "output_language": config.get("output_language", "English"),

        "selected_analysts": [
            a.value if hasattr(a, "value") else str(a)
            for a in selections.get("analysts", [])
        ],

        "data_vendors": copy.deepcopy(vendors),
        "tool_vendors": copy.deepcopy(config.get("tool_vendors", {})),

        "report_files": {
            "market":             "1_analysts/market.md",
            "sentiment":          "1_analysts/sentiment.md",
            "news":               "1_analysts/news.md",
            "fundamentals":       "1_analysts/fundamentals.md",
            "research_manager":   "2_research/manager.md",
            "trader":             "3_trading/trader.md",
            "risk_aggressive":    "4_risk/aggressive.md",
            "risk_conservative":  "4_risk/conservative.md",
            "risk_neutral":       "4_risk/neutral.md",
            "portfolio_decision": "5_portfolio/decision.md",
        },
    }

    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    (save_path / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_manifest(report_dir: Path) -> dict:
    """读 run_manifest.json；若不存在抛 FileNotFoundError。"""
    path = Path(report_dir) / "run_manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"run_manifest.json not found in {report_dir}\n"
            f"Re-run `tradingagents` (updated version) to generate the manifest."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_reports(report_dir: Path, manifest: dict) -> dict[str, str]:
    """按 manifest['report_files'] 逐个读取报告 markdown，返回 dict[name, content]。

    缺失文件 → 该字段为空字符串，不抛异常。
    """
    report_dir = Path(report_dir)
    result = {}
    for name, rel_path in manifest.get("report_files", {}).items():
        full_path = report_dir / rel_path
        if full_path.exists():
            result[name] = full_path.read_text(encoding="utf-8")
        else:
            result[name] = ""
    return result


def apply_manifest_to_config(config: dict, manifest: dict) -> dict:
    """把 manifest 里的标的相关字段覆盖到 config 深拷贝上，返回新 config。

    不覆盖 chat_llm_* 字段（这些跟随当前 CLI 配置）。
    """
    new_config = copy.deepcopy(config)

    if manifest.get("data_vendors"):
        if isinstance(new_config.get("data_vendors"), dict):
            new_config["data_vendors"].update(manifest["data_vendors"])
        else:
            new_config["data_vendors"] = copy.deepcopy(manifest["data_vendors"])

    if manifest.get("tool_vendors") is not None:
        new_config["tool_vendors"] = copy.deepcopy(manifest["tool_vendors"])

    if manifest.get("ccxt_symbol") is not None:
        new_config["ccxt_symbol"] = manifest["ccxt_symbol"]

    if manifest.get("benchmark_ticker") is not None:
        new_config["benchmark_ticker"] = manifest["benchmark_ticker"]

    if manifest.get("output_language"):
        new_config["output_language"] = manifest["output_language"]

    return new_config
