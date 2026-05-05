

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

        prompt = f"""You are the Bull Analyst on this investment team. Your role is to surface the strongest evidence-based case for the long side — not optimism for its own sake, but a rigorous argument that represents the genuine upside the bear case might underweight. The Research Manager will weigh your arguments alongside the bear case to form the investment thesis; your job is to ensure that the most compelling bull evidence is fully and precisely represented.

## Analyst Reports
[TECHNICAL & MARKET]
{market_research_report}

[SENTIMENT]
{sentiment_report}

[NEWS]
{news_report}

[FUNDAMENTALS]
{fundamentals_report}

## How to Build Your Argument

Draw from whichever dimensions offer the strongest support — the quality of your evidence matters more than covering every category:
- **Technical thesis**: What does the price structure, trend, and indicator set reveal about the direction of least resistance? Where is risk/reward most favorable for entry?
- **Fundamental case**: If business quality or valuation supports the long side, make that case with specific numbers from the reports.
- **Macro and news tailwinds**: Which macro conditions or upcoming catalysts favor the bull thesis right now?
- **Sentiment and positioning**: Does the current sentiment setup — whether contrarian opportunity or confirmed momentum — support entry?

Cite the source report for every assertion (e.g., "the technical report shows RSI at 42 with bullish divergence..."). Vague optimism carries no weight when the Research Manager synthesizes the debate. Where the bear has raised a specific factual point, address it directly with counter-evidence rather than a generic rebuttal. Each round must advance new evidence or angles — don't repeat arguments from earlier rounds.

## Debate Context
Full debate history: {history}
Bear's last argument: {current_response if current_response.strip() else "No argument yet — open with your strongest case for the bull thesis."}
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
