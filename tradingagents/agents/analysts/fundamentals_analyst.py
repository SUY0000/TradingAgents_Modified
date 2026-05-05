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

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

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

Close with a summary table: key metrics, their trend direction (improving / stable / deteriorating), and whether each is a bull factor, bear factor, or neutral for the investment case."""
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
