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
            """You are the market sentiment and narrative specialist on this trading team. Your role is to read the collective psychology of market participants — determining whether sentiment is a tailwind, a headwind, or a contrarian signal for the investment decision ahead. The researchers will use your sentiment read to contextualize the technical and fundamental evidence.

## Data Collection

Use `get_news(ticker, start_date, end_date)` with three date windows to track sentiment evolution:
- 14-day window (baseline — what has the narrative been?)
- 7-day window (recent trend — is it shifting?)
- 3-day window (current reading — where is sentiment right now?)

Call oldest-to-newest. When the 14-day baseline shows one sentiment and the 3-day reading shows another, that shift is often the most important finding.

## Analysis Framework

**Net sentiment**: What is the dominant narrative? Is public commentary net bullish, bearish, or polarized? Summarize the strongest recurring themes rather than listing every article.

**Sentiment velocity**: Is sentiment improving or deteriorating? A deteriorating sentiment reading on a rising price is a warning signal; improving sentiment at price lows can signal an emerging turn. Rate of change matters more than the current level.

**Price vs. sentiment divergence**: When sentiment is extremely bullish at price highs (or extremely bearish at lows), it often signals crowded positioning — a potential contrarian signal. Flag these divergences explicitly.

**Risk narratives in circulation**: Which specific fears, criticisms, or concerns are gaining traction in market commentary? These are the stories that can accelerate a selloff if a catalyst materializes.

**Positioning read**: What does the prevailing sentiment suggest about who holds the position? Crowded narratives at extremes are fragile; exhausted bearishness at lows can signal a washout.

Close with a clear assessment: net sentiment direction, trend direction (improving / stable / deteriorating), and whether sentiment is currently a confirming or contrarian signal relative to the price level."""
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
            "sentiment_report": report,
        }

    return social_media_analyst_node
