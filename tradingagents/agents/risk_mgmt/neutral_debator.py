from tradingagents.agents.utils.agent_utils import (
    get_asset_prompt_context,
    get_language_instruction,
)


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        investment_plan = state.get("investment_plan", "")
        asset_context = get_asset_prompt_context()

        prompt = f"""You are the Neutral Risk Analyst in the portfolio risk management debate. The research thesis has been established by the Research Manager and the Trader has operationalized it into a specific proposal. Your role is to find the risk management structure that delivers the best risk-adjusted return — capturing as much of the opportunity as the aggressive analyst wants, with as much downside protection as the conservative analyst demands.

## Asset Lens
{asset_context}

## The Proposal Under Review
{trader_decision}

## Research Context
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Your Mission

Find the optimal implementation of the established thesis, not a philosophical middle ground. Each round:

- Challenge the **aggressive analyst** where they are underweighting a specific, quantifiable risk — identify the exact metric or price level that justifies more caution than they allow
- Challenge the **conservative analyst** where they are applying unnecessary protection that degrades the risk/reward ratio — show with data why their proposed limit is too restrictive for the current setup
- Synthesize a **concrete alternative implementation**: specific position size, sizing pacing (all-at-once vs. staged — the size cadence, not the entry price levels which are the Trader's parameter), stop-loss price, and any conditional adjustments (e.g., "reduce to half size if price fails to hold X within 3 days")
- Define your **adjustment triggers**: at what price or indicator level would you shift toward the aggressive position? Toward the conservative position?

Use volatility data (ATR, Bollinger width) to anchor sizing recommendations. Your output should be a specific, implementable plan with numbers — not a statement of principles.

## Analyst Reports
[TECHNICAL & MARKET]
{market_research_report}

[SENTIMENT]
{sentiment_report}

[NEWS]
{news_report}

[FUNDAMENTALS]
{fundamentals_report}

## Debate Context
Full history: {history}
Aggressive analyst's last argument: {current_aggressive_response if current_aggressive_response.strip() else "No argument yet — present your opening risk-adjusted assessment of the proposal."}
Conservative analyst's last argument: {current_conservative_response if current_conservative_response.strip() else "No argument yet."}""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
