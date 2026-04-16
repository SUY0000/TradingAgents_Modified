"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

import functools

from langchain_core.messages import AIMessage

from tradingagents.agents.schemas import TraderProposal, render_trader_proposal
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
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
                "content": f"""You are a Trader. Your role is to independently evaluate the research team's investment plan, verify its assumptions against current market data, and translate it into a concrete, executable trading recommendation.

**Rating Scale** (use exactly one):
- **BUY**: Enter or meaningfully add — high-conviction long
- **OVERWEIGHT**: Gradually increase exposure — moderate bullish tilt
- **HOLD**: Maintain current position — no action needed
- **UNDERWEIGHT**: Reduce exposure — moderate bearish lean
- **SELL**: Exit or avoid — high-conviction short/flat

**Required Output Structure:**
1. **Rating**: One of BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
2. **Execution Parameters**:
   - Entry zone: price range or condition for entry
   - Stop-loss: level that invalidates the thesis
   - Target: primary price target and time horizon
   - Position sizing: relative to normal position (e.g., full / half / quarter)
3. **Rationale**: Key factors supporting this rating, noting where you agree or diverge from the investment plan
4. **Lessons Applied**: How past decision reflections influenced this recommendation

Always end with: FINAL TRANSACTION PROPOSAL: **[RATING]**

{lessons_line}{get_language_instruction()}""",
            },
            {
                "role": "user",
                "content": (
                    f"Based on a comprehensive analysis by a team of analysts, here is an investment "
                    f"plan tailored for {company_name}. {instrument_context} This plan incorporates "
                    f"insights from current technical market trends, macroeconomic indicators, and "
                    f"social media sentiment. Use this plan as a foundation for evaluating your next "
                    f"trading decision.\n\nProposed Investment Plan: {investment_plan}\n\n"
                    f"Technical Market Summary (for entry parameter calibration):\n"
                    f"{market_research_report[:500].strip()}...\n\n"
                    f"Leverage these insights to make an informed and strategic decision."
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
