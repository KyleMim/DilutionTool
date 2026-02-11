# Dilution Monitor

Automated surveillance system that identifies public companies engaged in consistent shareholder dilution through equity issuance.

![Screenshot placeholder](screenshot.png)

## What It Does

- Screens the US equity universe (~10,000 stocks) for dilution signals
- Scores companies on a composite model using 6 weighted factors
- Monitors SEC filings for equity offerings, ATM programs, and convertible notes
- Interactive dashboard with configurable thresholds and scoring weights

## Scoring Model

| Signal | Weight | What It Measures |
|---|---|---|
| Share CAGR | 25% | Annualized diluted share count growth over 3 years |
| FCF Burn | 20% | Trailing 4Q avg negative FCF / market cap (annualized, outlier-filtered) |
| SBC / Revenue | 15% | Stock-based compensation as a percentage of revenue (trailing 4Q) |
| Offering Frequency | 20% | Count of dilutive SEC filings in the last 3 years |
| Cash Runway | 10% | Months of cash at trailing 4Q burn rate (outlier-filtered) |
| ATM Active | 10% | Whether the company has an active ATM or shelf registration |

Each sub-score ranges from 0-100. The composite score is a weighted average, with automatic renormalization when data is missing.

**Severity tiers:**
- **Critical** (75+): Active, aggressive dilution
- **High** (50-74): Significant dilution risk
- **Moderate** (25-49): On watchlist, warrants monitoring
- **Low** (<25): Minimal dilution signals

## Stock Price Tracking

The screener table includes a **Price 12M** column showing each company's trailing 12-month stock price change, adjusted for splits. This gives immediate context on how dilution is affecting shareholder value.

**How it works:**
- During backfill, `fmp_client.get_price_change_12m()` fetches split-adjusted daily close prices from FMP's `/historical-price-eod/full` endpoint and computes the percentage change over 12 months
- The result is stored in `DilutionScore.price_change_12m` (decimal, e.g. -0.35 = -35%)
- The screener displays it as a color-coded column (green for positive, red for negative), sortable

**Company detail price chart:**
- When a user clicks into a company, the detail page shows an interactive stock price chart (Recharts AreaChart)
- Time range toggles: 3M, 6M, 12M, 24M
- Chart color adapts: green gradient when price is up over the period, red when down
- Price data is fetched on demand via `GET /api/companies/{ticker}/prices?months=N` which proxies FMP's historical price API

**Files changed:**
| File | Change |
|---|---|
| `backend/services/fmp_client.py` | Added `get_historical_prices()` and `get_price_change_12m()` |
| `backend/models.py` | Added `price_change_12m` column to `DilutionScore` |
| `backend/database.py` | Auto-migration adds column to existing tables |
| `backend/main.py` | New `GET /api/companies/{ticker}/prices` endpoint; `price_change_12m` in all response models |
| `backend/pipelines/backfill.py` | Step 4b fetches and stores 12M price change after scoring |
| `frontend/src/api/client.ts` | Added `PricePoint` type and `fetchCompanyPrices()` |
| `frontend/src/pages/Screener.tsx` | Added sortable "Price 12M" column with color-coded display |
| `frontend/src/pages/CompanyDetail.tsx` | Added stock price AreaChart with 3M/6M/12M/24M toggles |

## Architecture

This is a portfolio/demo version. The backend is a single-process FastAPI server with SQLite.

**For the full production design** (Celery workers, real-time filing monitor, PostgreSQL, alerting, cloud deployment), see [ARCHITECTURE.md](ARCHITECTURE.md) (if available).

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Recharts
- **Data:** Financial Modeling Prep API, SEC EDGAR

## Data Sources

- **Financial Modeling Prep (FMP):** Financials, share counts, market cap, income/cashflow/balance sheet data
- **SEC EDGAR:** Company CIK lookup, recent filings (S-3, 424B5, 8-K), filing text classification for dilution events

## Quick Start

### Local Development

```bash
# Clone the repo
git clone <repo-url>
cd monitor

# Set up environment
cp .env.example .env
# Edit .env and add your FMP_API_KEY (get one at https://financialmodelingprep.com/developer)

# Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Run everything
python run.py
```

Or use the Makefile:

```bash
make setup    # Install all dependencies
python run.py # Start servers (auto-backfills if no data)
```

### Production Build

```bash
make build    # Build frontend for production
make prod     # Run production server locally (serves built React app from FastAPI)
```

## Full Backfill

The quick start screens 500 companies. To scan the full universe:

```bash
python -m backend.pipelines.backfill              # Full run (~10,000 companies)
python -m backend.pipelines.backfill --resume      # Resume an interrupted run
python -m backend.pipelines.backfill --score-only  # Rescore using existing DB data (no API calls)
```

## Data Validation

Source API data (FMP) occasionally contains erroneous values. The validation tool detects and optionally corrects outliers:

```bash
python -m backend.pipelines.validate               # Scan & report outliers
python -m backend.pipelines.validate --ticker NNE   # Check a single company
python -m backend.pipelines.validate --fix          # Fix via web search (interactive)
python -m backend.pipelines.validate --fix --yes    # Auto-fix all
```

See [docs/scoring-data-quality.md](docs/scoring-data-quality.md) for details on the outlier detection methodology.

## API Documentation

FastAPI auto-generates interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs) when the server is running.

**Key endpoints:**
| Endpoint | Description |
|---|---|
| `GET /api/companies` | List companies with scores, filters, sorting, pagination |
| `GET /api/companies/{ticker}` | Company detail with score breakdown + financials |
| `GET /api/companies/{ticker}/history` | Time series data for charts |
| `GET /api/companies/{ticker}/filings` | SEC filings for a company |
| `GET /api/companies/{ticker}/prices?months=12` | Trailing split-adjusted daily prices (via FMP) |
| `GET /api/screener` | Dynamic threshold filtering |
| `GET /api/stats` | Dashboard summary statistics |
| `GET/PUT /api/config/thresholds` | View/update scoring thresholds |
| `GET/PUT /api/config/weights` | View/update scoring weights |

## Project Structure

```
monitor/
├── run.py                        # One-command entry point
├── Makefile                      # Convenience commands
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── backend/
│   ├── main.py                   # FastAPI app + all endpoints
│   ├── database.py               # SQLite + SQLAlchemy setup
│   ├── models.py                 # DB models (Company, Fundamentals, Filing, Score)
│   ├── config.py                 # Thresholds, weights, env vars
│   ├── services/
│   │   ├── fmp_client.py         # Financial Modeling Prep API client
│   │   ├── edgar_client.py       # SEC EDGAR client + filing classifier
│   │   └── scoring.py            # Composite dilution scoring engine
│   ├── pipelines/
│   │   ├── backfill.py           # Universe screen + data load + scoring (--score-only for rescore)
│   │   └── validate.py           # Outlier detection + web-search correction CLI
│   └── tests/
│       ├── test_fmp_client.py    # 15 tests
│       ├── test_edgar_client.py  # 20 tests
│       └── test_scoring.py       # 18 tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Layout + routing
│   │   ├── api/client.ts         # Typed API client
│   │   ├── pages/
│   │   │   ├── Screener.tsx      # Main table with stats + sector filters
│   │   │   ├── CompanyDetail.tsx # Score breakdown + charts + filings
│   │   │   └── Config.tsx        # Threshold + weight sliders
│   │   └── components/
│   │       ├── ScoreBadge.tsx    # Color-coded score badge
│   │       └── SparklineChart.tsx# Inline SVG sparkline
│   └── index.html
└── data/
    └── dilution_monitor.db       # SQLite database (gitignored)
```

## Deployment

This app is ready for deployment on Render, Railway, or your own server. See **[DEPLOY.md](DEPLOY.md)** for full deployment instructions.

**Quick deploy to Render:**
1. Push to GitHub
2. Connect repo to Render (auto-detects `render.yaml`)
3. Set `FMP_API_KEY` and `ANTHROPIC_API_KEY` environment variables
4. Deploy! The FastAPI server automatically serves the built React app.

The free tier works but has limitations (ephemeral storage, 512MB RAM). See [DEPLOY.md](DEPLOY.md) for production setup with PostgreSQL and persistent storage.

## What I'd Add for Production

- **Celery + Redis** for background job scheduling (backfill, re-scoring)
- **Real-time SEC filing monitor** polling EDGAR every 15 minutes for new filings
- **Multi-channel alerting** — Slack, email, SMS when a company crosses a threshold
- **PostgreSQL** for production-grade persistence and concurrent access
- **LLM-based filing classifier** instead of keyword matching for higher accuracy
- **Stock split normalization** for share count data (price data already uses split-adjusted closes)
- **Historical scoring** to track score changes over time and generate trend alerts
- **Deployment on Render/Railway** with CI/CD pipeline
- **User authentication** and saved watchlists per user
