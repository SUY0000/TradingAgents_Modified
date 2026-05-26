"""System prompt builder for the chat replay agent."""
from __future__ import annotations

import datetime


def build_system_prompt(
    manifest: dict,
    reports_bundle: dict,
    past_context: str,
    today: datetime.date,
    tool_names_csv: str = "",
    *,
    output_language: str | None = None,
) -> str:
    ticker = manifest.get("ticker", "")
    analysis_date = manifest.get("analysis_date", "")
    try:
        days_since = (today - datetime.date.fromisoformat(analysis_date)).days
    except (ValueError, TypeError):
        days_since = "?"

    # Inline asset_prompt_context (avoids touching global config)
    asset_type = manifest.get("asset_type", "stock")
    asset_prompt_context_map = {
        "stock": (
            "Asset lens: listed equity/ETF. Judge evidence through earnings power, "
            "valuation, sector rotation, institutional positioning, macro discount rates, "
            "and company-specific catalysts."
        ),
        "a_share": (
            "Asset lens: China mainland A-share. Judge evidence through policy tone, "
            "sector rotation, retail attention, northbound/main-force flows, margin balance, "
            "limit-up/down behavior, and domestic peer valuation."
        ),
        "crypto": (
            "Asset lens: crypto asset. Judge evidence through liquidity, leverage, funding/OI, "
            "token supply, protocol or adoption catalysts, regulatory headlines, macro risk appetite, "
            "and reflexive crowd positioning."
        ),
    }
    asset_prompt_context = asset_prompt_context_map.get(asset_type, asset_prompt_context_map["stock"])

    # Build instrument context line
    company = manifest.get("company_of_interest", ticker)
    instrument_context = (
        f"The instrument to analyze is `{company}` (original ticker: `{ticker}`). "
        f"{asset_prompt_context}"
    )

    def _report(key: str) -> str:
        val = reports_bundle.get(key, "")
        return val if val else "_（无）_"

    # Risk debate: concatenate three sections
    risk_parts = []
    for k in ("risk_aggressive", "risk_conservative", "risk_neutral"):
        v = reports_bundle.get(k, "")
        if v:
            risk_parts.append(v)
    risk_debate = "\n\n---\n\n".join(risk_parts) if risk_parts else "_（无）_"

    past_block = past_context.strip() if past_context and past_context.strip() else "_（无）_"

    # Language instruction
    lang = output_language or manifest.get("output_language", "English")
    if lang.strip().lower() == "english":
        language_instruction = ""
    else:
        language_instruction = f" Write your entire response in {lang}."

    return f"""你是 TradingAgents 的复盘对话分析师。用户加载了 {ticker} 于 {analysis_date} 的历史报告（报告距今 {days_since} 天），需要与你深入讨论该报告的判断质量与后续行情发展。

{instrument_context}

## 已加载的报告上下文

### 1. Analyst Reports

#### Market & Technical
{_report("market")}

#### Fundamentals
{_report("fundamentals")}

#### News
{_report("news")}

#### Sentiment
{_report("sentiment")}

### 2. Research Manager 投资计划
{_report("research_manager")}

### 3. Trader 执行方案
{_report("trader")}

### 4. 风险辩论
{risk_debate}

### 5. Portfolio Manager 最终决策
{_report("portfolio_decision")}

### 6. 历史决策与教训
{past_block}

---

## 工作方式
1. 用户提"报告里这条结论对吗"，先回到对应原文定位证据，再决定是否调工具查报告日期之后的真实数据验证。
2. 调工具前简述意图：为什么这个工具能回答此问题。
3. 区分两类讨论：
   (a) 报告内部一致性 / 逻辑质量 → 不调工具
   (b) 后续行情发展 / 价格变化 / 新事件 → 必须调工具拿报告日期之后的数据
4. 当原报告的预测被后续行情证伪/印证，明确指出关键转折点。
5. 不要重新生成完整 BUY/SELL 决定；这是复盘讨论，不是新一轮决策。
6. 你不持有执行权限；只做分析与讨论，不发出下单指令。

## 工具
{tool_names_csv}
{language_instruction}"""
