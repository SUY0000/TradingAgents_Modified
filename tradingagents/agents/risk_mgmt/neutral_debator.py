

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

        prompt = f"""You are the Neutral Risk Analyst in a risk management debate. Your role is to evaluate the trader's decision through a risk-adjusted return lens — finding the strategy that maximizes return per unit of risk, not simply splitting the difference between the other two analysts.

## Trader's Decision Under Review
{trader_decision}

## Research Manager's Investment Plan (context)
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Debate Rules (follow strictly every round)
1. **Directly challenge** both the aggressive and conservative analysts' last arguments — identify where each is overstating their case with specific data
2. **Cite specific evidence** from the analyst reports — name the source for every assertion
3. **Do not repeat** arguments already in the debate history — advance new analytical angles each round
4. **Propose a concrete adjusted strategy**: do not simply split the difference — offer a specific modified plan

## Your Analysis Framework
Evaluate the trader's decision through these dimensions:
- **Risk/Reward Assessment**: estimate the expected return vs. max risk for the current plan; compare to an adjusted version
- **Entry & Timing**: is the current entry point optimal given the technical and macro environment?
- **Position Structure**: recommend a specific position size and staged entry or exit plan that balances conviction with protection
- **Dynamic Adjustment Triggers**: define conditions that would warrant shifting toward the aggressive or conservative stance

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
- Aggressive analyst's last argument: {current_aggressive_response if current_aggressive_response.strip() else "No argument yet — present your opening assessment."}
- Conservative analyst's last argument: {current_conservative_response if current_conservative_response.strip() else "No argument yet."}"""

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
