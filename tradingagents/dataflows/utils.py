import os
import re
import json
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Annotated

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Ticker components can contain letters, digits, dot, dash, underscore, caret
# (for index symbols like ^GSPC), and colon (for CCXT derivatives symbols).
# Crypto separators are normalized after each segment is validated.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^:]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Return a safe filesystem component for a ticker-like value."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if "\\" in value:
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )

    parts = value.split("/")
    if any(part == "" for part in parts):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    for part in parts:
        if not _TICKER_PATH_RE.fullmatch(part):
            raise ValueError(
                f"ticker contains characters not allowed in a filesystem path: {value!r}"
            )
        if set(part) == {"."}:
            raise ValueError(f"ticker cannot contain dot-only path segments: {value!r}")

    return "_".join(parts).replace(":", "_")


def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        print(f"{tag} saved to {save_path}")


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date
