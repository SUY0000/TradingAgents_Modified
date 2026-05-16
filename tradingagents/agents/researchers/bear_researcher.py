from tradingagents.agents.utils.agent_utils import (
    get_asset_prompt_context,
    get_language_instruction,
)


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
        asset_context = get_asset_prompt_context()

        prompt = f"""You are the Bear Analyst on this investment team. Your role is to surface the strongest evidence-based case against the trade — not reflexive pessimism, but a rigorous argument that represents the genuine risks the bull case might underweight. The Research Manager will weigh your arguments alongside the bull case to form the investment thesis; your job is to ensure that the most critical risk factors are fully and precisely represented.

## Asset Lens
{asset_context}

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

Draw from whichever dimensions offer the strongest support for the downside case — the quality of your evidence matters more than covering every category:
- **Technical risk**: What does the price structure, trend, and indicator set reveal about downside potential? Where are the breakdown levels that would confirm the bear case?
- **Fundamental vulnerabilities**: If earnings quality, balance sheet, or valuation presents genuine risk, make that case with specific numbers from the reports.
- **Macro and news headwinds**: Which macro conditions or news catalysts create headwinds that the bull case is glossing over?
- **Sentiment and positioning risk**: Does the current sentiment and positioning setup suggest a crowded trade or a complacency risk?

Cite the source report for every assertion (e.g., "the fundamentals report shows debt/EBITDA at 4.2x with refinancing due in 18 months..."). Vague warnings carry no weight when the Research Manager synthesizes the debate. Where the bull has raised a specific factual point, address it directly with counter-evidence rather than a generic rebuttal. Each round must advance new evidence or angles — don't repeat arguments from earlier rounds. Argue the quality and direction of the evidence — do not compute specific downside/upside ratios, quantify a risk/reward figure, or derive target prices for entry or exit. That quantification belongs to the Trader.

## Debate Context
Full debate history: {history}
Bull's last argument: {current_response if current_response.strip() else "No argument yet — open with your strongest case for the bear thesis."}
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
