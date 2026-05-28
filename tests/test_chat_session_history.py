from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cli.chat.session import ensure_session, load_messages, msg_to_jsonl, append_message
from cli.chat.repl import _history_rows


def test_session_history_shows_all_messages_after_tool_call(tmp_path: Path):
    session_path = tmp_path / "sessions" / "default.jsonl"
    ensure_session(session_path, {"ticker": "BTC/USDT", "analysis_date": "2026-05-28"})

    user_msg = HumanMessage(content="现在怎么看？")
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call-1", "name": "get_okx_ticker_snapshot", "args": {"ticker": "BTC/USDT"}}],
    )
    tool_msg = ToolMessage(content="BTC is up", tool_call_id="call-1", name="get_okx_ticker_snapshot")
    final_msg = AIMessage(content=[{"type": "text", "text": "最终回复：仍需谨慎。"}])

    for msg in (user_msg, tool_call_msg, tool_msg, final_msg):
        append_message(session_path, msg_to_jsonl(msg))

    messages = load_messages(session_path)
    assert len(messages) == 4
    assert _history_rows(messages) == [
        ("user", "现在怎么看？"),
        ("assistant", ""),
        ("tool_call", "get_okx_ticker_snapshot(ticker='BTC/USDT')"),
        ("tool", "9 chars: BTC is up"),
        ("assistant", "最终回复：仍需谨慎。"),
    ]


def test_session_repair_only_drops_trailing_incomplete_tool_turn(tmp_path: Path):
    session_path = tmp_path / "sessions" / "default.jsonl"
    ensure_session(session_path, {"ticker": "AAPL", "analysis_date": "2026-05-28"})

    completed_user = HumanMessage(content="第一问")
    completed_tool_call = AIMessage(
        content="",
        tool_calls=[{"id": "call-1", "name": "tool", "args": {}}],
    )
    completed_tool = ToolMessage(content="result", tool_call_id="call-1", name="tool")
    completed_final = AIMessage(content="第一答")
    interrupted_user = HumanMessage(content="第二问")
    interrupted_tool_call = AIMessage(
        content="",
        tool_calls=[{"id": "call-2", "name": "tool", "args": {}}],
    )

    for msg in (
        completed_user,
        completed_tool_call,
        completed_tool,
        completed_final,
        interrupted_user,
        interrupted_tool_call,
    ):
        append_message(session_path, msg_to_jsonl(msg))

    messages = load_messages(session_path)
    assert _history_rows(messages) == [
        ("user", "第一问"),
        ("assistant", ""),
        ("tool_call", "tool()"),
        ("tool", "6 chars: result"),
        ("assistant", "第一答"),
    ]
