"""Interactive report browser for `tradingagents chat`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import questionary


def discover_reports(results_dir: Path) -> list[dict]:
    """Scan results_dir for directories containing run_manifest.json.

    Returns a list of dicts sorted by most-recently-modified manifest first:
        {
            "report_dir": Path,
            "manifest": dict,
            "mtime": float,
            "label": str,
        }

    Skips directories without a manifest. Tolerates malformed manifests.
    Returns [] if results_dir doesn't exist.
    """
    if not results_dir.exists():
        return []

    reports = []
    for manifest_path in results_dir.glob("*/*/run_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: skipping malformed manifest {manifest_path}: {e}")
            continue
        report_dir = manifest_path.parent
        mtime = manifest_path.stat().st_mtime
        label = format_report_label(manifest, report_dir)
        reports.append({
            "report_dir": report_dir,
            "manifest": manifest,
            "mtime": mtime,
            "label": label,
        })

    reports.sort(key=lambda r: r["mtime"], reverse=True)
    return reports


def format_report_label(manifest: dict, report_dir: Path) -> str:
    """Return one-line label for the selector menu.

    Example: '2026-05-26  BTC/USDT          crypto    (session: 3 msgs)'
    """
    date = manifest.get("analysis_date", "????-??-??")
    ticker = manifest.get("ticker", "???")
    asset_type = manifest.get("asset_type", "???")

    ticker_str = ticker if len(ticker) <= 16 else ticker[:15] + "…"

    msg_count = 0
    session_path = report_dir / "sessions" / "default.jsonl"
    try:
        if session_path.exists():
            for line in session_path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    if row.get("type") == "msg":
                        msg_count += 1
                except Exception:
                    pass
    except Exception:
        pass

    return f"{date:<10}  {ticker_str:<16}  {asset_type:<8}  (session: {msg_count} msgs)"


def pick_report(results_dir: Path) -> Optional[Path]:
    """Show questionary.select() over discover_reports() output.

    Returns the chosen report_dir, or None if cancelled (Ctrl-C) or no
    reports found.
    """
    reports = discover_reports(results_dir)
    if not reports:
        print(f"No reports found in {results_dir}")
        return None

    choices = [
        questionary.Choice(r["label"], value=r["report_dir"])
        for r in reports
    ]

    return questionary.select(
        "Select a report to chat about:",
        choices=choices,
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select\n- Ctrl-C to cancel",
        style=questionary.Style([
            ("selected", "fg:cyan noinherit"),
            ("highlighted", "fg:cyan noinherit"),
            ("pointer", "fg:cyan noinherit"),
        ]),
    ).ask()
