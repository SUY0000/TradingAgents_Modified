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
    get_asset_type,
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

        asset_type = get_asset_type()

        if asset_type == "a_share":
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
            builder = _build_crypto_system_message if asset_type == "crypto" else _build_stock_system_message
            system_message = builder(
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
                    "{system_message}\n\n"
                    "Current date: {current_date}. {instrument_context}",
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


def _build_stock_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
) -> str:
    """Assemble the US/listed-equity sentiment prompt."""
    return f"""You are the market sentiment and narrative specialist for a listed equity or ETF. Your job is to read the psychology around {ticker}: not whether the company is good or bad, but whether the current narrative, attention, and positioning are likely to amplify or fight the investment thesis downstream.

You already have the evidence for {start_date} through {end_date}. Treat news as the institutional narrative, StockTwits as fast retail positioning, and Reddit as slower community conviction. Do not invent missing social data; if a source is thin, make that uncertainty part of the conclusion.

<news_headlines>
{news_block}
</news_headlines>

<stocktwits_messages>
{stocktwits_block}
</stocktwits_messages>

<reddit_posts>
{reddit_block}
</reddit_posts>

Read the three sources as one market psychology tape. Look for the dominant story, how quickly it is changing, whether retail enthusiasm or fear is becoming crowded, and whether price-relevant catalysts are being understood or ignored. The strongest insight often comes from disagreement: bullish social chatter against deteriorating news, quiet retail while institutions re-rate the stock, or exhausted bearishness after bad news has already been absorbed.

Write a concise but high-signal sentiment report. Anchor claims in the supplied evidence, distinguish event from opinion, and explain whether sentiment is confirming, fading, overheated, washed out, or meaningfully divided. Close with a compact summary table covering source, direction, conviction, and the one narrative fact that matters most. Your report ends with that table; do not add trade recommendations, entry/exit guidance, or sizing advice.{get_language_instruction()}"""


def _build_crypto_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
) -> str:
    """Assemble the crypto sentiment prompt."""
    return f"""You are the crypto sentiment and reflexivity analyst for {ticker}. Your task is to read whether narratives, crowd positioning, and community attention are creating a tailwind, a liquidation-prone crowded trade, or a fading story. Crypto sentiment is reflexive: social conviction can drive flows, but crowded conviction can also become fuel for violent reversals.

The evidence below covers {start_date} through {end_date}. Yahoo/news headlines reflect institutional and regulatory framing; StockTwits captures short-horizon trader bias; Reddit captures community narratives and conviction. Use them alongside the knowledge that crypto markets trade continuously, react sharply to liquidity, leverage, exchange flows, regulation, ETF/macro headlines, protocol events, and token-specific unlock/supply narratives.

<news_headlines>
{news_block}
</news_headlines>

<stocktwits_messages>
{stocktwits_block}
</stocktwits_messages>

<reddit_posts>
{reddit_block}
</reddit_posts>

Focus on the narrative that could move marginal buyers or sellers now: risk-on/risk-off appetite, regulatory or ETF flow headlines, protocol adoption, security incidents, tokenomics, leverage euphoria, capitulation, and whether retail is chasing after the move or quietly accumulating before confirmation. Treat missing or thin social data as an analytical signal about attention, not as permission to speculate.

Write a focused crypto sentiment report that separates durable narrative from hype. Explain whether sentiment is constructive, fragile, overheated, washed out, or irrelevant because liquidity/macro dominates. Close with a compact summary table covering source, direction, conviction, and the decisive narrative or positioning clue. Your report ends with that table; do not add trade recommendations, entry/exit guidance, or sizing advice.{get_language_instruction()}"""


def _build_a_share_system_message(
    *,
    ticker: str,
    end_date: str,
    retail_block: str,
    sell_side_block: str,
    buy_side_block: str,
) -> str:
    """Assemble the A-share sentiment-analyst system message with three-layer data."""
    return f"""You are the A-share sentiment and narrative specialist for {ticker}. Your job is to read the three participant layers that drive mainland China equity reflexivity: retail attention, sell-side narrative, and buy-side institutional interest. Do not treat sentiment as generic mood; in A-shares, who is paying attention often matters as much as what they say.

The following evidence has already been collected as of {end_date}.

<retail_attention_eastmoney_30d>
{retail_block}
</retail_attention_eastmoney_30d>

<sell_side_research_90d>
{sell_side_block}
</sell_side_research_90d>

<buy_side_institutional_visits_180d>
{buy_side_block}
</buy_side_institutional_visits_180d>

Read the layers against each other. Rising retail popularity can confirm momentum early, but at price highs it can also signal crowding. Falling retail attention during improving fundamentals or strong institutional visits can be a quiet accumulation signal. Sell-side ratings matter less as labels and more as revision pressure: upgrades, downgrades, forecast direction, and whether consensus is becoming one-sided. Buy-side visits matter through recency, frequency, and institution quality; a sudden absence of visits can be as informative as a surge.

Write a high-conviction A-share sentiment report that explains whether the three layers align, conflict, or create a contrarian setup. Identify the single most important narrative imbalance and what it implies for downstream research. Close with a compact three-layer table covering participant layer, direction, conviction, and decisive evidence, followed by one net sentiment verdict. Your report ends there; do not add trade recommendations, entry/exit guidance, or sizing advice.{get_language_instruction()}"""


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
