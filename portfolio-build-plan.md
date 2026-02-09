# Dilution Monitor — Portfolio Build Plan

## What You're Building

A Python + React application that screens the US equity universe for companies engaged in consistent shareholder dilution, scores them on a composite model, and presents the results in a polished interactive dashboard.

**Stack:** Python 3.12 · FastAPI · SQLite · React + TypeScript · Recharts
**Data:** Financial Modeling Prep API (free tier or $30/mo plan)
**Runs locally:** `python run.py` starts everything

---

## Repo Structure

```
dilution-monitor/
├── README.md                  ← Architecture overview, screenshots, how to run
├── ARCHITECTURE.md            ← Full production system design (already written)
├── run.py                     ← One-command entry point
├── backend/
│   ├── main.py                ← FastAPI app
│   ├── database.py            ← SQLite + SQLAlchemy setup
│   ├── models.py              ← All DB models
│   ├── config.py              ← Thresholds, weights, env vars
│   ├── services/
│   │   ├── fmp_client.py      ← Financial Modeling Prep API client
│   │   ├── edgar_client.py    ← SEC EDGAR client + filing classifier
│   │   └── scoring.py         ← Composite dilution scoring engine
│   ├── pipelines/
│   │   ├── backfill.py        ← Universe screen + initial data load
│   │   └── score_all.py       ← Score every tracked company
│   ├── api/
│   │   ├── companies.py       ← Company endpoints
│   │   ├── screener.py        ← Screener endpoint
│   │   └── config.py          ← Threshold/weight endpoints
│   └── tests/
│       ├── test_scoring.py
│       ├── test_fmp_client.py
│       └── test_classifier.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Screener.tsx
│   │   │   ├── CompanyDetail.tsx
│   │   │   └── Config.tsx
│   │   ├── components/
│   │   │   ├── ScoreBadge.tsx
│   │   │   ├── SparklineChart.tsx
│   │   │   ├── ShareCountChart.tsx
│   │   │   └── ThresholdSlider.tsx
│   │   └── api/
│   │       └── client.ts       ← API fetch wrapper
│   └── index.html
├── data/
│   └── dilution_monitor.db    ← SQLite database (gitignored)
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Phase 1: Database & Models

**Claude Code Prompt:**
```
Create a Python project called dilution-monitor.

Set up SQLite via SQLAlchemy 2.0 (synchronous is fine) in backend/database.py.
DB file path: data/dilution_monitor.db (create data/ dir if needed).

Define models in backend/models.py:

1. Company
   - id, ticker (unique), cik, name, sector, exchange, market_cap
   - tracking_tier: "watchlist" | "monitoring" | "inactive"
   - created_at, updated_at

2. FundamentalsQuarterly
   - id, company_id FK, fiscal_period (e.g. "2024-Q3"), fiscal_year, quarter
   - shares_outstanding_diluted, free_cash_flow, stock_based_compensation
   - revenue, cash_and_equivalents
   - unique constraint on (company_id, fiscal_period)

3. SecFiling
   - id, company_id FK, accession_number (unique)
   - filing_type, filed_date, filing_url
   - is_dilution_event (bool), dilution_type (nullable)
   - offering_amount_dollars (nullable)

4. DilutionScore
   - id, company_id FK, score_date
   - composite_score
   - share_cagr_score, fcf_burn_score, sbc_revenue_score
   - offering_freq_score, cash_runway_score, atm_active_score
   - share_cagr_3y, fcf_burn_rate, sbc_revenue_pct
   - offering_count_3y, cash_runway_months, atm_program_active

Create backend/config.py that loads from environment variables with defaults:
- FMP_API_KEY (required)
- EDGAR_USER_AGENT (default: "DilutionMonitor dev@example.com")
- DB_PATH (default: "data/dilution_monitor.db")
- Scoring thresholds and weights as a dataclass with defaults matching our architecture doc

Add auto-create-tables on startup.
Add .env.example and .gitignore (ignore .env, data/*.db, __pycache__, node_modules).
Add requirements.txt: fastapi, uvicorn, sqlalchemy, httpx, python-dotenv, pydantic
```

**Time: ~1 hour**

---

## Phase 2: FMP Client

**Claude Code Prompt:**
```
Create backend/services/fmp_client.py.

Use httpx (async-capable but we'll use sync for simplicity).
Base URL: https://financialmodelingprep.com/api/v3
API key from config.

Implement with retry logic (3 retries, exponential backoff) and rate limiting
(sleep 0.25s between calls to stay under 300/min):

1. get_stock_list() -> list[dict]
   GET /stock/list?apikey={key}
   Return: list of {ticker, name, sector, exchange, market_cap, type}
   Filter to US exchanges and type="stock" on the client side.

2. get_income_statements(ticker, period="quarter", limit=12) -> list[dict]
   GET /income-statement/{ticker}?period=quarter&limit=12&apikey={key}
   Extract: date, period, weightedAverageShsOutDil, revenue, operatingIncome

3. get_cashflow_statements(ticker, period="quarter", limit=12) -> list[dict]
   GET /cash-flow-statement/{ticker}?period=quarter&limit=12&apikey={key}
   Extract: date, period, freeCashFlow, stockBasedCompensation

4. get_balance_sheets(ticker, period="quarter", limit=12) -> list[dict]
   GET /balance-sheet-statement/{ticker}?period=quarter&limit=12&apikey={key}
   Extract: date, period, cashAndCashEquivalents

5. get_company_profile(ticker) -> dict
   GET /profile/{ticker}?apikey={key}

6. get_full_fundamentals(ticker, limit=12) -> dict
   Calls 2, 3, 4 above and merges by period into a unified list of quarterly records.
   Each record has: fiscal_period, shares_outstanding, fcf, sbc, revenue, cash

Add logging for every API call. 
Write tests in backend/tests/test_fmp_client.py using unittest.mock to mock httpx responses.
Include 2-3 realistic mock responses based on actual FMP data shapes.
```

**Time: ~1 hour**

---

## Phase 3: EDGAR Client & Filing Classifier

**Claude Code Prompt:**
```
Create backend/services/edgar_client.py.

Use httpx. Set User-Agent header from config.EDGAR_USER_AGENT.
Rate limit: sleep 0.12s between requests (max 10/sec to sec.gov).

Implement:

1. lookup_cik(ticker) -> str | None
   Use SEC company tickers JSON: https://www.sec.gov/files/company_tickers.json
   Cache the full mapping in memory on first call.
   Return zero-padded 10-digit CIK string.

2. get_recent_filings(cik, filing_types=["S-3", "S-3/A", "424B5", "8-K"], limit=20) -> list[dict]
   GET https://data.sec.gov/submissions/CIK{cik}.json
   Parse the "recent" filings from the response.
   Filter by form type. Return: accession_number, form, filingDate, primaryDocument URL.

3. classify_filing(filing_type, primary_doc_url) -> dict
   For S-3 filings: automatically flag as potential dilution (atm_shelf).
   For 424B5: fetch the document text (first 5000 chars), run keyword classifier.
   For 8-K: fetch document text, run keyword classifier.
   
   Keyword classifier searches for these patterns:
   - "at-the-market" or "ATM" -> type: "atm"
   - "registered direct" -> type: "registered_direct"
   - "public offering" + "underwriting" -> type: "follow_on"
   - "convertible" + "note" -> type: "convertible"
   - "private placement" or "PIPE" -> type: "pipe"
   - Dollar amount regex near offering keywords: r'\$[\d,.]+ (?:million|billion)'
   
   Return: {is_dilution_event: bool, dilution_type: str|None, offering_amount: float|None, confidence: float}

Write tests with sample filing text snippets for each dilution type.
Test the classifier against at least 5 realistic text samples.
```

**Time: ~1.5 hours**

---

## Phase 4: Scoring Engine

**Claude Code Prompt:**
```
Create backend/services/scoring.py.

The scoring engine computes a composite dilution score (0-100) for a company
using data from the database.

Accept a ScoringConfig dataclass with weights and thresholds (from backend/config.py).

Implement score_company(db_session, company_id, config) -> DilutionScore:

Pull the company's last 12 quarters of fundamentals and all sec_filings.

Calculate each sub-score (0-100):

1. share_cagr_score:
   Take oldest and newest shares_outstanding from fundamentals.
   CAGR = (newest/oldest)^(4/num_quarters) - 1 (annualized).
   Score = min(cagr / 0.50 * 100, 100). So 50% annual growth = max score.

2. fcf_burn_score:
   Average quarterly FCF (only negative quarters) / market_cap * 4 (annualized).
   Score = min(abs(rate) / 0.70 * 100, 100).
   If no negative FCF quarters, score = 0.

3. sbc_revenue_score:
   Trailing 4Q sum of SBC / trailing 4Q sum of revenue.
   Score = min(ratio / 0.60 * 100, 100).
   If revenue <= 0 and SBC > 0, score = 100.

4. offering_freq_score:
   Count sec_filings where is_dilution_event=True in last 3 years.
   Score = min(count / 7 * 100, 100).

5. cash_runway_score:
   Latest cash / abs(avg quarterly FCF burn).
   Months = quarters * 3.
   Score = max(0, (24 - months) / 24 * 100).
   If FCF >= 0, score = 0.

6. atm_active_score:
   Any S-3 or ATM-classified filing in last 2 years? 100 : 0.

Composite = weighted average using config weights. If a sub-score can't be
calculated (missing data), exclude its weight and renormalize.

Save result to dilution_scores table. Return the DilutionScore model instance.

Also implement:
- score_all(db_session, config) -> list[DilutionScore] — scores every watchlist company
- get_latest_scores(db_session) -> list of (Company, DilutionScore) joined

Write thorough tests:
- Test with a company that should score high (serial diluter)
- Test with a company that should score low (cash flow positive, stable shares)
- Test missing data handling (company with only 2 quarters of history)
- Test weight renormalization when sub-scores are missing
```

**Time: ~1.5 hours**

---

## Phase 5: Backfill Pipeline

**Claude Code Prompt:**
```
Create backend/pipelines/backfill.py.

This is the main data pipeline. It screens the universe, loads data, and scores.

Implement run_backfill(db_session, fmp_client, edgar_client, config, 
                       max_companies=3000, quick_mode=False):

Step 1: Pull universe
- Call fmp_client.get_stock_list()
- Filter: US exchanges, type=stock, market_cap > 0
- Insert/update all into companies table as tier="inactive"
- Log: "Loaded {n} US equities"

Step 2: Quick screen
- For each company (with progress bar using print or tqdm):
  - Pull income statements (just need shares_outstanding over time)
  - Pull cashflow statements (just need FCF)
  - Calculate rough 3-year share CAGR
  - Count negative FCF quarters out of last 8
  - If share_cagr > config.share_cagr_min OR neg_fcf_quarters >= config.fcf_negative_quarters:
    mark as candidate
- If quick_mode=True, only screen first 500 companies (for testing)
- Log: "Screened {n} companies, {m} candidates identified"

Step 3: Enrich candidates
- For each candidate:
  - Pull full fundamentals via fmp_client.get_full_fundamentals()
  - Store all quarters in fundamentals_quarterly (upsert on company_id + fiscal_period)
  - Look up CIK via edgar_client.lookup_cik()
  - Pull recent filings via edgar_client.get_recent_filings()
  - Classify each filing
  - Store in sec_filings table (upsert on accession_number)
- Log: "Enriched {n} candidates"

Step 4: Score
- Run scoring.score_all()
- Companies with composite >= 25: set tier="watchlist"
- Rest of candidates: set tier="monitoring"
- Log: "Watchlist: {n} companies, Monitoring: {m} companies"
- Print top 10 by score as a formatted table

Add CLI entry point:
  python -m backend.pipelines.backfill [--quick] [--max-companies 500]

Handle interruptions gracefully — commit to DB after each company so progress 
isn't lost if the process is killed. Add a --resume flag that skips already-enriched companies.
```

**Time: ~2 hours**

---

## Phase 6: FastAPI Backend

**Claude Code Prompt:**
```
Create the FastAPI app in backend/main.py.

On startup: create DB tables if they don't exist, load config.

Routes:

GET /api/companies
  Query params: sector, min_score, max_score, tier, sort_by (default: composite_score), 
  sort_dir (default: desc), limit (default: 50), offset (default: 0)
  Returns: list of companies joined with their latest dilution_score
  Include: ticker, name, sector, market_cap, tracking_tier, and all score fields

GET /api/companies/{ticker}
  Returns: company profile + latest score breakdown + latest 8 quarters of fundamentals

GET /api/companies/{ticker}/history
  Returns: quarterly fundamentals + scores over time (for charts)

GET /api/companies/{ticker}/filings
  Returns: all SEC filings for this company, ordered by date desc

GET /api/screener
  Query params: all threshold overrides (share_cagr_min, sbc_revenue_min, etc.)
  Applies filters on top of scored data and returns matching companies
  This lets the frontend filter dynamically without re-scoring

GET /api/screener/sectors
  Returns: list of {sector, count} for filter tabs

GET /api/config/thresholds
  Returns current thresholds

PUT /api/config/thresholds
  Updates thresholds in memory (not persisted to DB for the portfolio version — 
  resets on restart, which is fine)

GET /api/config/weights  
PUT /api/config/weights
  Same pattern for scoring weights

GET /api/stats
  Returns: total_companies, watchlist_count, critical_count (score >= 75), 
  avg_score, sectors breakdown

Add CORS middleware allowing localhost:5173 (Vite dev server).
Use Pydantic response models for all endpoints.
Add a root route GET / that returns {"status": "ok", "version": "1.0.0"}.
```

**Time: ~2 hours**

---

## Phase 7: React Dashboard

**Claude Code Prompt:**
```
Create a React + TypeScript frontend in /frontend using Vite.

npm create vite@latest frontend -- --template react-ts
Install: tailwindcss, recharts, react-router-dom, @tanstack/react-query

Configure Tailwind with a custom dark theme:
  colors: { surface: "#0f172a", panel: "#0b1120", border: "#1e293b", 
  accent: "#6366f1", danger: "#ef4444", warning: "#f59e0b" }

Google Fonts: JetBrains Mono (data/numbers), IBM Plex Sans (body text)

API client in src/api/client.ts:
  Base URL from import.meta.env.VITE_API_URL || "http://localhost:8000"
  Simple fetch wrapper with JSON parsing.

React Query setup in App.tsx with 60-second refetch interval.

Pages (use React Router):

1. Screener (/) — src/pages/Screener.tsx
   - Stats bar: 4 cards (tracked, flagged, critical, avg score) from GET /api/stats
   - Sector filter tabs from GET /api/screener/sectors
   - Data table from GET /api/companies with:
     - Columns: Company (ticker + name), Score (color-coded badge), 
       Share CAGR 3Y, Sparkline (tiny SVG from share history), 
       FCF Burn, SBC/Rev, Offerings, Runway, ATM status
     - Sortable columns (client-side sort is fine)
     - Click row -> navigate to /company/{ticker}
   - Style the table to match the prototype I showed you earlier:
     dark background, monospace numbers, red/amber/green score badges,
     subtle row hover, sparkline charts inline

2. Company Detail (/company/:ticker) — src/pages/CompanyDetail.tsx
   - Back button
   - Header: ticker, name, score badge, severity label, sector, price, market cap
   - Score breakdown: 6 cards in a grid, each showing sub-score (big number + color),
     label, and the underlying metric
   - Two charts side by side:
     - Shares Outstanding over time (Recharts AreaChart, red gradient)
     - Free Cash Flow over time (Recharts BarChart, red for negative)
   - Filing timeline: vertical list of offerings with date, type badge 
     (color-coded by type), and dollar amount
   Data from: GET /api/companies/{ticker}, GET /api/companies/{ticker}/history,
   GET /api/companies/{ticker}/filings

3. Config (/config) — src/pages/Config.tsx
   - Two tabs: Thresholds and Weights
   - Slider for each parameter (range input styled with accent color)
   - Each slider shows: label, current value, description, min/max
   - Live preview panel on the right: bar chart showing all companies' scores,
     highlighted if they pass current thresholds. Updates on every slider change.
   - Save button: PUT to /api/config/thresholds or /api/config/weights
   - Reset defaults button

Navigation: left sidebar, minimal, with icons for Screener, Config.
Active page highlighted with accent color.

The overall aesthetic should feel like a Bloomberg terminal meets a modern SaaS dashboard.
Dark, data-dense, professional. Use the exact color palette from the prototype.
```

**Time: ~3 hours**

---

## Phase 8: run.py & README

**Claude Code Prompt:**
```
Create run.py at the project root.

This is the single entry point that does everything:

import subprocess, sys, os

1. Check that .env exists and FMP_API_KEY is set. If not, print instructions and exit.
2. Check if data/dilution_monitor.db exists. 
   If not, print "No data found. Running initial backfill..." 
   and run the backfill pipeline in quick mode (500 companies).
3. Start the FastAPI server on port 8000 in a background thread.
4. Check if frontend/node_modules exists. If not, run npm install.
5. Print instructions: 
   "Dashboard: http://localhost:5173"
   "API docs: http://localhost:8000/docs"
   "To load full universe: python -m backend.pipelines.backfill"
6. Start the Vite dev server on port 5173 (foreground process).

Also create a Makefile:
  make setup     — pip install -r requirements.txt && cd frontend && npm install
  make backfill  — python -m backend.pipelines.backfill
  make quick     — python -m backend.pipelines.backfill --quick --max-companies 500
  make api       — uvicorn backend.main:app --reload --port 8000
  make frontend  — cd frontend && npm run dev
  make dev       — run api and frontend concurrently
  make test      — pytest backend/tests/

Now create README.md:

# Dilution Monitor

One-line description: Automated surveillance system that identifies public companies 
engaged in consistent shareholder dilution through equity issuance.

## Screenshot
[screenshot placeholder — we'll add after building]

## What It Does
- Screens the US equity universe (~4000 stocks) for dilution signals
- Scores companies on a composite model using 6 weighted factors
- Monitors SEC filings for equity offerings, ATM programs, and convertible notes
- Interactive dashboard with configurable thresholds and scoring weights

## Scoring Model
Table showing the 6 signals, their weights, and what they measure.

## Architecture
Brief summary + link to ARCHITECTURE.md for the full production design.
Explain what's built (the portfolio version) vs what the production system would add
(Celery workers, real-time filing monitor, alerting, cloud deployment).

## Tech Stack
Python 3.12, FastAPI, SQLAlchemy, SQLite, React, TypeScript, Tailwind, Recharts

## Data Sources
- Financial Modeling Prep API (fundamentals, share counts)
- SEC EDGAR (filings, CIK lookup, filing classification)

## Quick Start
```
git clone ...
cp .env.example .env  # add your FMP_API_KEY
make setup
python run.py
```

## Full Backfill
```
python -m backend.pipelines.backfill  # screens ~4000 companies, takes ~2 hours
```

## API Documentation
FastAPI auto-generates docs at http://localhost:8000/docs

## Project Structure
Show the directory tree.

## What I'd Add for Production
Bullet list: Celery + Redis for background jobs, real-time SEC filing monitor polling
every 15 min, multi-channel alerting (Slack, email, SMS), PostgreSQL for production,
deployment on Render, filing classification via LLM instead of keywords,
stock split normalization. Reference ARCHITECTURE.md.
```

**Time: ~1 hour**

---

## Build Order Summary

| Phase | What | Time |
|---|---|---|
| 1 | Database & models | ~1 hr |
| 2 | FMP API client | ~1 hr |
| 3 | EDGAR client + classifier | ~1.5 hr |
| 4 | Scoring engine | ~1.5 hr |
| 5 | Backfill pipeline | ~2 hr |
| 6 | FastAPI backend | ~2 hr |
| 7 | React dashboard | ~3 hr |
| 8 | run.py + README | ~1 hr |
| **Total** | | **~13 hours** |

---

## Tips

1. **Run Phase 5 early with --quick.** Once you have real data in SQLite, everything else is easier to build and test. You'll see real scores and can sanity-check the model.

2. **Phase 7 is the longest.** Consider splitting it into two Claude Code sessions: one for the Screener page, one for CompanyDetail + Config.

3. **Take a screenshot** of the dashboard with real data for the README. A good screenshot is worth more than a paragraph of explanation in a job application.

4. **The ARCHITECTURE.md you already have is a differentiator.** It shows you've thought through production concerns (idempotent ingestion, split adjustment, filing NLP, scaling) even though you deliberately scoped the build to a portfolio demo. Interviewers notice this.

5. **Git commits matter.** Commit after each phase with a clear message. A clean git history shows discipline.
