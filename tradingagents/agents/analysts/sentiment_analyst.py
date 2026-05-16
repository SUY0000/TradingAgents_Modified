"""Sentiment analyst — multi-source sentiment analysis for a target ticker.

Previously named ``social_media_analyst``. Renamed and redesigned because
the old version had a prompt that demanded social-media analysis but the
only tool available was Yahoo Finance news — which led LLMs to fabricate
Reddit/X/StockTwits content under prompt pressure (verified live).

The redesigned agent pre-fetches three complementary data sources before
the LLM is invoked and injects them into the prompt as structured blocks:

  1. News headlines     — Yahoo Finance (institutional framing)
  2. StockTwits messages — retail-trader posts indexed by cashtag, with
                           user-labeled Bullish/Bearish sentiment tags
  3. Reddit posts        — r/wallstreetbets, r/stocks, r/investing

The agent does not use tool-calling; the data is in the prompt from
turn 0. The LLM produces the sentiment report in a single invocation.

See: https://github.com/TauricResearch/TradingAgents/issues/557
"""

from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_news,
)
from tradingagents.dataflows.reddit import fetch_reddit_posts
from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    For US/crypto tickers: pre-fetches news + StockTwits + Reddit data.
    For A-share tickers: pre-fetches three-layer sentiment (retail/sell-side/buy-side).
    Data is injected into the prompt as structured blocks for a single LLM call.
    """

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = build_instrument_context(ticker)

        from tradingagents.dataflows.config import get_config
        vendors = get_config().get("data_vendors", {})
        is_a_share = (
            vendors.get("core_stock_apis") == "akshare"
            and vendors.get("technical_indicators") == "akshare"
        )

        if is_a_share:
            from tradingagents.agents.utils.cn_sentiment_tools import (
                get_a_share_hot_rank_history,
                get_a_share_research_reports,
                get_a_share_institutional_research,
            )
            retail_block = get_a_share_hot_rank_history.func(ticker, end_date, look_back_days=30)
            sell_side_block = get_a_share_research_reports.func(ticker, end_date, look_back_days=90)
            buy_side_block = get_a_share_institutional_research.func(ticker, end_date, look_back_days=180)
            system_message = _build_a_share_system_message(
                ticker=ticker,
                end_date=end_date,
                retail_block=retail_block,
                sell_side_block=sell_side_block,
                buy_side_block=buy_side_block,
            )
        else:
            # Pre-fetch all three sources. Each fetcher degrades gracefully and
            # returns a string (no exceptions surface from here), so the LLM
            # always sees something — either real data or a clear placeholder.
            news_block = get_news.func(ticker, start_date, end_date)
            stocktwits_block = fetch_stocktwits_messages(ticker, limit=30)
            reddit_block = fetch_reddit_posts(ticker)
            system_message = _build_system_message(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                news_block=news_block,
                stocktwits_block=stocktwits_block,
                reddit_block=reddit_block,
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # No bind_tools — the data is already in the prompt; a single LLM
        # call produces the report directly.
        chain = prompt | llm
        result = chain.invoke(state["messages"])

        return {
            "messages": [result],
            "sentiment_report": result.content,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### StockTwits messages — retail-trader social platform indexed by cashtag
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### Reddit posts — r/wallstreetbets, r/stocks, r/investing (past 7 days)
Community discussion. Engagement signal via upvote score and comment count. Subreddit character matters (r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term).

<start_of_reddit>
{reddit_block}
<end_of_reddit>

## How to analyze this data (best practices)

1. **Read the StockTwits Bullish/Bearish ratio as a leading retail-sentiment signal.** A 70/30 bullish/bearish split is moderately bullish; ≥90/10 may indicate over-extension and contrarian risk; 50/50 is uncertainty. Sample size matters — base rates on the actual message count, not percentages alone.

2. **Look for cross-source divergences.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious).

3. **Weight Reddit posts by engagement.** A 400-upvote / 200-comment thread reflects community attention; a 3-upvote post is noise. Read the body excerpts for context — the title alone often misleads.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this caveat explicitly. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

## Output

Produce a sentiment report covering, in order:

1. **Overall sentiment direction** — Bullish / Bearish / Neutral / Mixed — with a brief confidence note based on data quality and sample size.
2. **Source-by-source breakdown** — what each of news / StockTwits / Reddit is telling you, with specific evidence (cite message counts, ratios, notable posts).
3. **Divergences, alignments, and key narratives** across sources.
4. **Catalysts and risks** surfaced by the data.
5. **Markdown table** at the end summarizing key sentiment signals, their direction, source, and supporting evidence.

{get_language_instruction()}"""


def _build_a_share_system_message(
    *,
    ticker: str,
    end_date: str,
    retail_block: str,
    sell_side_block: str,
    buy_side_block: str,
) -> str:
    """Assemble the A-share sentiment-analyst system message with three-layer data."""
    return f"""You are the market sentiment and narrative specialist on this trading team, focused on A-share (China mainland) markets. Your report reads the collective psychology of three distinct layers of market participants and determines whether their combined sentiment is a tailwind, headwind, or contrarian signal for the investment decision ahead.

The following data has already been collected for you as of {end_date}:

## Retail layer — East Money popularity ranking trend (past 30 days)

<start_of_retail>
{retail_block}
<end_of_retail>

## Sell-side layer — Broker research reports and rating consensus (past 90 days)

<start_of_sell_side>
{sell_side_block}
<end_of_sell_side>

## Buy-side layer — Institutional on-site research visits (past 180 days)

<start_of_buy_side>
{buy_side_block}
<end_of_buy_side>

## Analysis Framework

**Retail attention (散户层)**: Is retail interest rising or falling? Rising popularity rank with stagnant or falling price is a crowding warning. Falling retail attention during a price rally can signal a healthy, institution-led move.

**Sell-side consensus (卖方层)**: What is the dominant broker rating? Are there recent upgrades or downgrades? Concentrated "买入" ratings at highs can be a contrarian warning; downgrades near lows can signal washout. Track earnings forecast direction (are EPS estimates being revised up or down?).

**Buy-side engagement (买方层)**: How many institutional visits have occurred recently? High visit frequency from fund managers and analysts signals strong institutional interest. Sudden drop in visits can signal waning conviction. Note the most recent visit date — recency matters.

**Three-layer synthesis**: When all three layers align (e.g., falling retail + firm sell-side + heavy buy-side visits = institutional accumulation under the radar), the signal is high-conviction. When layers diverge, explain the divergence and its implications.

Close with a three-layer summary table (retail / sell-side / buy-side: each rated bullish / neutral / bearish with one-sentence rationale) and an overall net sentiment verdict. Your report ends with this table — do not add investment recommendations, entry/exit guidance, or sizing advice.{get_language_instruction()}"""


# ---------------------------------------------------------------------------
# Backwards-compatibility shim
# ---------------------------------------------------------------------------
def create_social_media_analyst(llm):
    """Deprecated alias for :func:`create_sentiment_analyst`.

    Kept so existing code that imports ``create_social_media_analyst``
    continues to work.

    .. deprecated::
        Import :func:`create_sentiment_analyst` directly instead.
    """
    import warnings
    warnings.warn(
        "create_social_media_analyst is deprecated and will be removed in a "
        "future version. Use create_sentiment_analyst instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return create_sentiment_analyst(llm)
