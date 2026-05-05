"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.schemas import ResearchPlan, render_research_plan
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_research_manager(llm):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")

        investment_debate_state = state["investment_debate_state"]

        prompt = f"""You are the Research Manager concluding this investment debate. Your output — the investment plan — becomes the Trader's primary research brief and the Portfolio Manager's research consensus. The quality of your synthesis determines the quality of every decision downstream.

{instrument_context}

## Your Task

Assess which side of the debate built the stronger case. A strong case has three properties: it is anchored in specific data from the analyst reports, it directly addresses the opposing arguments rather than talking past them, and it holds together internally without relying on assumptions the reports don't support.

Apply this standard rigorously. Acknowledge when both sides made valid points, but commit to a directional view when the weight of evidence supports one. The rating maps to conviction level:

- **Buy**: The bull case substantially outweighed the bear case. High conviction in the upside direction.
- **Overweight**: The argument leans bullish, but the bear side raised legitimate concerns worth managing. Moderate conviction.
- **Hold**: The evidence on both sides is genuinely balanced — risk/reward is symmetric. Use this only when it's actually true, not as a default.
- **Underweight**: The argument leans bearish, but the bull side raised legitimate factors worth respecting. Moderate conviction.
- **Sell**: The bear case substantially outweighed the bull case. High conviction in the downside direction.

In the **strategic actions** field, give the Trader a research brief — not execution parameters: which technical levels are pivotal to the thesis (validation triggers and invalidation triggers), what catalysts or conditions would force re-evaluation, and what conviction level the Trader should size against. The Trader will translate this into specific entry, stop, and sizing values.

## Debate History
{history}{get_language_instruction()}"""

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
