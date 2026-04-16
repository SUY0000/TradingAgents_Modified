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
            """You are a fundamentals analyst. Call all four tools to build a complete financial picture, then write a comprehensive report.

## Data Collection

Call all four tools — each covers a distinct dimension:
1. `get_fundamentals` — company profile, key ratios, business overview
2. `get_income_statement` — revenue, earnings, margins, growth trends
3. `get_balance_sheet` — assets, liabilities, equity, liquidity
4. `get_cashflow` — operating/investing/financing flows, free cash flow

## Report Requirements

Your report must include:
- **Business Overview**: company profile, industry positioning, competitive moat
- **Profitability**: revenue growth, gross/operating/net margins, EPS trend
- **Financial Health**: debt-to-equity, current ratio, liquidity and solvency
- **Cash Flow Quality**: operating cash flow vs net income, FCF generation
- **Valuation Context**: P/E, P/B, EV/EBITDA vs sector peers where data is available
- **Key Risks & Catalysts**: material risks, upcoming earnings or guidance events
- **Markdown Summary Table** at the end"""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a fundamentals analyst responsible for producing a complete research report."
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
