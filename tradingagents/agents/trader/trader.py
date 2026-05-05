"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

import functools

from langchain_core.messages import AIMessage

from tradingagents.agents.schemas import TraderProposal, render_trader_proposal
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_trader(llm):
    structured_llm = bind_structured(llm, TraderProposal, "Trader")

    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state.get("market_report", "")

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        messages = [
            {
                "role": "system",
                "content": f"""You are the Trader responsible for operationalizing the research team's investment plan into a precise, executable transaction proposal. The Research Manager has committed to a directional view after evaluating the full investment debate; your job is to translate that view into exact execution parameters — not to re-litigate the research thesis.

Your value is at the execution layer. For each parameter, apply your professional judgment:

**Entry precision**: Given the current price action in the market report, where is the optimal entry point? Is the current price already at a favorable level, or should you wait for a specific support test, breakout confirmation, or pullback setup?

**Risk definition**: Place the stop-loss at the level that would technically invalidate the research thesis — a specific price where the setup breaks, not a mechanical percentage below entry. This is the most important parameter you set.

**Target specification**: What is the primary price target based on the technical structure, and what is a realistic holding period? If there are natural resistance levels that serve as interim targets, note them.

**Position sizing**: Calibrate to the conviction level in the research plan and the current volatility regime. Full size for high conviction with low volatility; reduced size for moderate conviction or elevated volatility.

If a meaningful conflict exists between the research plan's direction and a clear technical signal in the market data, note it briefly — but default to executing the research plan unless the conflict is severe enough to warrant a different action.

{lessons_line}Always end with: FINAL TRANSACTION PROPOSAL: **[BUY/HOLD/SELL]**{get_language_instruction()}""",
            },
            {
                "role": "user",
                "content": (
                    f"Operationalize the following investment plan for {company_name}. "
                    f"{instrument_context}\n\n"
                    f"Research Manager's Investment Plan:\n{investment_plan}\n\n"
                    f"Technical Market Data (for entry and stop calibration):\n"
                    f"{market_research_report[:600].strip()}...\n\n"
                    f"Translate this plan into your transaction proposal with specific entry zone, "
                    f"stop-loss level, price target, and position sizing."
                ),
            },
        ]

        trader_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            messages,
            render_trader_proposal,
            "Trader",
        )

        return {
            "messages": [AIMessage(content=trader_plan)],
            "trader_investment_plan": trader_plan,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
