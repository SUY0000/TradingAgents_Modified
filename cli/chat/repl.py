"""Interactive REPL for the chat replay sub-command."""
from __future__ import annotations

import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from cli.chat.session import append_message, load_messages, msg_to_jsonl, truncate_last_message

console = Console()


def _format_args_summary(args: dict, max_len: int = 80) -> str:
    text = ", ".join(f"{k}={repr(v)}" for k, v in (args or {}).items())
    return text[:max_len] + "…" if len(text) > max_len else text


_MAX_HISTORY_LINES = 20


def _print_history(messages: list) -> None:
    """Print a compact summary of loaded messages so the user can see context."""
    if not messages:
        return
    total = len(messages)
    shown = messages[-_MAX_HISTORY_LINES:] if total > _MAX_HISTORY_LINES else messages
    if total > _MAX_HISTORY_LINES:
        console.print(f"[dim]… {total - _MAX_HISTORY_LINES} earlier messages omitted[/dim]")
    for m in shown:
        if isinstance(m, HumanMessage):
            text = (m.content or "").strip().split("\n")[0][:120]
            console.print(f"  [bold cyan]>[/bold cyan] {text}")
        elif isinstance(m, AIMessage):
            content = m.content if isinstance(m.content, str) else ""
            text = content.strip().split("\n")[0][:120]
            console.print(f"  [bold green]●[/bold green] {text}")
            if m.tool_calls:
                for tc in m.tool_calls:
                    args_summary = _format_args_summary(tc.get("args", {}))
                    console.print(f"    [cyan]⏺ {tc['name']}({args_summary})[/cyan]")
        elif isinstance(m, ToolMessage):
            content = m.content or ""
            preview = content[:80] + ("…" if len(content) > 80 else "")
            console.print(f"    [dim]└─ {len(content)} chars: {preview}[/dim]")
    console.print(Rule(style="dim"))


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


def _handle_slash(
    user_input: str,
    config: dict,
    rebuild_fn,
    app_graph_ref: list,
    manifest: dict,
    session_path_ref: list,
    state_messages: list,
    report_dir: Path,
) -> str:
    """Dispatch a slash command.

    Returns one of: "continue", "break", "unknown".
    """
    parts = user_input.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/help":
        t = Table(show_header=False, show_lines=False, box=None, padding=(0, 2))
        t.add_column("cmd", style="bold cyan", no_wrap=True)
        t.add_column("desc")
        t.add_row("/help", "Show this help.")
        t.add_row("/tools", "List currently bound chat tools.")
        t.add_row("/lang [LANG]", "Switch output language (e.g. /lang zh, /lang en).")
        t.add_row("/model", "Re-select chat LLM provider, model, and effort.")
        t.add_row("/sessions", "Switch to another session in this report.")
        t.add_row("/new [title]", "Create a new session (optional title).")
        t.add_row("/title <name>", "Rename the current session.")
        t.add_row("/delete", "Delete the current session.")
        t.add_row("/exit, /quit", "Exit the chat.")
        console.print(t)
        return "continue"

    if cmd == "/lang":
        if rebuild_fn is None:
            console.print("[yellow]Hot-swap unavailable in this session.[/yellow]")
            return "continue"
        if arg:
            lang = arg
        else:
            try:
                import questionary
                lang = questionary.text("Output language (e.g. en, zh, Japanese):").ask()
                if not lang:
                    console.print("[dim]Cancelled.[/dim]")
                    return "continue"
                lang = lang.strip()
            except ImportError:
                console.print("[yellow]questionary not installed; pass language as argument: /lang zh[/yellow]")
                return "continue"
        config["output_language"] = lang
        try:
            app_graph_ref[0] = rebuild_fn(config)
            console.print(
                f"[green]Language switched to {lang}. "
                f"The next response will use the new language.[/green]"
            )
        except Exception as exc:
            console.print(f"[red]Failed to rebuild graph: {exc}[/red]")
        return "continue"

    if cmd == "/model":
        if rebuild_fn is None:
            console.print("[yellow]Hot-swap unavailable in this session.[/yellow]")
            return "continue"
        from cli.chat.llm_setup import setup_chat_llm_interactive
        setup_chat_llm_interactive(config, force_interactive=True)
        try:
            app_graph_ref[0] = rebuild_fn(config)
            new_model = config.get("chat_llm_model", "?")
            new_provider = config.get("chat_llm_provider", "?")
            console.print(
                f"[green]Model switched to {new_provider}/{new_model}.[/green]"
            )
        except Exception as exc:
            console.print(f"[red]Failed to rebuild graph: {exc}[/red]")
        return "continue"

    if cmd == "/tools":
        from cli.chat.agent import get_chat_tools
        tools = get_chat_tools(config)
        t = Table(title=f"Available tools ({len(tools)})", show_lines=False)
        t.add_column("Name", style="cyan", no_wrap=True)
        t.add_column("Description")
        for tool in tools:
            desc = (tool.description or "").strip().split("\n")[0][:120]
            t.add_row(tool.name, desc)
        console.print(t)
        return "continue"

    if cmd == "/sessions":
        from cli.chat.session import list_sessions
        sessions = list_sessions(report_dir)
        if not sessions:
            console.print("[yellow]No sessions found.[/yellow]")
            return "continue"
        current = session_path_ref[0]
        try:
            import questionary
        except ImportError:
            console.print("[yellow]questionary not installed.[/yellow]")
            return "continue"
        choices = []
        mapping = {}
        for s in sessions:
            marker = "★ " if s["path"] == current else "  "
            label = f"{marker}{s['title']:<30}  ({s['n_msgs']} msgs)  {s['created_at']}"
            choices.append(label)
            mapping[label] = s["path"]
        selected = questionary.select("Switch to session:", choices=choices).ask()
        if selected is None:
            return "continue"
        new_path = mapping[selected]
        if new_path == current:
            return "continue"
        session_path_ref[0] = new_path
        state_messages.clear()
        state_messages.extend(load_messages(new_path))
        console.print(f"[green]Switched to session:[/green] {new_path.name} ({len(state_messages)} msgs loaded)")
        _print_header(manifest, session_path_ref[0], config, len(state_messages))
        _print_history(state_messages)
        return "continue"

    if cmd == "/new":
        from cli.chat.session import make_session_path, ensure_session
        title = arg or "untitled"
        new_path = make_session_path(report_dir, title)
        ensure_session(new_path, manifest, title=title)
        session_path_ref[0] = new_path
        state_messages.clear()
        console.print(f"[green]New session created:[/green] {new_path.name}")
        return "continue"

    if cmd == "/title":
        if not arg:
            console.print("[yellow]Usage: /title <new-name>[/yellow]")
            return "continue"
        from cli.chat.session import rename_session_file, rewrite_header
        new_path = rename_session_file(session_path_ref[0], arg)
        rewrite_header(new_path, title=arg)
        session_path_ref[0] = new_path
        console.print(f"[green]Session renamed to:[/green] {new_path.name}")
        return "continue"

    if cmd == "/delete":
        try:
            import questionary
        except ImportError:
            console.print("[yellow]questionary not installed.[/yellow]")
            return "continue"
        from cli.chat.session import (
            delete_session, list_sessions, latest_session_path,
            make_session_path, ensure_session,
        )
        confirmed = questionary.confirm(
            f"Delete session {session_path_ref[0].name}? This cannot be undone.",
            default=False,
        ).ask()
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            return "continue"
        delete_session(session_path_ref[0])
        remaining = list_sessions(report_dir)
        if remaining:
            new_path = remaining[0]["path"]
            state_messages.clear()
            state_messages.extend(load_messages(new_path))
            console.print(f"[green]Switched to:[/green] {new_path.name}")
        else:
            new_path = make_session_path(report_dir, "untitled")
            ensure_session(new_path, manifest, title="untitled")
            state_messages.clear()
            console.print(f"[green]All sessions deleted. Created:[/green] {new_path.name}")
        session_path_ref[0] = new_path
        _print_header(manifest, session_path_ref[0], config, len(state_messages))
        _print_history(state_messages)
        return "continue"

    return "unknown"


def run_repl(
    app_graph,
    session_path: Path,
    manifest: dict,
    config: dict,
    rebuild_fn=None,
    report_dir: Path | None = None,
) -> None:
    """Main REPL loop."""
    try:
        from prompt_toolkit import PromptSession
    except ImportError:
        console.print("[red]prompt_toolkit not installed. Run: pip install prompt_toolkit[/red]")
        return

    state_messages = load_messages(session_path)
    session_path_ref = [session_path]
    _print_header(manifest, session_path_ref[0], config, len(state_messages))

    if state_messages:
        console.print(f"[dim]已加载 {len(state_messages)} 条历史消息[/dim]")
        _print_history(state_messages)
    else:
        console.print("[dim]新 session 已创建。输入问题开始复盘讨论。[/dim]")
        console.print(Rule(style="dim"))

    app_graph_ref = [app_graph]
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

        if user_input_stripped.startswith("/"):
            action = _handle_slash(
                user_input_stripped,
                config,
                rebuild_fn,
                app_graph_ref,
                manifest,
                session_path_ref,
                state_messages,
                report_dir,
            )
            if action == "break":
                break
            if action == "unknown":
                console.print("[yellow]Unknown command. Type /help to see available commands.[/yellow]")
            continue

        # Append user message
        user_msg = HumanMessage(content=user_input)
        state_messages.append(user_msg)
        append_message(session_path_ref[0], msg_to_jsonl(user_msg))

        # Invoke agent
        console.print()
        try:
            new_msgs = stream_invoke(app_graph_ref[0], state_messages, config)
        except KeyboardInterrupt:
            console.print("[yellow]\n已中断[/yellow]")
            # Remove the user message we just appended since we got no response
            state_messages.pop()
            truncate_last_message(session_path_ref[0])
            continue
        except Exception as exc:
            console.print(f"[red]响应失败: {exc}[/red]")
            state_messages.pop()
            truncate_last_message(session_path_ref[0])
            continue

        # Persist new messages
        for m in new_msgs:
            state_messages.append(m)
            if isinstance(m, AIMessage):
                append_message(session_path_ref[0], msg_to_jsonl(m, model=config.get("chat_llm_model", ""), effort=config.get("chat_llm_effort", "")))
            else:
                append_message(session_path_ref[0], msg_to_jsonl(m))

        console.print()

    console.print("[dim]再见。[/dim]")
