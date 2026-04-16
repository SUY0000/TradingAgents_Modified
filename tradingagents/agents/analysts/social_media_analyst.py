from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction, get_news
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
        ]

        system_message = (
            """You are a market sentiment analyst. Research public sentiment and market narrative around the asset using targeted news searches, then write a comprehensive sentiment report.

## Data Collection

Use `get_news(ticker, start_date, end_date)` with the asset's ticker symbol to retrieve recent news and public commentary. Run 2–3 calls with different date windows to capture sentiment evolution over time (e.g., past 3 days, past 7 days, past 14 days). Use the earliest window first to establish a baseline, then the latest window to identify shifting sentiment.

## Report Requirements

Your report must include:
- **Overall Sentiment**: net market sentiment (bullish/bearish/mixed) with supporting evidence
- **Key Sentiment Drivers**: top narratives driving current market perception, both positive and negative
- **Sentiment Trend**: is sentiment improving, deteriorating, or stable over the analysis window?
- **Retail vs Institutional Tone**: distinguish retail chatter from institutional commentary where discernible
- **Risk Narratives**: FUD, reputational risks, or hype cycles that could impact price
- **Trading Implications**: how sentiment aligns or diverges from the fundamental and technical picture
- **Markdown Summary Table** at the end"""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a market sentiment analyst responsible for producing a complete research report."
                    " Call ALL required tools before writing the final report."
                    " Do NOT output the report until all tools have been called."
                    " Tools available: {tool_names}.\n\n{system_message}\n\n"
                    "Current date: {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
