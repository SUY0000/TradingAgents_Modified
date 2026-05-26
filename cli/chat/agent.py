"""Chat LLM construction and LangGraph sub-graph assembly."""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

from tradingagents.agents.utils.agent_utils import Toolkit, get_all_tools_for_asset_type
from tradingagents.llm_clients import create_llm_client
from cli.chat.prompt import build_system_prompt


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]


def _build_chat_kwargs(config: dict) -> dict:
    """Build provider-specific kwargs for the chat LLM.

    Mirrors trading_graph._get_provider_kwargs() but reads chat_llm_* keys
    instead of quick_/deep_ keys.
    """
    kwargs = {}
    provider = config.get("chat_llm_provider", "openai").lower()
    effort = config.get("chat_llm_effort", "default")
    api_key = config.get("llm_api_key")

    if not api_key:
        from tradingagents.llm_clients.api_key_env import get_api_key_env
        env_var = get_api_key_env(provider)
        if env_var:
            api_key = os.environ.get(env_var)

    if provider == "custom_openai":
        api_key = os.environ.get("CUSTOM_OPENAI_API_KEY") or api_key
    elif provider == "custom_anthropic":
        api_key = os.environ.get("CUSTOM_ANTHROPIC_API_KEY") or api_key

    if api_key:
        kwargs["api_key"] = api_key

    if provider == "google":
        if effort and effort != "default":
            kwargs["thinking_level"] = effort
    elif provider in ("openai", "custom_openai"):
        if effort and effort != "default":
            kwargs["reasoning_effort"] = effort
    elif provider in ("anthropic", "custom_anthropic"):
        if effort and effort != "default":
            kwargs["effort"] = effort
    elif provider == "deepseek":
        if effort and effort != "default":
            kwargs["reasoning_effort"] = effort

    # Custom provider headers
    if provider == "custom_openai":
        try:
            from tradingagents.llm_clients.headers_env import load_custom_headers
            headers = load_custom_headers("CUSTOM_OPENAI_HEADERS")
            if headers:
                kwargs["default_headers"] = headers
        except ImportError:
            pass
    elif provider == "custom_anthropic":
        try:
            from tradingagents.llm_clients.headers_env import load_custom_headers
            headers = load_custom_headers("CUSTOM_ANTHROPIC_HEADERS")
            if headers:
                kwargs["default_headers"] = headers
        except ImportError:
            pass

    return kwargs


def build_chat_llm(config: dict):
    """Construct the chat LLM from config['chat_llm_*'] triple."""
    provider = config.get("chat_llm_provider", "openai")
    model = config.get("chat_llm_model", "gpt-4o")
    provider_lower = provider.lower()
    base_url = config.get("backend_url")
    if provider_lower == "custom_openai":
        base_url = os.environ.get("CUSTOM_OPENAI_BASE_URL") or base_url
    elif provider_lower == "custom_anthropic":
        base_url = os.environ.get("CUSTOM_ANTHROPIC_BASE_URL") or base_url
    kwargs = _build_chat_kwargs(config)
    client = create_llm_client(provider=provider, model=model, base_url=base_url, **kwargs)
    return client.get_llm()


def load_past_context(company_of_interest: str, config: dict) -> str:
    """Load past trading memory context for the given company."""
    try:
        from tradingagents.agents.utils.memory import TradingMemoryLog
        memory_log = TradingMemoryLog(config)
        return memory_log.get_past_context(company_of_interest)
    except Exception:
        return ""


def build_chat_app(
    manifest: dict,
    reports_bundle: dict,
    past_context: str,
    llm,
    toolkit: Toolkit,
    config: dict,
    today: datetime.date,
):
    """Build and compile the LangGraph chat sub-graph."""
    tools = get_all_tools_for_asset_type(toolkit, config)
    llm_with_tools = llm.bind_tools(tools)
    tool_names_csv = ", ".join(t.name for t in tools)
    system_prompt = build_system_prompt(
        manifest, reports_bundle, past_context, today, tool_names_csv,
        output_language=config.get("output_language"),
    )

    def chat_node(state: ChatState):
        msgs = [SystemMessage(content=system_prompt)] + state["messages"]
        return {"messages": [llm_with_tools.invoke(msgs)]}

    def route(state: ChatState):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(ChatState)
    graph.add_node("chat", chat_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "chat")
    graph.add_conditional_edges("chat", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "chat")
    return graph.compile()


def rebuild_app_graph(
    manifest: dict,
    reports_bundle: dict,
    past_context: str,
    config: dict,
    today: datetime.date,
):
    """Rebuild the chat app graph after /model or /lang.

    Re-instantiates the LLM (picks up updated chat_llm_* and output_language
    from config) and re-binds tools. REPL keeps its own message history, so
    nothing is lost by reconstructing the compiled graph.
    """
    llm = build_chat_llm(config)
    toolkit = Toolkit(config)
    return build_chat_app(manifest, reports_bundle, past_context, llm, toolkit, config, today)
