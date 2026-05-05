from tradingagents.agents.utils.agent_utils import get_language_instruction


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        investment_plan = state.get("investment_plan", "")

        prompt = f"""You are the Conservative Risk Analyst in the portfolio risk management debate. The research thesis has been established by the Research Manager and the Trader has operationalized it into a specific proposal. Your role is not to block the trade — it's to ensure that the downside parameters in the proposal adequately protect the portfolio if the thesis is wrong.

## The Proposal Under Review
{trader_decision}

## Research Context
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Your Mission

Argue for the risk parameters that properly bound the downside within the established thesis. Each round, focus on specific parameters that are inadequately protective:

- If the stop-loss is too wide: identify the specific technical level that should serve as the stop, and explain what a break of that level means for the thesis
- If the position size is too large: quantify the maximum drawdown exposure and explain why it exceeds acceptable portfolio risk given current volatility
- Propose concrete protective alternatives with specific numbers — exact stop level in price terms, maximum position size as a percentage of portfolio, or staged entry conditions that limit initial risk exposure
- Quantify the downside scenario: if the thesis is wrong and the position hits the stop, what is the percentage impact on the portfolio, and is that within acceptable limits?

Ground every claim in the analyst reports — specific support levels, volatility data (ATR, Bollinger width), or identified risk event timing. Don't say "risks exist" — say exactly which levels, metrics, or events make the current plan inadequately protected.

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
Aggressive analyst's last argument: {current_aggressive_response if current_aggressive_response.strip() else "No argument yet — present your opening assessment of the risk parameters."}
Neutral analyst's last argument: {current_neutral_response if current_neutral_response.strip() else "No argument yet."}""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
