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

        prompt = f"""You are the Conservative Risk Analyst in a risk management debate. Your role is to quantify the downside risks in the trader's decision and advocate for specific protective measures — not to reject the trade outright, but to ensure risk is properly bounded.

## Trader's Decision Under Review
{trader_decision}

## Research Manager's Investment Plan (context)
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Debate Rules (follow strictly every round)
1. **Directly rebut** the aggressive and neutral analysts' last arguments — address their specific claims with data, not generic caution
2. **Cite specific evidence** from the analyst reports — name the source for every assertion
3. **Do not repeat** arguments already in the debate history — advance new risk angles each round
4. **Quantify the risk**: state specific downside levels, max acceptable drawdown, or exposure limits — avoid vague warnings

## Your Analysis Framework
Build your argument across the most relevant dimensions:
- **Downside Risk**: key support levels that if broken signal trend failure; estimated max drawdown scenario
- **Risk Exposure Limits**: recommend maximum position size as % of portfolio given current volatility
- **Macro & Liquidity Headwinds**: adverse conditions that increase the probability of the downside scenario
- **Protective Measures**: specific stop-loss levels, hedging approaches, or staged entry to reduce risk

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
- Full debate history: {history}
- Aggressive analyst's last argument: {current_aggressive_response if current_aggressive_response.strip() else "No argument yet — present your opening case."}
- Neutral analyst's last argument: {current_neutral_response if current_neutral_response.strip() else "No argument yet."}""" + get_language_instruction()

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
