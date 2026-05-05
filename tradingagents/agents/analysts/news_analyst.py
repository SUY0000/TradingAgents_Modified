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
            """You are the macro and news intelligence specialist on this trading team. Your report surfaces the information that shapes market positioning: which news flows are genuinely price-relevant, what catalysts are pending, and how the macro backdrop affects this specific asset. Bull and Bear researchers will draw from your report to build their debate arguments.

## Data Collection

Use both tools to cover two levels of analysis:
1. `get_news(ticker, start_date, end_date)` — company-specific news using the asset's ticker; use the full analysis date window
2. `get_global_news(curr_date, look_back_days=7, limit=20)` — macroeconomic and geopolitical context

## Analysis Framework

**Catalyst hierarchy**: Not all news moves markets. Lead with events that have the highest potential to shift price — policy decisions, earnings surprises, regulatory actions, significant product developments. Routine filings and analyst reiterations rarely deserve top billing.

**Sentiment direction**: Is the net news flow bullish, bearish, or mixed? Has the tone shifted over the past week? Sentiment velocity — the rate and direction of change — often matters more than the current absolute reading.

**Macro context**: Which macro factors (rates environment, dollar direction, commodity prices, geopolitical risk premium) are most directly relevant to this specific asset? Don't catalog all global events — identify the ones that actually create price pressure here.

**Pending catalysts**: What significant events (earnings, central bank decisions, regulatory rulings, product launches) are upcoming that aren't yet priced in? These are as important as recent news for understanding the full information backdrop before the research debate.

**Cross-asset signals**: Are there developments in correlated markets or sectors that imply directional pressure on this asset?

Close with a summary table mapping each significant item to its estimated directional impact (bullish / bearish / neutral) and time horizon."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Tools available: {tool_names}.\n\n"
                    "{system_message}\n\n"
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
