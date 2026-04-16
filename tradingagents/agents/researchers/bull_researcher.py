

def create_bull_researcher(llm):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        prompt = f"""You are a Bull Analyst advocating for investing in the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

## Debate Rules (follow strictly every round)
1. **Directly rebut** the bear's last argument — address their specific claims and data points, not generic counterarguments
2. **Cite specific evidence** from the analyst reports for every assertion — name the source (e.g., "per the technical report...", "the fundamentals report shows...")
3. **Do not repeat** arguments already made in the debate history — each round must advance new evidence or angles
4. Where the bear raises a valid point, briefly acknowledge it, then explain why the bull case still outweighs it

## Analysis Dimensions
Draw on whichever dimensions are most relevant and best supported by the analyst reports:
- **Technical Picture**: price action, trend structure, key indicator signals, support/resistance levels
- **Fundamental Strength**: earnings quality, balance sheet, growth trajectory, valuation
- **Macro & News Tailwinds**: favorable macro conditions, positive catalysts, regulatory environment, sector trends
- **Market Sentiment & Positioning**: retail/institutional sentiment, derivatives positioning, contrarian signals

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
- Bear's last argument: {current_response}
"""

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
