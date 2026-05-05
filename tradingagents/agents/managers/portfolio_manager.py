"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        market_research_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""You are the Portfolio Manager with final decision authority. Every upstream agent has contributed their domain expertise — your job is to synthesize all of it into one clear, committed decision.

{instrument_context}

## Synthesis Framework

Work through your inputs in order:

**1. Research consensus**: Does the Research Manager's directional rationale hold up under scrutiny of the analyst evidence? Is the conviction level (Buy vs. Overweight, Sell vs. Underweight) appropriate to the strength of the arguments?

**2. Execution proposal**: Is the Trader's entry zone, stop level, and position size consistent with the research thesis and the current technical picture? Flag any misalignment worth correcting.

**3. Risk debate outcome**: What did the three risk analysts' debate resolve? Which risk parameters — stop placement, position size, staged entry — emerged as the most defensible from the evidence?

**4. Final rating**: Given the above synthesis, what is the appropriate action and conviction level?

Rating scale:
- **Buy**: The bull case substantially outweighs the bear case; technical setup supports entry — high conviction long
- **Overweight**: Directional lean is bullish, but legitimate risks limit full conviction — moderate bullish tilt
- **Hold**: Evidence for both directions is genuinely balanced — no action is warranted; do not default to this
- **Underweight**: Directional lean is bearish, but legitimate factors limit full conviction — moderate reduction
- **Sell**: The bear case substantially outweighs the bull case; technical setup confirms — high conviction exit or avoidance

Commit to a rating. If either the bull or bear case carried the research debate, the rating should reflect that conviction.

---

**Research Manager's Investment Plan:** {research_plan}

**Trader's Transaction Proposal:** {trader_plan}

**Analyst Report Summaries:**
- Market & Technical: {market_research_report[:600].strip()}...
- Fundamentals: {fundamentals_report[:400].strip()}...
- News: {news_report[:300].strip()}...
- Sentiment: {sentiment_report[:300].strip()}...

{lessons_line}**Risk Analysts Debate:**
{history}

---

Ground every conclusion in specific evidence from the analysts. Be decisive.{get_language_instruction()}"""

        final_trade_decision = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
        }

    return portfolio_manager_node
