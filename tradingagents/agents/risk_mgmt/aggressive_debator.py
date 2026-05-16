from tradingagents.agents.utils.agent_utils import (
    get_asset_prompt_context,
    get_language_instruction,
)


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        investment_plan = state.get("investment_plan", "")
        asset_context = get_asset_prompt_context()

        prompt = f"""You are the Aggressive Risk Analyst in the portfolio risk management debate. The research thesis has been established by the Research Manager and the Trader has operationalized it into a specific proposal. Your role is not to re-evaluate whether the trade is right — it's to challenge risk parameters that are unnecessarily restrictive and ensure the team captures the full opportunity within the investment thesis.

## Asset Lens
{asset_context}

## The Proposal Under Review
{trader_decision}

## Research Context
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Your Mission

Argue for the risk parameters that capture maximum upside within the established thesis. Each round, focus on specific parameters your opponents proposed that are too conservative:

- If the conservative analyst proposed a tight stop: argue why that specific level is too conservative, citing the technical structure — where is the actual thesis invalidation point?
- If the neutral analyst proposed reduced sizing: argue why the current volatility regime and conviction level justify fuller exposure
- Quantify the opportunity cost: what return is left on the table if the overly cautious parameters are adopted?
- Propose your own concrete alternative with specific numbers — position size percentage, stop-loss level, and staged-sizing pacing (number of tranches and deployment conditions, not new exit target prices). Do not redefine the entry price, entry timing conditions, or price targets — those are the Trader's parameters

The argument should be grounded in the analyst reports. Don't argue that risks don't exist — argue that the risk/reward ratio justifies the exposure level you're advocating.

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
Conservative analyst's last argument: {current_conservative_response if current_conservative_response.strip() else "No argument yet — present your opening case for the most aggressive risk parameters defensible under the established thesis."}
Neutral analyst's last argument: {current_neutral_response if current_neutral_response.strip() else "No argument yet."}""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
