from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        vendors = get_config().get("data_vendors", {})
        is_a_share = (
            vendors.get("core_stock_apis") == "akshare"
            and vendors.get("technical_indicators") == "akshare"
        )

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        if is_a_share:
            from tradingagents.agents.utils.fundamental_data_tools import (
                get_earnings_forecast,
                get_shareholder_count,
                get_valuation_comparison,
            )
            tools += [get_earnings_forecast, get_shareholder_count, get_valuation_comparison]

        if is_a_share:
            system_message = (
                """You are the fundamental research specialist on this trading team, focused on A-share (China mainland) markets. Your report answers the core valuation question: does the current price reflect the underlying business economics, and what does the shareholder structure and peer valuation say about the risk/opportunity? The researchers will draw on your findings to anchor their debate in fundamental reality.

## Data Collection

Call all seven tools — each covers a distinct dimension:
1. `get_fundamentals` — company overview, key ratios (PE/PB/dividend yield), sector classification
2. `get_income_statement` — revenue trend, gross and net margin structure, earnings quality
3. `get_balance_sheet` — capital structure, liquidity (current ratio), debt load
4. `get_cashflow` — operating / investing / financing cash flows, free cash flow quality
5. `get_earnings_forecast(ticker, curr_date)` — management pre-announcement (业绩预告): YoY profit change expectation, announcement type (预增/续盈/预减/扭亏), and reason
6. `get_shareholder_count(ticker, curr_date)` — quarterly stock holder count history (股东户数): declining count = institutional concentration; rising count = retail dispersion
7. `get_valuation_comparison(ticker, curr_date)` — peer PE/PB/PS/PEG/EV-EBITDA vs. industry median and top peers (同行估值对标)

## Analysis Framework

**Business quality**: Competitive position, moat durability, revenue mix. What drives growth — volume, price, or mix?

**Earnings quality**: Compare net profit to operating cash flow — divergence flags accounting aggression. Check if earnings pre-announcement (业绩预告) is consistent with the trend in the financial statements.

**Financial resilience**: Net Debt/EBITDA, current ratio, short-term debt maturity. Could the balance sheet absorb a 20–30% revenue shock?

**Shareholder structure signals**: Is 股东户数 falling while price rises (institutional accumulation — positive) or rising while price is stagnant (retail dispersion — warning)? Compare the most recent quarter to the prior 3–4 periods.

**Relative valuation**: Does the stock trade at a premium or discount to the industry median PE/PB? Is the premium justified by superior ROE or growth, or is it excessive? Flag any extreme outlier metrics.

**Forward catalysts**: Earnings pre-announcement direction (if available) — is the company guiding for acceleration or deceleration relative to consensus?

Close with a summary table: key metrics, trend direction (improving / stable / deteriorating), and bull / bear / neutral classification. Your report ends with this table — do not add investment recommendations, entry/exit guidance, or suitability assessments."""
                + get_language_instruction()
            )
        else:
            system_message = (
                """You are the fundamental research specialist on this trading team. Your report answers the core valuation question: does the current price reflect the underlying business economics, or is there a meaningful mismatch that creates risk or opportunity? The researchers will draw on your findings to anchor their bull and bear arguments in fundamental reality.

## Data Collection

Call all four tools — each covers a distinct dimension of the financial picture:
1. `get_fundamentals` — business overview, key ratios, sector positioning
2. `get_income_statement` — revenue trend, margin structure, earnings quality
3. `get_balance_sheet` — capital structure, liquidity, solvency
4. `get_cashflow` — cash generation quality, capex intensity, free cash flow

## Analysis Framework

**Business quality**: What competitive advantage does this company have, and how durable is it? The quality of the moat determines how much valuation premium is justified.

**Earnings quality**: Compare net income to operating cash flow — significant divergence (earnings growing while FCF stagnates or declines) is a red flag that deserves explicit analysis. One-time items can flatter reported numbers.

**Financial resilience**: Assess debt load relative to earnings power (Net Debt/EBITDA) and the current ratio. Would the balance sheet survive a 20–30% revenue shock?

**Valuation context**: Current multiple vs. the company's historical range and sector peers. Is growth priced in, or is there a discount that creates a margin of safety? Overvaluation is a risk factor even for high-quality businesses.

**Key risk triggers**: Identify the specific financial vulnerabilities — covenant risks, refinancing walls, customer concentration, regulatory exposure — that could force a rerating.

For crypto or digital assets where traditional financial statements are unavailable: focus on protocol revenue, token supply dynamics, ecosystem growth metrics, and developer activity where data exists. Note explicitly when standard metrics cannot be computed.

Close with a summary table: key metrics, their trend direction (improving / stable / deteriorating), and whether each is a bull factor, bear factor, or neutral for the investment case. Your report ends with this table — do not add investment recommendations, guidance on whether to buy or sell, or suitability assessments for any investor type."""
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
