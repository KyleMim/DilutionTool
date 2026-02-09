import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ScoringConfig:
    # Thresholds for quick screen
    share_cagr_min: float = 0.05       # 5% annual share growth triggers candidate
    fcf_negative_quarters: int = 4     # min negative FCF quarters out of 8

    # Sub-score normalization ceilings
    share_cagr_ceiling: float = 0.50   # 50% annual CAGR = max score
    fcf_burn_ceiling: float = 0.70     # 70% burn rate = max score
    sbc_revenue_ceiling: float = 0.60  # 60% SBC/revenue = max score
    offering_freq_ceiling: int = 7     # 7 offerings in 3 years = max score
    cash_runway_max_months: int = 24   # < 24 months runway starts scoring

    # Weights (must sum to 1.0)
    weight_share_cagr: float = 0.25
    weight_fcf_burn: float = 0.20
    weight_sbc_revenue: float = 0.15
    weight_offering_freq: float = 0.20
    weight_cash_runway: float = 0.10
    weight_atm_active: float = 0.10

    # Tier thresholds
    watchlist_min_score: float = 25.0


@dataclass
class AppConfig:
    fmp_api_key: str = ""
    edgar_user_agent: str = "DilutionMonitor dev@example.com"
    db_path: str = "data/dilution_monitor.db"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5-20250929"
    scoring: ScoringConfig = field(default_factory=ScoringConfig)


def get_config() -> AppConfig:
    fmp_key = os.getenv("FMP_API_KEY", "")
    if not fmp_key:
        print("WARNING: FMP_API_KEY not set. API calls will fail.")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        print("WARNING: ANTHROPIC_API_KEY not set. AI chat will not work.")

    return AppConfig(
        fmp_api_key=fmp_key,
        edgar_user_agent=os.getenv("EDGAR_USER_AGENT", "DilutionMonitor dev@example.com"),
        db_path=os.getenv("DB_PATH", "data/dilution_monitor.db"),
        anthropic_api_key=anthropic_key,
        llm_model=os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929"),
    )
