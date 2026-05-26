"""Chat session persistence — JSONL read/write for multi-turn chat history."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def default_session_path(report_dir: Path) -> Path:
    return Path(report_dir) / "sessions" / "default.jsonl"


def ensure_session(session_path: Path, manifest: dict) -> None:
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
        "title": "default",
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

    # Integrity check: if the last AIMessage has tool_calls but no following ToolMessages,
    # discard that AIMessage and the user message that preceded it.
    messages = [jsonl_to_msg(d) for d in raw_msgs]
    messages = _repair_incomplete_tool_calls(messages)
    return messages


def _repair_incomplete_tool_calls(messages: list) -> list:
    """Drop trailing AIMessage+preceding user message if tool_calls are unresolved."""
    if not messages:
        return messages
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        # Find the user message that immediately precedes this AIMessage
        tail = messages[:-1]
        while tail and isinstance(tail[-1], (AIMessage, ToolMessage)):
            tail = tail[:-1]
        if tail and isinstance(tail[-1], HumanMessage):
            tail = tail[:-1]
        return tail
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
