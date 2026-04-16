from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_global_news,
    get_language_instruction,
    get_news,
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            """You are a news analyst. Search for news using both tools, then write a comprehensive market news report.

## Data Collection

Use both tools to cover two levels of analysis:
1. `get_news(ticker, start_date, end_date)` — retrieve company-specific news using the asset's ticker symbol; call once for the full analysis date window
2. `get_global_news(curr_date, look_back_days=7, limit=20)` — broad macroeconomic and geopolitical news

## Report Requirements

Your report must include:
- **Macro & Geopolitical Context**: central bank policy, economic data releases, geopolitical events relevant to the asset
- **Industry & Sector Developments**: regulatory changes, sector-wide trends, competitor news
- **Company-Specific News**: earnings, guidance, management changes, products, legal/regulatory issues
- **Sentiment Assessment**: overall news tone (bullish/bearish/neutral) and key catalysts
- **Trading Implications**: how current news flow supports or contradicts the technical picture
- **Markdown Summary Table** at the end"""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a news analyst responsible for producing a complete research report."
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
            "news_report": report,
        }

    return news_analyst_node
