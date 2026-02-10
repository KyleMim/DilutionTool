"""LLM client for AI agent chat using Anthropic Claude API with tool use."""

import json
import logging
from typing import Generator
from datetime import datetime, timedelta

import anthropic
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import Company, DilutionScore, FundamentalsQuarterly, SecFiling, Note
from backend.services.fmp_client import FMPClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_COMPANY = """You are a dilution analysis assistant for the Dilution Monitor tool.
You are currently analyzing {ticker} ({name}).

Here is the data we have in our database for this company:

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

You have access to tools to look up additional data:
- Use `lookup_company_profile` to get fresh company profile data from the financial API
- Use `lookup_fundamentals` to get detailed quarterly financials (income, cashflow, balance sheet)
- Use `lookup_stock_price` to get historical daily prices
- Use `search_notes` to find previous research notes and memos (returns previews)
- Use `get_note_detail` to read the full content of a specific note by ID
- Use `save_note` to save a new note or memo with your analysis
- Use `update_note` to revise or overwrite an existing note
- Use `web_search` to search the internet for recent news, competitor info, management details, analyst opinions, or any other public information

When the user asks you to write a memo or save findings, use the save_note tool directly.
You can incorporate content from existing notes by reading them with get_note_detail first.

Provide insightful analysis. Be specific, reference the actual data points. Use markdown
formatting for clarity. When discussing dilution risk, explain the implications for shareholders.
Keep responses concise but thorough."""

SYSTEM_PROMPT_GLOBAL = """You are a dilution analysis assistant for the Dilution Monitor tool.
You help users understand dilution metrics, analyze equity structures, interpret SEC filings,
and assess shareholder dilution risk. You can discuss general finance topics related to dilution,
stock-based compensation, cash burn, offerings, ATM programs, and related subjects.

You have access to tools to look up data about any company:
- Use `lookup_company_profile` to get company profile data
- Use `lookup_fundamentals` to get detailed quarterly financials
- Use `lookup_stock_price` to get historical daily prices
- Use `lookup_dilution_score` to get our internal dilution score for tracked companies
- Use `search_notes` to find previous research notes and memos (returns previews)
- Use `get_note_detail` to read the full content of a specific note by ID
- Use `save_note` to save a new note or memo with your analysis
- Use `update_note` to revise or overwrite an existing note
- Use `web_search` to search the internet for recent news, competitor info, management details, analyst opinions, or any other public information

When the user asks you to write a memo or save findings, use the save_note tool directly.
You can incorporate content from existing notes by reading them with get_note_detail first.
When a user asks about a specific company, use the tools to look up data before answering.
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


# ── Tool Definitions ─────────────────────────────────────────────────

TOOLS = [
    {
        "name": "lookup_company_profile",
        "description": "Look up a company's profile including market cap, sector, industry, description, CEO, number of employees, and key financial ratios. Use this to get fresh data about any publicly traded company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. AAPL, TSLA, SOFI)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "lookup_fundamentals",
        "description": "Look up a company's quarterly financial data including revenue, shares outstanding, free cash flow, stock-based compensation, and cash on hand. Returns the most recent quarters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "quarters": {
                    "type": "integer",
                    "description": "Number of quarters to fetch (default 8, max 20)",
                    "default": 8
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "lookup_stock_price",
        "description": "Look up a company's historical stock prices. Returns daily close prices and volume.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "months": {
                    "type": "integer",
                    "description": "Number of months of history (default 12, max 60)",
                    "default": 12
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "lookup_dilution_score",
        "description": "Look up a company's dilution score and SEC filings from our internal database. Only works for companies we are tracking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "search_notes",
        "description": "Search for previous research notes and memos using full-text search. Returns titles, types, and short content previews. Use get_note_detail to read the full content of a specific note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'ATM program', 'dilution risk', 'cash runway'). Leave empty to list recent notes."
                },
                "ticker": {
                    "type": "string",
                    "description": "Filter notes by company ticker (optional)"
                },
                "note_type": {
                    "type": "string",
                    "enum": ["note", "memo"],
                    "description": "Filter by note type (optional)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_note_detail",
        "description": "Get the full content of a specific note or memo by its ID. Use this after search_notes to read the full text of a relevant note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "The note ID from search_notes results"
                }
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "save_note",
        "description": "Save a new note or memo. Use this when the user asks you to write up findings, create a memo, save research, or document analysis. You write the full content in markdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title for the note or memo"
                },
                "content": {
                    "type": "string",
                    "description": "Full content in markdown format"
                },
                "note_type": {
                    "type": "string",
                    "enum": ["note", "memo"],
                    "description": "Type of note: 'note' for general notes, 'memo' for structured investment memos"
                },
                "ticker": {
                    "type": "string",
                    "description": "Company ticker to associate with this note (optional)"
                }
            },
            "required": ["title", "content", "note_type"]
        }
    },
    {
        "name": "update_note",
        "description": "Update/overwrite an existing note or memo. Use this when the user asks you to edit, revise, or update a specific note. Use get_note_detail first to read the current content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "The ID of the note to update"
                },
                "title": {
                    "type": "string",
                    "description": "New title for the note"
                },
                "content": {
                    "type": "string",
                    "description": "New full content in markdown format (replaces existing content entirely)"
                }
            },
            "required": ["note_id", "title", "content"]
        }
    },
]


# ── Tool Execution ───────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict, db: Session, fmp_api_key: str) -> str:
    """Execute a tool and return the result as a string."""
    try:
        if tool_name == "lookup_company_profile":
            return _tool_company_profile(tool_input["ticker"], fmp_api_key)
        elif tool_name == "lookup_fundamentals":
            return _tool_fundamentals(
                tool_input["ticker"],
                tool_input.get("quarters", 8),
                fmp_api_key,
            )
        elif tool_name == "lookup_stock_price":
            return _tool_stock_price(
                tool_input["ticker"],
                tool_input.get("months", 12),
                fmp_api_key,
            )
        elif tool_name == "lookup_dilution_score":
            return _tool_dilution_score(tool_input["ticker"], db)
        elif tool_name == "search_notes":
            return _tool_search_notes(
                db,
                tool_input.get("query"),
                tool_input.get("ticker"),
                tool_input.get("note_type"),
            )
        elif tool_name == "get_note_detail":
            return _tool_get_note_detail(db, tool_input["note_id"])
        elif tool_name == "save_note":
            return _tool_save_note(
                db,
                tool_input["title"],
                tool_input["content"],
                tool_input["note_type"],
                tool_input.get("ticker"),
            )
        elif tool_name == "update_note":
            return _tool_update_note(
                db,
                tool_input["note_id"],
                tool_input["title"],
                tool_input["content"],
            )
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        logger.error("Tool execution error for %s: %s", tool_name, e)
        return f"Error executing {tool_name}: {str(e)}"


def _tool_company_profile(ticker: str, fmp_api_key: str) -> str:
    fmp = FMPClient(api_key=fmp_api_key)
    profile = fmp.get_company_profile(ticker.upper())
    if not profile:
        return f"No profile found for {ticker}"

    # Extract key fields
    fields = {
        "symbol": profile.get("symbol"),
        "companyName": profile.get("companyName"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "exchange": profile.get("exchange"),
        "marketCap": profile.get("marketCap"),
        "price": profile.get("price"),
        "beta": profile.get("beta"),
        "volAvg": profile.get("volAvg"),
        "lastDividend": profile.get("lastDividend"),
        "range": profile.get("range"),
        "changes": profile.get("changes"),
        "ceo": profile.get("ceo"),
        "fullTimeEmployees": profile.get("fullTimeEmployees"),
        "description": profile.get("description", "")[:500],
    }
    return json.dumps(fields, indent=2)


def _tool_fundamentals(ticker: str, quarters: int, fmp_api_key: str) -> str:
    quarters = min(quarters, 20)
    fmp = FMPClient(api_key=fmp_api_key)
    data = fmp.get_full_fundamentals(ticker.upper(), limit=quarters)
    if not data:
        return f"No fundamental data found for {ticker}"

    # Format as markdown table
    result = f"## {ticker.upper()} Quarterly Fundamentals ({len(data)} quarters)\n\n"
    result += "| Date | Period | Shares | Revenue | FCF | SBC | Cash |\n"
    result += "|------|--------|--------|---------|-----|-----|------|\n"
    for row in data:
        result += (
            f"| {row.get('date', '--')} "
            f"| {row.get('fiscal_period', '--')} "
            f"| {_fmt_num(row.get('shares_outstanding'))} "
            f"| {_fmt_num(row.get('revenue'))} "
            f"| {_fmt_num(row.get('fcf'))} "
            f"| {_fmt_num(row.get('sbc'))} "
            f"| {_fmt_num(row.get('cash'))} |\n"
        )
    return result


def _tool_stock_price(ticker: str, months: int, fmp_api_key: str) -> str:
    months = min(months, 60)
    fmp = FMPClient(api_key=fmp_api_key)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    prices = fmp.get_historical_prices(ticker.upper(), from_date=from_date, to_date=to_date)

    if not prices:
        return f"No price data found for {ticker}"

    # Summarize rather than returning every day
    result = f"## {ticker.upper()} Stock Price ({months} months)\n\n"

    first = prices[0]
    last = prices[-1]
    first_price = first.get("close", 0)
    last_price = last.get("close", 0)
    pct_change = ((last_price - first_price) / first_price * 100) if first_price else 0

    result += f"- **Period**: {first.get('date')} to {last.get('date')}\n"
    result += f"- **Start Price**: ${first_price:.2f}\n"
    result += f"- **End Price**: ${last_price:.2f}\n"
    result += f"- **Change**: {pct_change:+.1f}%\n"

    # Find high/low
    closes = [p["close"] for p in prices if p.get("close")]
    if closes:
        result += f"- **High**: ${max(closes):.2f}\n"
        result += f"- **Low**: ${min(closes):.2f}\n"
        result += f"- **Data Points**: {len(prices)} days\n"

    # Recent 10 days
    result += "\n### Recent Prices\n\n"
    result += "| Date | Close | Volume |\n"
    result += "|------|-------|--------|\n"
    for p in prices[-10:]:
        result += f"| {p.get('date', '--')} | ${p.get('close', 0):.2f} | {_fmt_num(p.get('volume'))} |\n"

    return result


def _tool_dilution_score(ticker: str, db: Session) -> str:
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        return f"{ticker} is not tracked in our database. Use lookup_company_profile or lookup_fundamentals to get data from the financial API instead."

    score = (
        db.query(DilutionScore)
        .filter_by(company_id=company.id)
        .order_by(desc(DilutionScore.id))
        .first()
    )

    filings = (
        db.query(SecFiling)
        .filter_by(company_id=company.id)
        .order_by(desc(SecFiling.filed_date))
        .limit(15)
        .all()
    )

    result = f"## {ticker.upper()} Dilution Score\n\n"

    if score:
        result += f"- **Composite Score**: {score.composite_score:.1f}/100\n"
        result += f"- **Share CAGR Score**: {_safe_score(score.share_cagr_score)} (CAGR: {_fmt_pct(score.share_cagr_3y)})\n"
        result += f"- **FCF Burn Score**: {_safe_score(score.fcf_burn_score)} (Rate: {_fmt_pct(score.fcf_burn_rate)})\n"
        result += f"- **SBC/Revenue Score**: {_safe_score(score.sbc_revenue_score)} (Ratio: {_fmt_pct(score.sbc_revenue_pct)})\n"
        result += f"- **Offering Freq Score**: {_safe_score(score.offering_freq_score)} ({score.offering_count_3y or 0} filings in 3y)\n"
        result += f"- **Cash Runway Score**: {_safe_score(score.cash_runway_score)} ({_safe_months(score.cash_runway_months)} months)\n"
        result += f"- **ATM Active Score**: {_safe_score(score.atm_active_score)} (Active: {score.atm_program_active})\n"
        result += f"- **12M Price Change**: {_fmt_pct(score.price_change_12m)}\n"
    else:
        result += "No dilution score computed yet.\n"

    if filings:
        result += f"\n### SEC Filings ({len(filings)} most recent)\n\n"
        result += "| Date | Type | Dilutive | Dilution Type | Amount |\n"
        result += "|------|------|----------|---------------|--------|\n"
        for f in filings:
            result += (
                f"| {f.filed_date} | {f.filing_type} "
                f"| {'Yes' if f.is_dilution_event else 'No'} "
                f"| {f.dilution_type or '--'} "
                f"| {_fmt_num(f.offering_amount_dollars)} |\n"
            )

    return result


def _tool_search_notes(db: Session, query: str = None, ticker: str = None, note_type: str = None) -> str:
    from sqlalchemy import text as sql_text

    PREVIEW_LENGTH = 400

    if query and query.strip():
        from backend.database import is_sqlite
        params = {"query": query.strip()}
        where_clauses = []
        if ticker:
            where_clauses.append("n.ticker = :ticker")
            params["ticker"] = ticker.upper()
        if note_type:
            where_clauses.append("n.note_type = :note_type")
            params["note_type"] = note_type

        extra_where = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

        if is_sqlite():
            # Use FTS5 full-text search on SQLite
            rows = db.execute(
                sql_text(f"""
                    SELECT n.id, n.title, n.note_type, n.ticker, n.updated_at,
                           SUBSTR(n.content, 1, :preview_len) as preview,
                           LENGTH(n.content) as content_length
                    FROM notes_fts fts
                    JOIN notes n ON n.id = fts.rowid
                    WHERE notes_fts MATCH :query{extra_where}
                    ORDER BY rank
                    LIMIT 10
                """),
                {**params, "preview_len": PREVIEW_LENGTH},
            ).fetchall()
        else:
            # Use ILIKE on PostgreSQL
            like_param = f"%{query.strip()}%"
            params["like_query"] = like_param
            rows = db.execute(
                sql_text(f"""
                    SELECT n.id, n.title, n.note_type, n.ticker, n.updated_at,
                           SUBSTRING(n.content FROM 1 FOR :preview_len) as preview,
                           LENGTH(n.content) as content_length
                    FROM notes n
                    WHERE (n.title ILIKE :like_query OR n.content ILIKE :like_query){extra_where}
                    ORDER BY n.updated_at DESC
                    LIMIT 10
                """),
                {**params, "preview_len": PREVIEW_LENGTH},
            ).fetchall()
    else:
        # No query — list recent notes
        orm_query = db.query(Note)
        if ticker:
            orm_query = orm_query.filter(Note.ticker == ticker.upper())
        if note_type:
            orm_query = orm_query.filter(Note.note_type == note_type)
        notes = orm_query.order_by(desc(Note.updated_at)).limit(10).all()
        rows = [
            (n.id, n.title, n.note_type, n.ticker, n.updated_at,
             n.content[:PREVIEW_LENGTH], len(n.content))
            for n in notes
        ]

    if not rows:
        filter_desc = ""
        if query:
            filter_desc += f" matching '{query}'"
        if ticker:
            filter_desc += f" for {ticker.upper()}"
        if note_type:
            filter_desc += f" of type '{note_type}'"
        return f"No notes found{filter_desc}."

    result = f"## Found {len(rows)} note(s)\n\n"
    result += "Use `get_note_detail` with a note ID to read the full content.\n\n"
    for row in rows:
        note_id, title, ntype, nticker, updated, preview, content_len = row
        truncated = "..." if content_len > PREVIEW_LENGTH else ""
        result += f"### [{note_id}] {title}\n"
        result += f"- **Type**: {ntype} | **Ticker**: {nticker or 'General'} | **Updated**: {updated}\n"
        result += f"- **Length**: {content_len} chars\n"
        result += f"\n> {preview}{truncated}\n\n---\n\n"

    return result


def _tool_get_note_detail(db: Session, note_id: int) -> str:
    note = db.query(Note).get(note_id)
    if not note:
        return f"Note {note_id} not found."

    result = f"## {note.title}\n"
    result += f"- **Type**: {note.note_type}\n"
    result += f"- **Ticker**: {note.ticker or 'General'}\n"
    result += f"- **Created**: {note.created_at}\n"
    result += f"- **Updated**: {note.updated_at}\n\n"
    result += note.content
    return result


def _tool_save_note(db: Session, title: str, content: str, note_type: str, ticker: str = None) -> str:
    note = Note(
        title=title,
        content=content,
        note_type=note_type,
        ticker=ticker.upper() if ticker else None,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return f"Saved {note_type} '{title}' (ID: {note.id})"


def _tool_update_note(db: Session, note_id: int, title: str, content: str) -> str:
    note = db.query(Note).get(note_id)
    if not note:
        return f"Note {note_id} not found."
    note.title = title
    note.content = content
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return f"Updated {note.note_type} '{title}' (ID: {note.id})"


def _fts_upsert(db: Session, note: Note):
    """Insert or update the FTS index for a note (SQLite only)."""
    from backend.database import is_sqlite
    from sqlalchemy import text as sql_text
    if not is_sqlite():
        return
    db.execute(sql_text("DELETE FROM notes_fts WHERE rowid = :id"), {"id": note.id})
    db.execute(
        sql_text(
            "INSERT INTO notes_fts(rowid, title, content, ticker, note_type) "
            "VALUES (:id, :title, :content, :ticker, :note_type)"
        ),
        {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "ticker": note.ticker or "",
            "note_type": note.note_type,
        },
    )


# ── Helper formatters ────────────────────────────────────────────────

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


def _safe_score(v) -> str:
    return f"{v:.1f}" if v is not None else "N/A"


def _safe_months(v) -> str:
    return f"{v:.0f}" if v is not None else "N/A"


# ── Context Builder ──────────────────────────────────────────────────

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
        share_cagr_score=_safe_score(score.share_cagr_score) if score else "N/A",
        fcf_burn_score=_safe_score(score.fcf_burn_score) if score else "N/A",
        sbc_revenue_score=_safe_score(score.sbc_revenue_score) if score else "N/A",
        offering_freq_score=_safe_score(score.offering_freq_score) if score else "N/A",
        cash_runway_score=_safe_score(score.cash_runway_score) if score else "N/A",
        atm_active_score=_safe_score(score.atm_active_score) if score else "N/A",
        share_cagr_3y=_fmt_pct(score.share_cagr_3y) if score else "N/A",
        fcf_burn_rate=_fmt_pct(score.fcf_burn_rate) if score else "N/A",
        sbc_revenue_pct=_fmt_pct(score.sbc_revenue_pct) if score else "N/A",
        offering_count_3y=score.offering_count_3y if score else "N/A",
        cash_runway_months=_safe_months(score.cash_runway_months) if score else "N/A",
        atm_program_active=score.atm_program_active if score else "N/A",
        price_change_12m=_fmt_pct(score.price_change_12m) if score else "N/A",
        fundamentals_table=fundamentals_table,
        filings_table=filings_table,
    )


# ── LLM Client ───────────────────────────────────────────────────────

class LLMClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def stream_with_tools(
        self,
        messages: list[dict],
        system_prompt: str,
        db: Session,
        fmp_api_key: str,
    ) -> Generator[dict, None, None]:
        """
        Handle tool-use loop with Claude. Yields SSE events:
        - {"type": "tool_use", "tool": "...", "input": {...}} — tool being called
        - {"type": "chunk", "content": "..."} — text chunk from final response
        - {"type": "done", "content": "..."} — final complete response
        """
        current_messages = list(messages)
        max_tool_rounds = 5  # prevent infinite loops

        # Combine custom tools with Anthropic's server-side web search
        all_tools = TOOLS + [{"type": "web_search_20250305", "name": "web_search"}]

        for _round in range(max_tool_rounds):
            # Call Claude (non-streaming to detect tool use)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=current_messages,
                tools=all_tools,
            )

            # Separate block types:
            # - tool_use: custom tools we execute ourselves
            # - server_tool_use: server-side tools (web_search) already executed
            # - text: final text response
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            server_tool_blocks = [b for b in response.content if b.type == "server_tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            # Notify frontend about any web searches that happened
            for stb in server_tool_blocks:
                yield {
                    "type": "tool_use",
                    "tool": "web_search",
                    "input": getattr(stb, "input", {}),
                }

            if not tool_use_blocks:
                # No custom tool calls — this is the final response, stream it
                final_text = "".join(b.text for b in text_blocks)
                # Yield in chunks to simulate streaming
                chunk_size = 20
                for i in range(0, len(final_text), chunk_size):
                    yield {"type": "chunk", "content": final_text[i:i + chunk_size]}
                yield {"type": "done", "content": final_text}
                return

            # Has custom tool calls — execute them
            # Add Claude's full response to messages (includes server tool blocks)
            current_messages.append({
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            })

            # Execute each custom tool and add results
            tool_results = []
            for tool_block in tool_use_blocks:
                # Notify frontend about tool usage
                yield {
                    "type": "tool_use",
                    "tool": tool_block.name,
                    "input": tool_block.input,
                }

                result = execute_tool(
                    tool_block.name,
                    tool_block.input,
                    db,
                    fmp_api_key,
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                })

            current_messages.append({
                "role": "user",
                "content": tool_results,
            })

        # If we hit max rounds, yield whatever text we have
        yield {"type": "chunk", "content": "I've gathered the available data. "}
        yield {"type": "done", "content": "I've gathered the available data but hit the maximum number of lookups. Please ask a more specific question."}

    def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> Generator[str, None, None]:
        """Simple streaming without tools (used for memo generation)."""
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
