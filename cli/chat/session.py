"""Chat session persistence — JSONL read/write for multi-turn chat history."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def default_session_path(report_dir: Path) -> Path:
    return Path(report_dir) / "sessions" / "default.jsonl"


_TS_FORMAT = "%Y%m%d-%H%M%S"
_TS_PREFIX_LEN = 15   # "YYYYMMDD-HHMMSS"


def _ts_slug() -> str:
    return datetime.now().strftime(_TS_FORMAT)


def _sanitize_title(title: str) -> str:
    """Lowercase, non-alnum/underscore → '-', trim ≤40 chars, fallback 'untitled'."""
    s = (title or "").strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "-", s).strip("-")
    s = s[:40]
    return s or "untitled"


def make_session_path(report_dir: Path, title: str = "default") -> Path:
    """Return a fresh session jsonl path under {report_dir}/sessions/."""
    return Path(report_dir) / "sessions" / f"{_ts_slug()}-{_sanitize_title(title)}.jsonl"


def list_sessions(report_dir: Path) -> list[dict]:
    """Scan {report_dir}/sessions/*.jsonl, parse header line, return sorted by mtime desc.

    Each item: {"path": Path, "id": str, "title": str, "created_at": str, "mtime": float, "n_msgs": int}
    Files whose first line fails JSON parse are silently skipped.
    """
    sessions_dir = Path(report_dir) / "sessions"
    if not sessions_dir.exists():
        return []
    out = []
    for p in sessions_dir.glob("*.jsonl"):
        try:
            with open(p, encoding="utf-8") as f:
                first = f.readline().strip()
                if not first:
                    continue
                header = json.loads(first)
                # Count msg lines (excluding header)
                n_msgs = 0
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            if d.get("type") == "msg":
                                n_msgs += 1
                        except json.JSONDecodeError:
                            pass
            if header.get("type") != "header":
                continue
            out.append({
                "path": p,
                "id": header.get("id", ""),
                "title": header.get("title", p.stem),
                "created_at": header.get("created_at", ""),
                "mtime": p.stat().st_mtime,
                "n_msgs": n_msgs,
            })
        except (OSError, json.JSONDecodeError):
            continue
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def latest_session_path(report_dir: Path) -> Path | None:
    sessions = list_sessions(report_dir)
    return sessions[0]["path"] if sessions else None


def rewrite_header(session_path: Path, **updates) -> None:
    """Atomically rewrite the JSONL header line with merged updates."""
    session_path = Path(session_path)
    lines = session_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    header = json.loads(lines[0])
    header.update(updates)
    lines[0] = json.dumps(header, ensure_ascii=False)
    tmp = session_path.with_suffix(session_path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, session_path)


def rename_session_file(session_path: Path, new_title: str) -> Path:
    """Rename the jsonl file, preserving the timestamp prefix if present.

    If the existing filename has a valid YYYYMMDD-HHMMSS prefix, keep it.
    Otherwise prepend a fresh _ts_slug() prefix.
    Returns the new path. File is moved on disk via os.replace.
    """
    session_path = Path(session_path)
    stem = session_path.stem
    prefix = stem[:_TS_PREFIX_LEN]
    try:
        datetime.strptime(prefix, _TS_FORMAT)
        ts = prefix
    except ValueError:
        ts = _ts_slug()
    new_name = f"{ts}-{_sanitize_title(new_title)}.jsonl"
    new_path = session_path.parent / new_name
    if new_path == session_path:
        return session_path
    os.replace(session_path, new_path)
    return new_path


def delete_session(session_path: Path) -> None:
    Path(session_path).unlink(missing_ok=True)


def ensure_session(session_path: Path, manifest: dict, title: str = "default") -> None:
    """Create the session file with a header line if it does not exist."""
    session_path = Path(session_path)
    if session_path.exists():
        return
    session_path.parent.mkdir(parents=True, exist_ok=True)
    ticker = manifest.get("ticker", "")
    date = manifest.get("analysis_date", "")
    ticker_safe = manifest.get("ticker_safe", ticker.replace("/", "_"))
    header = {
        "type": "header",
        "schema_version": 1,
        "id": str(uuid.uuid4()),
        "title": title,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "report_ref": f"{ticker_safe}/{date}",
    }
    session_path.write_text(json.dumps(header, ensure_ascii=False) + "\n", encoding="utf-8")


def load_messages(session_path: Path) -> list:
    """Read JSONL, skip the header line, return list of LangChain messages."""
    session_path = Path(session_path)
    if not session_path.exists():
        return []
    raw_msgs = []
    with open(session_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") == "header":
                continue
            if d.get("type") == "msg":
                raw_msgs.append(d)

    messages = [jsonl_to_msg(d) for d in raw_msgs]
    return _repair_incomplete_tool_calls(messages)


def _repair_incomplete_tool_calls(messages: list) -> list:
    """Drop the trailing user turn if its tool_calls are missing tool results."""
    for ai_idx in range(len(messages) - 1, -1, -1):
        ai_msg = messages[ai_idx]
        if not isinstance(ai_msg, AIMessage) or not getattr(ai_msg, "tool_calls", None):
            continue

        expected_ids = {tc.get("id") for tc in ai_msg.tool_calls if tc.get("id")}
        following = messages[ai_idx + 1:]
        actual_ids = {
            msg.tool_call_id
            for msg in following
            if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None)
        }
        if expected_ids and expected_ids.issubset(actual_ids):
            return messages

        cut_idx = ai_idx
        for idx in range(ai_idx - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                cut_idx = idx
                break
        return messages[:cut_idx]

    return messages


def append_message(session_path: Path, msg: dict) -> None:
    """Append one JSONL line. msg must have type='msg'."""
    with open(session_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def truncate_last_message(session_path: Path) -> None:
    """Remove the last persisted message row while preserving the session header."""
    session_path = Path(session_path)
    lines = session_path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= 1:
        return
    lines = lines[:-1]
    session_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── LangChain ↔ JSONL conversion ────────────────────────────────────────────

def msg_to_jsonl(message, model: str = "", effort: str = "") -> dict:
    """Convert a LangChain BaseMessage to a JSONL dict."""
    ts = datetime.now(tz=timezone.utc).isoformat()
    if isinstance(message, HumanMessage):
        return {"type": "msg", "role": "user", "ts": ts, "content": message.content}
    if isinstance(message, AIMessage):
        d = {
            "type": "msg",
            "role": "assistant",
            "ts": ts,
            "model": model,
            "effort": effort,
            "content": message.content if isinstance(message.content, str) else "",
        }
        if message.tool_calls:
            d["tool_calls"] = [
                {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                for tc in message.tool_calls
            ]
        return d
    if isinstance(message, ToolMessage):
        return {
            "type": "msg",
            "role": "tool",
            "ts": ts,
            "tool_call_id": message.tool_call_id,
            "name": getattr(message, "name", ""),
            "content": message.content if isinstance(message.content, str) else str(message.content),
        }
    # Fallback for other message types
    return {"type": "msg", "role": "unknown", "ts": ts, "content": str(message.content)}


def jsonl_to_msg(d: dict):
    """Convert a JSONL dict back to a LangChain BaseMessage."""
    role = d.get("role", "")
    content = d.get("content", "")
    if role == "user":
        return HumanMessage(content=content)
    if role == "assistant":
        tool_calls = d.get("tool_calls", [])
        if tool_calls:
            return AIMessage(content=content, tool_calls=tool_calls)
        return AIMessage(content=content)
    if role == "tool":
        return ToolMessage(
            content=content,
            tool_call_id=d.get("tool_call_id", ""),
            name=d.get("name", ""),
        )
    return HumanMessage(content=content)
