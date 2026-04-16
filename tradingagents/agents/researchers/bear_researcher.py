from tradingagents.agents.utils.agent_utils import get_language_instruction


def create_bear_researcher(llm):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        prompt = f"""You are a Bear Analyst making the case against investing in the stock. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

## Debate Rules (follow strictly every round)
1. **Directly rebut** the bull's last argument — address their specific claims and data points, not generic counterarguments
2. **Cite specific evidence** from the analyst reports for every assertion — name the source (e.g., "per the technical report...", "the news report shows...")
3. **Do not repeat** arguments already made in the debate history — each round must advance new evidence or angles
4. Where the bull raises a valid point, briefly acknowledge it, then explain why the bear case still outweighs it

## Analysis Dimensions
Draw on whichever dimensions are most relevant and best supported by the analyst reports:
- **Technical Weakness**: deteriorating price action, bearish indicator signals, key resistance levels, breakdown patterns
- **Fundamental Risks**: earnings quality concerns, balance sheet vulnerabilities, valuation stretched, declining trajectory
- **Macro & News Headwinds**: adverse macro conditions, negative catalysts, regulatory threats, sector deterioration
- **Market Sentiment & Positioning**: overextended positioning, crowded longs, derivatives signals pointing to downside risk

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
- Bull's last argument: {current_response}
""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
