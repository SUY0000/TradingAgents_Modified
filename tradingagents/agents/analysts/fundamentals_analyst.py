from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_asset_type,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        asset_type = get_asset_type()
        is_a_share = asset_type == "a_share"

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

        system_message = _build_system_message(asset_type)

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


def _build_system_message(asset_type: str) -> str:
    language = get_language_instruction()
    if asset_type == "crypto":
        return f"""You are the crypto fundamentals analyst. Traditional equity statements may be sparse or economically irrelevant here, so your job is to extract whatever the configured fundamentals tools can provide, then judge the asset through crypto-native economics: network usage, protocol revenue where available, token supply, issuance/unlocks, ecosystem traction, developer/community durability, security/regulatory risk, and whether value capture actually accrues to the token.

Call all four fundamentals tools. If a financial statement is unavailable or not meaningful for this crypto ticker, say so plainly and do not force equity ratios onto a token. Use any available company/security information only as context; the central question is whether the token or crypto asset has durable demand, credible supply discipline, and identifiable catalysts or vulnerabilities.

Write a fundamentals report that separates hard data from absent data. Explain the economic model, supply/demand pressure, quality of adoption, balance-sheet or issuer risk if relevant, and the largest fundamental uncertainty. Close with a compact table of fundamental factors, direction, evidence quality, and bull/bear/neutral classification. Your report ends there; do not add investment recommendations, entry/exit guidance, or sizing advice.{language}"""

    if asset_type == "a_share":
        return f"""You are the A-share fundamental research specialist. Your job is to decide whether the current market narrative is supported by business quality, earnings trajectory, balance-sheet resilience, shareholder structure, and valuation versus domestic peers.

Call all seven tools: core fundamentals, income statement, balance sheet, cashflow, earnings forecast, shareholder count, and valuation comparison. In A-shares, do not stop at PE/PB. Pay attention to earnings preannouncement direction, cash-flow conversion, leverage and liquidity, changes in shareholder count, peer-relative valuation, industry classification, and whether the stock deserves a premium or discount inside its sector.

Read the numbers as a business story. A falling shareholder count can indicate institutional concentration; rising holders alongside weak price can signal retail dispersion. Broker forecasts matter only if they align with actual profitability and cash generation. Valuation is only cheap if quality and earnings durability justify it.

Write a focused fundamental report covering business quality, earnings quality, financial resilience, shareholder-structure signal, relative valuation, and forward catalyst risk. Close with a compact table of key factors, trend, evidence quality, and bull/bear/neutral classification. Your report ends there; do not add investment recommendations, entry/exit guidance, or suitability claims.{language}"""

    return f"""You are the listed-equity fundamental research specialist. Your job is to decide whether the market price is supported by business economics: moat, growth durability, margin structure, cash conversion, balance-sheet resilience, valuation, and the specific risks that could force a rerating.

Call all four tools: fundamentals, income statement, balance sheet, and cashflow. Do not produce a generic company profile. Build a thesis-quality read of business quality, earnings quality, solvency, valuation context, and risk triggers. Compare net income to operating cash flow, growth to margins, leverage to earnings power, and valuation to the durability of the business.

The best fundamental report makes the debate sharper: what would a serious bull underwrite, what would a serious bear attack, and which fact matters most? If data is missing, identify the analytical gap rather than filling it with assumptions.

Write a focused fundamental report covering business quality, earnings quality, financial resilience, valuation context, and key risk triggers. Close with a compact table of key factors, trend, evidence quality, and bull/bear/neutral classification. Your report ends there; do not add investment recommendations, entry/exit guidance, or suitability claims.{language}"""
