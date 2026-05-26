"""Interactive REPL for the chat replay sub-command."""
from __future__ import annotations

import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from cli.chat.session import append_message, load_messages, msg_to_jsonl, truncate_last_message

console = Console()


def _format_args_summary(args: dict, max_len: int = 80) -> str:
    text = ", ".join(f"{k}={repr(v)}" for k, v in (args or {}).items())
    return text[:max_len] + "…" if len(text) > max_len else text


def _count_session_tokens(messages: list) -> int:
    """Rough token estimate: 1 token ≈ 4 chars."""
    total = sum(len(str(getattr(m, "content", ""))) for m in messages)
    return total // 4


def stream_invoke(app_graph, state_messages: list, config: dict) -> list:
    """Stream the graph and collect new messages. Returns list of new messages."""
    new_messages = []

    try:
        for chunk in app_graph.stream(
            {"messages": state_messages}, stream_mode="updates"
        ):
            # chunk is {node_name: {"messages": [...]}}
            for node_name, node_output in chunk.items():
                msgs_out = node_output.get("messages", [])
                for msg in msgs_out:
                    if isinstance(msg, AIMessage):
                        content = msg.content if isinstance(msg.content, str) else ""
                        if content:
                            console.print(Markdown(content))
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                args_summary = _format_args_summary(tc.get("args", {}))
                                console.print(f"  [cyan]⏺ {tc['name']}({args_summary})[/cyan]")
                        new_messages.append(msg)

                    elif isinstance(msg, ToolMessage):
                        content = msg.content or ""
                        preview = content[:80] + "…" if len(content) > 80 else content
                        console.print(f"  [dim]└─ {len(content)} chars: {preview}[/dim]")
                        new_messages.append(msg)

    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if new_messages:
            raise
        console.print(f"[yellow]stream failed, falling back to invoke: {exc}[/yellow]")
        result = app_graph.invoke({"messages": state_messages})
        for msg in result.get("messages", [])[len(state_messages):]:
            if isinstance(msg, AIMessage):
                content = msg.content if isinstance(msg.content, str) else ""
                if content:
                    console.print(Markdown(content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        args_summary = _format_args_summary(tc.get("args", {}))
                        console.print(f"  [cyan]⏺ {tc['name']}({args_summary})[/cyan]")
                new_messages.append(msg)
            elif isinstance(msg, ToolMessage):
                content = msg.content or ""
                preview = content[:80] + "…" if len(content) > 80 else content
                console.print(f"  [dim]└─ {len(content)} chars: {preview}[/dim]")
                new_messages.append(msg)

    return new_messages


def _print_header(manifest: dict, session_path: Path, config: dict, n_messages: int) -> None:
    ticker = manifest.get("ticker", "?")
    analysis_date = manifest.get("analysis_date", "?")
    try:
        import datetime
        days_since = (datetime.date.today() - datetime.date.fromisoformat(analysis_date)).days
        age_str = f"{days_since} 天前"
    except Exception:
        age_str = "?"

    model = config.get("chat_llm_model", "?")
    effort = config.get("chat_llm_effort", "?")
    lang = manifest.get("output_language", "English")
    session_name = session_path.stem

    console.print(
        Panel(
            f"[bold]Report:[/bold]  {ticker} · {analysis_date} ({age_str})\n"
            f"[bold]Session:[/bold] {session_name} · {n_messages} messages\n"
            f"[bold]Model:[/bold]   {model} · effort={effort} · lang={lang}",
            title="[bold cyan]TradingAgents Chat[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )


def run_repl(
    app_graph,
    session_path: Path,
    manifest: dict,
    config: dict,
) -> None:
    """Main REPL loop."""
    try:
        from prompt_toolkit import PromptSession
    except ImportError:
        console.print("[red]prompt_toolkit not installed. Run: pip install prompt_toolkit[/red]")
        return

    state_messages = load_messages(session_path)
    _print_header(manifest, session_path, config, len(state_messages))

    if state_messages:
        console.print(f"[dim]已加载 {len(state_messages)} 条历史消息[/dim]")
    else:
        console.print("[dim]新 session 已创建。输入问题开始复盘讨论。[/dim]")
    console.print(Rule(style="dim"))

    model = config.get("chat_llm_model", "")
    effort = config.get("chat_llm_effort", "")
    pt_session = PromptSession()
    first_interrupt_at = None

    while True:
        # Status line
        tk_estimate = _count_session_tokens(state_messages)
        console.print(
            f"[dim][当前 session: {len(state_messages)} msgs · ~{tk_estimate} tokens][/dim]"
        )

        try:
            user_input = pt_session.prompt("> ")
        except KeyboardInterrupt:
            if first_interrupt_at and time.time() - first_interrupt_at < 2:
                break
            first_interrupt_at = time.time()
            console.print("[dim]再次 Ctrl-C 退出[/dim]")
            continue
        except EOFError:
            break

        user_input_stripped = user_input.strip()
        if not user_input_stripped:
            continue
        if user_input_stripped.lower() in {"/exit", "/quit", "exit", "quit"}:
            break

        # Append user message
        user_msg = HumanMessage(content=user_input)
        state_messages.append(user_msg)
        append_message(session_path, msg_to_jsonl(user_msg))

        # Invoke agent
        console.print()
        try:
            new_msgs = stream_invoke(app_graph, state_messages, config)
        except KeyboardInterrupt:
            console.print("[yellow]\n已中断[/yellow]")
            # Remove the user message we just appended since we got no response
            state_messages.pop()
            truncate_last_message(session_path)
            continue
        except Exception as exc:
            console.print(f"[red]响应失败: {exc}[/red]")
            state_messages.pop()
            truncate_last_message(session_path)
            continue

        # Persist new messages
        for m in new_msgs:
            state_messages.append(m)
            if isinstance(m, AIMessage):
                append_message(session_path, msg_to_jsonl(m, model=model, effort=effort))
            else:
                append_message(session_path, msg_to_jsonl(m))

        console.print()

    console.print("[dim]再见。[/dim]")
