"""
FastAPI backend for Dilution Monitor.

Endpoints:
  GET  /                           - Health check
  GET  /api/companies              - List companies with scores
  GET  /api/companies/{ticker}     - Company detail
  GET  /api/companies/{ticker}/history - Historical data
  GET  /api/companies/{ticker}/filings - SEC filings
  GET  /api/screener               - Dynamic screener
  GET  /api/screener/sectors       - Sector filter options
  GET  /api/config/thresholds      - Get scoring thresholds
  PUT  /api/config/thresholds      - Update thresholds
  GET  /api/config/weights         - Get scoring weights
  PUT  /api/config/weights         - Update weights
  GET  /api/stats                  - Dashboard stats
"""
from typing import Optional, List
from datetime import date, datetime, timedelta
import os

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from backend.config import get_config, ScoringConfig
from backend.database import SessionLocal, create_tables
from backend.models import Company, DilutionScore, FundamentalsQuarterly, SecFiling
from backend.services.fmp_client import FMPClient
from backend.api.chat import router as chat_router
from backend.api.notes import router as notes_router

app = FastAPI(title="Dilution Monitor API", version="1.0.0")
app.include_router(chat_router)
app.include_router(notes_router)

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global config (in-memory, resets on restart)
config = get_config()


@app.on_event("startup")
def startup():
    create_tables()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------ #
# Response models
# ------------------------------------------------------------------ #

class CompanyListItem(BaseModel):
    ticker: str
    name: str
    sector: Optional[str]
    market_cap: Optional[float]
    tracking_tier: str
    composite_score: Optional[float]
    share_cagr_score: Optional[float]
    fcf_burn_score: Optional[float]
    sbc_revenue_score: Optional[float]
    offering_freq_score: Optional[float]
    cash_runway_score: Optional[float]
    atm_active_score: Optional[float]
    share_cagr_3y: Optional[float]
    fcf_burn_rate: Optional[float]
    sbc_revenue_pct: Optional[float]
    offering_count_3y: Optional[int]
    cash_runway_months: Optional[float]
    atm_program_active: Optional[bool]
    price_change_12m: Optional[float]

    class Config:
        from_attributes = True


class PricePoint(BaseModel):
    date: str
    close: Optional[float]
    volume: Optional[int]


class FundamentalsItem(BaseModel):
    fiscal_period: str
    shares_outstanding_diluted: Optional[float]
    free_cash_flow: Optional[float]
    stock_based_compensation: Optional[float]
    revenue: Optional[float]
    cash_and_equivalents: Optional[float]

    class Config:
        from_attributes = True


class FilingItem(BaseModel):
    accession_number: str
    filing_type: str
    filed_date: Optional[date]
    is_dilution_event: bool
    dilution_type: Optional[str]
    offering_amount_dollars: Optional[float]

    class Config:
        from_attributes = True


class CompanyDetail(BaseModel):
    ticker: str
    name: str
    sector: Optional[str]
    exchange: Optional[str]
    market_cap: Optional[float]
    tracking_tier: str
    score: Optional[CompanyListItem]
    fundamentals: List[FundamentalsItem]

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_companies: int
    watchlist_count: int
    critical_count: int
    avg_score: Optional[float]
    sectors: List[dict]


class SectorCount(BaseModel):
    sector: str
    count: int


# ------------------------------------------------------------------ #
# Routes
# ------------------------------------------------------------------ #

@app.get("/")
def root():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/companies", response_model=List[CompanyListItem])
def list_companies(
    sector: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    tier: Optional[str] = None,
    sort_by: str = "composite_score",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    # Subquery for latest score per company
    latest_scores = (
        db.query(
            DilutionScore.company_id,
            func.max(DilutionScore.id).label("max_id")
        )
        .group_by(DilutionScore.company_id)
        .subquery()
    )

    query = (
        db.query(Company, DilutionScore)
        .join(DilutionScore, Company.id == DilutionScore.company_id)
        .join(latest_scores, DilutionScore.id == latest_scores.c.max_id)
    )

    # Filters
    if sector:
        query = query.filter(Company.sector == sector)
    if tier:
        query = query.filter(Company.tracking_tier == tier)
    if min_score is not None:
        query = query.filter(DilutionScore.composite_score >= min_score)
    if max_score is not None:
        query = query.filter(DilutionScore.composite_score <= max_score)

    # Sorting
    sort_col = getattr(DilutionScore, sort_by, DilutionScore.composite_score)
    if sort_dir == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    results = query.offset(offset).limit(limit).all()

    return [
        CompanyListItem(
            ticker=company.ticker,
            name=company.name,
            sector=company.sector,
            market_cap=company.market_cap,
            tracking_tier=company.tracking_tier,
            composite_score=score.composite_score,
            share_cagr_score=score.share_cagr_score,
            fcf_burn_score=score.fcf_burn_score,
            sbc_revenue_score=score.sbc_revenue_score,
            offering_freq_score=score.offering_freq_score,
            cash_runway_score=score.cash_runway_score,
            atm_active_score=score.atm_active_score,
            share_cagr_3y=score.share_cagr_3y,
            fcf_burn_rate=score.fcf_burn_rate,
            sbc_revenue_pct=score.sbc_revenue_pct,
            offering_count_3y=score.offering_count_3y,
            cash_runway_months=score.cash_runway_months,
            atm_program_active=score.atm_program_active,
            price_change_12m=score.price_change_12m,
        )
        for company, score in results
    ]


@app.get("/api/companies/{ticker}")
def get_company(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Latest score
    score = (
        db.query(DilutionScore)
        .filter_by(company_id=company.id)
        .order_by(desc(DilutionScore.id))
        .first()
    )

    # Latest 8 quarters
    fundamentals = (
        db.query(FundamentalsQuarterly)
        .filter_by(company_id=company.id)
        .order_by(desc(FundamentalsQuarterly.fiscal_period))
        .limit(8)
        .all()
    )

    score_data = None
    if score:
        score_data = CompanyListItem(
            ticker=company.ticker,
            name=company.name,
            sector=company.sector,
            market_cap=company.market_cap,
            tracking_tier=company.tracking_tier,
            composite_score=score.composite_score,
            share_cagr_score=score.share_cagr_score,
            fcf_burn_score=score.fcf_burn_score,
            sbc_revenue_score=score.sbc_revenue_score,
            offering_freq_score=score.offering_freq_score,
            cash_runway_score=score.cash_runway_score,
            atm_active_score=score.atm_active_score,
            share_cagr_3y=score.share_cagr_3y,
            fcf_burn_rate=score.fcf_burn_rate,
            sbc_revenue_pct=score.sbc_revenue_pct,
            offering_count_3y=score.offering_count_3y,
            cash_runway_months=score.cash_runway_months,
            atm_program_active=score.atm_program_active,
            price_change_12m=score.price_change_12m,
        )

    return {
        "ticker": company.ticker,
        "name": company.name,
        "sector": company.sector,
        "exchange": company.exchange,
        "market_cap": company.market_cap,
        "tracking_tier": company.tracking_tier,
        "score": score_data,
        "fundamentals": [FundamentalsItem.from_orm(f) for f in fundamentals]
    }


@app.get("/api/companies/{ticker}/history")
def get_company_history(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    fundamentals = (
        db.query(FundamentalsQuarterly)
        .filter_by(company_id=company.id)
        .order_by(FundamentalsQuarterly.fiscal_period.asc())
        .all()
    )

    scores = (
        db.query(DilutionScore)
        .filter_by(company_id=company.id)
        .order_by(DilutionScore.score_date.asc())
        .all()
    )

    return {
        "fundamentals": [FundamentalsItem.from_orm(f) for f in fundamentals],
        "scores": [CompanyListItem(
            ticker=company.ticker,
            name=company.name,
            sector=company.sector,
            market_cap=company.market_cap,
            tracking_tier=company.tracking_tier,
            composite_score=s.composite_score,
            share_cagr_score=s.share_cagr_score,
            fcf_burn_score=s.fcf_burn_score,
            sbc_revenue_score=s.sbc_revenue_score,
            offering_freq_score=s.offering_freq_score,
            cash_runway_score=s.cash_runway_score,
            atm_active_score=s.atm_active_score,
            share_cagr_3y=s.share_cagr_3y,
            fcf_burn_rate=s.fcf_burn_rate,
            sbc_revenue_pct=s.sbc_revenue_pct,
            offering_count_3y=s.offering_count_3y,
            cash_runway_months=s.cash_runway_months,
            atm_program_active=s.atm_program_active,
            price_change_12m=s.price_change_12m,
        ) for s in scores]
    }


@app.get("/api/companies/{ticker}/filings", response_model=List[FilingItem])
def get_company_filings(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    filings = (
        db.query(SecFiling)
        .filter_by(company_id=company.id)
        .order_by(desc(SecFiling.filed_date))
        .all()
    )

    return [FilingItem.from_orm(f) for f in filings]


@app.get("/api/companies/{ticker}/prices", response_model=List[PricePoint])
def get_company_prices(
    ticker: str,
    months: int = Query(default=12, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """Fetch trailing split-adjusted daily prices from FMP."""
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not config.fmp_api_key:
        raise HTTPException(status_code=503, detail="FMP API key not configured")

    fmp = FMPClient(api_key=config.fmp_api_key)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    prices = fmp.get_historical_prices(ticker.upper(), from_date=from_date, to_date=to_date)
    return [PricePoint(**p) for p in prices]


@app.get("/api/screener", response_model=List[CompanyListItem])
def screener(
    share_cagr_min: Optional[float] = None,
    fcf_burn_min: Optional[float] = None,
    sbc_revenue_min: Optional[float] = None,
    offering_count_min: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # Get all scored companies
    latest_scores = (
        db.query(
            DilutionScore.company_id,
            func.max(DilutionScore.id).label("max_id")
        )
        .group_by(DilutionScore.company_id)
        .subquery()
    )

    query = (
        db.query(Company, DilutionScore)
        .join(DilutionScore, Company.id == DilutionScore.company_id)
        .join(latest_scores, DilutionScore.id == latest_scores.c.max_id)
    )

    # Apply threshold filters
    if share_cagr_min is not None:
        query = query.filter(DilutionScore.share_cagr_3y >= share_cagr_min)
    if fcf_burn_min is not None:
        query = query.filter(DilutionScore.fcf_burn_rate <= fcf_burn_min)  # Negative values
    if sbc_revenue_min is not None:
        query = query.filter(DilutionScore.sbc_revenue_pct >= sbc_revenue_min)
    if offering_count_min is not None:
        query = query.filter(DilutionScore.offering_count_3y >= offering_count_min)

    results = query.order_by(desc(DilutionScore.composite_score)).limit(100).all()

    return [
        CompanyListItem(
            ticker=company.ticker,
            name=company.name,
            sector=company.sector,
            market_cap=company.market_cap,
            tracking_tier=company.tracking_tier,
            composite_score=score.composite_score,
            share_cagr_score=score.share_cagr_score,
            fcf_burn_score=score.fcf_burn_score,
            sbc_revenue_score=score.sbc_revenue_score,
            offering_freq_score=score.offering_freq_score,
            cash_runway_score=score.cash_runway_score,
            atm_active_score=score.atm_active_score,
            share_cagr_3y=score.share_cagr_3y,
            fcf_burn_rate=score.fcf_burn_rate,
            sbc_revenue_pct=score.sbc_revenue_pct,
            offering_count_3y=score.offering_count_3y,
            cash_runway_months=score.cash_runway_months,
            atm_program_active=score.atm_program_active,
            price_change_12m=score.price_change_12m,
        )
        for company, score in results
    ]


@app.get("/api/screener/sectors", response_model=List[SectorCount])
def get_sectors(db: Session = Depends(get_db)):
    results = (
        db.query(Company.sector, func.count(Company.id).label("count"))
        .filter(Company.tracking_tier.in_(["watchlist", "monitoring"]))
        .filter(Company.sector.isnot(None))
        .group_by(Company.sector)
        .order_by(desc("count"))
        .all()
    )

    return [SectorCount(sector=sector, count=count) for sector, count in results]


@app.get("/api/config/thresholds")
def get_thresholds():
    return {
        "share_cagr_min": config.scoring.share_cagr_min,
        "fcf_negative_quarters": config.scoring.fcf_negative_quarters,
        "share_cagr_ceiling": config.scoring.share_cagr_ceiling,
        "fcf_burn_ceiling": config.scoring.fcf_burn_ceiling,
        "sbc_revenue_ceiling": config.scoring.sbc_revenue_ceiling,
        "offering_freq_ceiling": config.scoring.offering_freq_ceiling,
        "cash_runway_max_months": config.scoring.cash_runway_max_months,
        "watchlist_min_score": config.scoring.watchlist_min_score,
    }


@app.put("/api/config/thresholds")
def update_thresholds(thresholds: dict):
    for key, value in thresholds.items():
        if hasattr(config.scoring, key):
            setattr(config.scoring, key, value)
    return get_thresholds()


@app.get("/api/config/weights")
def get_weights():
    return {
        "weight_share_cagr": config.scoring.weight_share_cagr,
        "weight_fcf_burn": config.scoring.weight_fcf_burn,
        "weight_sbc_revenue": config.scoring.weight_sbc_revenue,
        "weight_offering_freq": config.scoring.weight_offering_freq,
        "weight_cash_runway": config.scoring.weight_cash_runway,
        "weight_atm_active": config.scoring.weight_atm_active,
    }


@app.put("/api/config/weights")
def update_weights(weights: dict):
    for key, value in weights.items():
        if hasattr(config.scoring, key):
            setattr(config.scoring, key, value)
    return get_weights()


@app.get("/api/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Company).count()
    watchlist = db.query(Company).filter_by(tracking_tier="watchlist").count()

    # Critical count (score >= 75)
    critical_subq = (
        db.query(
            DilutionScore.company_id,
            func.max(DilutionScore.id).label("max_id")
        )
        .group_by(DilutionScore.company_id)
        .subquery()
    )
    critical = (
        db.query(DilutionScore)
        .join(critical_subq, DilutionScore.id == critical_subq.c.max_id)
        .filter(DilutionScore.composite_score >= 75)
        .count()
    )

    # Average score
    avg_score_result = (
        db.query(func.avg(DilutionScore.composite_score))
        .join(critical_subq, DilutionScore.id == critical_subq.c.max_id)
        .scalar()
    )

    # Sector breakdown
    sectors = (
        db.query(Company.sector, func.count(Company.id).label("count"))
        .filter(Company.tracking_tier.in_(["watchlist", "monitoring"]))
        .filter(Company.sector.isnot(None))
        .group_by(Company.sector)
        .all()
    )

    return StatsResponse(
        total_companies=total,
        watchlist_count=watchlist,
        critical_count=critical,
        avg_score=float(avg_score_result) if avg_score_result else None,
        sectors=[{"sector": s, "count": c} for s, c in sectors]
    )


# ------------------------------------------------------------------ #
# Serve React app (production only)
# ------------------------------------------------------------------ #

frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
print(f"[STARTUP] Looking for frontend build at: {frontend_dist}")
print(f"[STARTUP] Frontend dist exists: {os.path.exists(frontend_dist)}")
if os.path.exists(frontend_dist):
    print(f"[STARTUP] Frontend dist contents: {os.listdir(frontend_dist)}")

    # Mount static assets
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        print(f"[STARTUP] Mounted /assets from {assets_dir}")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes."""
        # Let API routes pass through (they're already defined above)
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Check if requesting a static file
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Serve index.html for all other routes (SPA routing)
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
else:
    print(f"[STARTUP] WARNING: Frontend dist not found. Only API will be available.")
