"""LLM client for AI agent chat using Anthropic Claude API."""

import anthropic
from typing import Generator
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import Company, DilutionScore, FundamentalsQuarterly, SecFiling

SYSTEM_PROMPT_COMPANY = """You are a dilution analysis assistant for the Dilution Monitor tool.
You are currently analyzing {ticker} ({name}).

Here is all available data for this company:

## Company Profile
- Ticker: {ticker}
- Name: {name}
- Sector: {sector}
- Exchange: {exchange}
- Market Cap: {market_cap}
- Tracking Tier: {tracking_tier}

## Dilution Scores (0-100, higher = more dilutive)
- Composite Score: {composite_score}
- Share CAGR Score: {share_cagr_score} (3-year annualized share growth: {share_cagr_3y})
- FCF Burn Score: {fcf_burn_score} (burn rate: {fcf_burn_rate})
- SBC/Revenue Score: {sbc_revenue_score} (ratio: {sbc_revenue_pct})
- Offering Frequency Score: {offering_freq_score} ({offering_count_3y} offerings in 3 years)
- Cash Runway Score: {cash_runway_score} ({cash_runway_months} months)
- ATM Active Score: {atm_active_score} (active: {atm_program_active})
- 12-Month Price Change: {price_change_12m}

## Quarterly Fundamentals (most recent first)
{fundamentals_table}

## SEC Filings
{filings_table}

Provide insightful analysis. Be specific, reference the actual data points. Use markdown
formatting for clarity. When discussing dilution risk, explain the implications for shareholders.
Keep responses concise but thorough."""

SYSTEM_PROMPT_GLOBAL = """You are a dilution analysis assistant for the Dilution Monitor tool.
You help users understand dilution metrics, analyze equity structures, interpret SEC filings,
and assess shareholder dilution risk. You can discuss general finance topics related to dilution,
stock-based compensation, cash burn, offerings, ATM programs, and related subjects.
Respond in clear, concise markdown."""

MEMO_GENERATION_PROMPT = """Based on the following conversation, generate a structured investment memo.
The memo should include:

## Executive Summary
A 2-3 sentence overview of the key findings.

## Company Overview
Key company details discussed.

## Dilution Risk Assessment
Analysis of dilution factors discussed in the conversation.

## Key Findings
Bullet points of the most important takeaways.

## Risks & Considerations
Any risks or concerns raised.

## Conclusion
Brief summary recommendation or outlook.

---

Conversation:
{conversation_text}

Generate the memo now in markdown format."""


def _fmt_num(v) -> str:
    if v is None:
        return "--"
    abs_v = abs(v)
    if abs_v >= 1e12:
        return f"${v / 1e12:.1f}T"
    if abs_v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs_v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if abs_v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _fmt_pct(v) -> str:
    if v is None:
        return "--"
    return f"{v * 100:.1f}%"


def build_company_context(db: Session, ticker: str) -> str:
    """Build system prompt with full company data injected."""
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        return SYSTEM_PROMPT_GLOBAL

    score = (
        db.query(DilutionScore)
        .filter_by(company_id=company.id)
        .order_by(desc(DilutionScore.id))
        .first()
    )

    fundamentals = (
        db.query(FundamentalsQuarterly)
        .filter_by(company_id=company.id)
        .order_by(desc(FundamentalsQuarterly.fiscal_period))
        .limit(12)
        .all()
    )

    filings = (
        db.query(SecFiling)
        .filter_by(company_id=company.id)
        .order_by(desc(SecFiling.filed_date))
        .limit(20)
        .all()
    )

    # Format fundamentals table
    fundamentals_table = "| Period | Shares | FCF | SBC | Revenue | Cash |\n"
    fundamentals_table += "|--------|--------|-----|-----|---------|------|\n"
    for f in fundamentals:
        fundamentals_table += (
            f"| {f.fiscal_period} "
            f"| {_fmt_num(f.shares_outstanding_diluted)} "
            f"| {_fmt_num(f.free_cash_flow)} "
            f"| {_fmt_num(f.stock_based_compensation)} "
            f"| {_fmt_num(f.revenue)} "
            f"| {_fmt_num(f.cash_and_equivalents)} |\n"
        )

    # Format filings table
    filings_table = "| Date | Type | Dilutive | Dilution Type | Amount |\n"
    filings_table += "|------|------|----------|---------------|--------|\n"
    for f in filings:
        filings_table += (
            f"| {f.filed_date} | {f.filing_type} "
            f"| {'Yes' if f.is_dilution_event else 'No'} "
            f"| {f.dilution_type or '--'} "
            f"| {_fmt_num(f.offering_amount_dollars)} |\n"
        )

    return SYSTEM_PROMPT_COMPANY.format(
        ticker=company.ticker,
        name=company.name,
        sector=company.sector or "N/A",
        exchange=company.exchange or "N/A",
        market_cap=_fmt_num(company.market_cap),
        tracking_tier=company.tracking_tier,
        composite_score=f"{score.composite_score:.1f}" if score else "N/A",
        share_cagr_score=f"{score.share_cagr_score:.1f}" if score and score.share_cagr_score is not None else "N/A",
        fcf_burn_score=f"{score.fcf_burn_score:.1f}" if score and score.fcf_burn_score is not None else "N/A",
        sbc_revenue_score=f"{score.sbc_revenue_score:.1f}" if score and score.sbc_revenue_score is not None else "N/A",
        offering_freq_score=f"{score.offering_freq_score:.1f}" if score and score.offering_freq_score is not None else "N/A",
        cash_runway_score=f"{score.cash_runway_score:.1f}" if score and score.cash_runway_score is not None else "N/A",
        atm_active_score=f"{score.atm_active_score:.1f}" if score and score.atm_active_score is not None else "N/A",
        share_cagr_3y=_fmt_pct(score.share_cagr_3y) if score else "N/A",
        fcf_burn_rate=_fmt_pct(score.fcf_burn_rate) if score else "N/A",
        sbc_revenue_pct=_fmt_pct(score.sbc_revenue_pct) if score else "N/A",
        offering_count_3y=score.offering_count_3y if score else "N/A",
        cash_runway_months=f"{score.cash_runway_months:.0f}" if score and score.cash_runway_months is not None else "N/A",
        atm_program_active=score.atm_program_active if score else "N/A",
        price_change_12m=_fmt_pct(score.price_change_12m) if score else "N/A",
        fundamentals_table=fundamentals_table,
        filings_table=filings_table,
    )


class LLMClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> Generator[str, None, None]:
        """Yield text chunks as they arrive from Claude."""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def generate_memo(
        self,
        conversation_text: str,
        company_context: str = "",
    ) -> str:
        """Generate a structured memo from a conversation."""
        system = company_context or SYSTEM_PROMPT_GLOBAL
        prompt = MEMO_GENERATION_PROMPT.format(conversation_text=conversation_text)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
