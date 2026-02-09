import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Company, FundamentalsQuarterly, SecFiling, DilutionScore
from backend.config import ScoringConfig
from backend.services.scoring import score_company, score_all, get_latest_scores, _weighted_composite


def _make_session():
    """Create an in-memory SQLite DB for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_serial_diluter(session) -> int:
    """Add a company that should score HIGH (serial diluter)."""
    company = Company(
        ticker="MULN", name="Mullen Automotive", sector="Consumer Cyclical",
        exchange="NASDAQ", market_cap=50_000_000, tracking_tier="watchlist"
    )
    session.add(company)
    session.flush()

    # Share count growing rapidly: 100M -> 500M over 8 quarters
    shares_schedule = [100e6, 130e6, 170e6, 220e6, 280e6, 350e6, 420e6, 500e6]
    for i, shares in enumerate(shares_schedule):
        q = (i % 4) + 1
        y = 2023 + (i // 4)
        session.add(FundamentalsQuarterly(
            company_id=company.id,
            fiscal_period=f"{y}-Q{q}",
            fiscal_year=y, quarter=q,
            shares_outstanding_diluted=shares,
            free_cash_flow=-10_000_000,
            stock_based_compensation=5_000_000,
            revenue=500_000,
            cash_and_equivalents=max(15_000_000 - i * 2_000_000, 1_000_000),
        ))

    # Multiple dilution filings
    for i in range(5):
        session.add(SecFiling(
            company_id=company.id,
            accession_number=f"0001499961-24-{i:06d}",
            filing_type="424B5",
            filed_date=date.today() - timedelta(days=i * 90),
            is_dilution_event=True,
            dilution_type="atm",
            offering_amount_dollars=10_000_000,
        ))
    # Active S-3
    session.add(SecFiling(
        company_id=company.id,
        accession_number="0001499961-24-100000",
        filing_type="S-3",
        filed_date=date.today() - timedelta(days=30),
        is_dilution_event=True,
        dilution_type="atm_shelf",
    ))

    session.commit()
    return company.id


def _add_healthy_company(session) -> int:
    """Add a company that should score LOW (profitable, stable shares)."""
    company = Company(
        ticker="AAPL", name="Apple Inc.", sector="Technology",
        exchange="NASDAQ", market_cap=2_800_000_000_000, tracking_tier="monitoring"
    )
    session.add(company)
    session.flush()

    # Stable share count, positive FCF
    for i in range(8):
        q = (i % 4) + 1
        y = 2023 + (i // 4)
        session.add(FundamentalsQuarterly(
            company_id=company.id,
            fiscal_period=f"{y}-Q{q}",
            fiscal_year=y, quarter=q,
            shares_outstanding_diluted=15_500_000_000,  # Stable
            free_cash_flow=25_000_000_000,  # Positive
            stock_based_compensation=3_000_000_000,
            revenue=90_000_000_000,
            cash_and_equivalents=60_000_000_000,
        ))

    session.commit()
    return company.id


def _add_sparse_company(session) -> int:
    """Add a company with minimal data (only 2 quarters)."""
    company = Company(
        ticker="NEW", name="New Corp", sector="Technology",
        exchange="NASDAQ", market_cap=100_000_000, tracking_tier="monitoring"
    )
    session.add(company)
    session.flush()

    for i in range(2):
        q = i + 1
        session.add(FundamentalsQuarterly(
            company_id=company.id,
            fiscal_period=f"2024-Q{q}",
            fiscal_year=2024, quarter=q,
            shares_outstanding_diluted=10_000_000 + i * 2_000_000,
            free_cash_flow=-5_000_000,
            stock_based_compensation=None,
            revenue=None,
            cash_and_equivalents=8_000_000,
        ))

    session.commit()
    return company.id


class TestScoreCompanyHigh(unittest.TestCase):
    """Serial diluter should score high."""

    def setUp(self):
        self.session = _make_session()
        self.company_id = _add_serial_diluter(self.session)
        self.config = ScoringConfig()

    def test_composite_score_is_high(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertGreater(result.composite_score, 60)

    def test_share_cagr_score_is_high(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertGreater(result.share_cagr_score, 50)

    def test_offering_freq_score_is_high(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertGreater(result.offering_freq_score, 50)

    def test_atm_is_active(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertEqual(result.atm_active_score, 100)
        self.assertTrue(result.atm_program_active)

    def test_saved_to_db(self):
        score_company(self.session, self.company_id, self.config)
        count = self.session.query(DilutionScore).filter_by(company_id=self.company_id).count()
        self.assertEqual(count, 1)


class TestScoreCompanyLow(unittest.TestCase):
    """Healthy company should score low."""

    def setUp(self):
        self.session = _make_session()
        self.company_id = _add_healthy_company(self.session)
        self.config = ScoringConfig()

    def test_composite_score_is_low(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertLess(result.composite_score, 20)

    def test_fcf_burn_is_zero(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertEqual(result.fcf_burn_score, 0)

    def test_no_atm_active(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertEqual(result.atm_active_score, 0)

    def test_cash_runway_is_zero(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertEqual(result.cash_runway_score, 0)

    def test_offering_freq_is_zero(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertEqual(result.offering_freq_score, 0)


class TestScoreCompanySparse(unittest.TestCase):
    """Company with only 2 quarters should still produce a score."""

    def setUp(self):
        self.session = _make_session()
        self.company_id = _add_sparse_company(self.session)
        self.config = ScoringConfig()

    def test_produces_a_score(self):
        result = score_company(self.session, self.company_id, self.config)
        self.assertIsNotNone(result.composite_score)
        self.assertGreaterEqual(result.composite_score, 0)

    def test_sbc_revenue_is_none(self):
        result = score_company(self.session, self.company_id, self.config)
        # No SBC or revenue data -> None
        self.assertIsNone(result.sbc_revenue_score)

    def test_share_cagr_still_calculated(self):
        result = score_company(self.session, self.company_id, self.config)
        # 10M -> 12M in 2 quarters, should have a CAGR
        self.assertIsNotNone(result.share_cagr_score)


class TestWeightRenormalization(unittest.TestCase):
    def test_renormalization_with_missing_scores(self):
        config = ScoringConfig()
        scores = {
            "share_cagr_score": 80,
            "fcf_burn_score": 60,
            "sbc_revenue_score": None,  # Missing
            "offering_freq_score": 40,
            "cash_runway_score": 50,
            "atm_active_score": 100,
        }
        composite = _weighted_composite(scores, config)

        # Without SBC (weight=0.15), total weight = 0.85
        # Composite should be > 0 and renormalized
        self.assertGreater(composite, 0)
        self.assertLessEqual(composite, 100)

    def test_all_none_returns_zero(self):
        config = ScoringConfig()
        scores = {
            "share_cagr_score": None,
            "fcf_burn_score": None,
            "sbc_revenue_score": None,
            "offering_freq_score": None,
            "cash_runway_score": None,
            "atm_active_score": None,
        }
        composite = _weighted_composite(scores, config)
        self.assertEqual(composite, 0)

    def test_single_score_gets_full_weight(self):
        config = ScoringConfig()
        scores = {
            "share_cagr_score": 80,
            "fcf_burn_score": None,
            "sbc_revenue_score": None,
            "offering_freq_score": None,
            "cash_runway_score": None,
            "atm_active_score": None,
        }
        composite = _weighted_composite(scores, config)
        # Only share_cagr exists, so composite = 80 (renormalized to itself)
        self.assertAlmostEqual(composite, 80, places=1)


class TestScoreAll(unittest.TestCase):
    def test_scores_all_tracked_companies(self):
        session = _make_session()
        id1 = _add_serial_diluter(session)
        id2 = _add_healthy_company(session)

        config = ScoringConfig()
        results = score_all(session, config)

        self.assertEqual(len(results), 2)
        tickers_scored = {session.get(Company, r.company_id).ticker for r in results}
        self.assertEqual(tickers_scored, {"MULN", "AAPL"})


class TestGetLatestScores(unittest.TestCase):
    def test_returns_joined_results(self):
        session = _make_session()
        id1 = _add_serial_diluter(session)
        config = ScoringConfig()
        score_company(session, id1, config)

        results = get_latest_scores(session)
        self.assertEqual(len(results), 1)
        company, score = results[0]
        self.assertEqual(company.ticker, "MULN")
        self.assertGreater(score.composite_score, 0)


if __name__ == "__main__":
    unittest.main()
