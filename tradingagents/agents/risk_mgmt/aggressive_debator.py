

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

        prompt = f"""You are the Aggressive Risk Analyst in a risk management debate. Your role is to quantify the opportunity cost of excessive caution and make the strongest evidence-based case for pursuing the trader's decision with appropriate conviction.

## Trader's Decision Under Review
{trader_decision}

## Research Manager's Investment Plan (context)
{investment_plan.strip() if investment_plan.strip() else "Not available."}

## Debate Rules (follow strictly every round)
1. **Directly rebut** the conservative and neutral analysts' last arguments — address their specific concerns with data, not generic optimism
2. **Cite specific evidence** from the analyst reports — name the source for every assertion
3. **Do not repeat** arguments already in the debate history — advance new angles each round
4. **Quantify the opportunity cost**: where opponents advocate caution, show what returns would be foregone

## Your Analysis Framework
Build your argument across the most relevant dimensions:
- **Technical Momentum**: trend strength, momentum indicators, key breakout levels supporting entry
- **Upside Targets**: price targets, risk/reward ratio, expected return vs. max risk
- **Catalyst Timing**: upcoming events or conditions that favor acting now rather than waiting
- **Position Sizing**: recommend an optimal position size that captures upside while keeping risk bounded

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
- Conservative analyst's last argument: {current_conservative_response if current_conservative_response.strip() else "No argument yet — present your opening case."}
- Neutral analyst's last argument: {current_neutral_response if current_neutral_response.strip() else "No argument yet."}"""

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
