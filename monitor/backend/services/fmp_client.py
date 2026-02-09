"""
Financial Modeling Prep (FMP) API client.

Docs: https://site.financialmodelingprep.com/developer/docs

Endpoints used (stable):
  GET /stable/companies/list                 — Full US equity universe
  GET /stable/income-statement?symbol={ticker} — Quarterly income (shares, revenue)
  GET /stable/cash-flow-statement?symbol={ticker} — Quarterly cashflow (FCF, SBC)
  GET /stable/balance-sheet-statement?symbol={ticker} — Quarterly balance sheet (cash)
  GET /stable/profile?symbol={ticker}        — Company profile
  GET /stable/historical-price-eod/full?symbol={ticker} — Daily split-adjusted prices
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/stable"

US_EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "NYSEArca", "NYSEMkt", "BATS", "CBOE"}

# Rate limit: 0.25s between calls = max 240/min (under the 300/min cap)
RATE_LIMIT_DELAY = 0.25
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds


class FMPClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._last_call_time: float = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call_time = time.time()

    def _get(self, path: str, params: Optional[dict] = None) -> list | dict:
        url = f"{BASE_URL}{path}"
        if params is None:
            params = {}
        params["apikey"] = self.api_key

        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limit()
            try:
                logger.info("FMP API call: GET %s (attempt %d)", path, attempt)
                resp = httpx.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("FMP API error on %s (attempt %d): %s", path, attempt, exc)
                if attempt < MAX_RETRIES:
                    backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.info("Retrying in %.1fs...", backoff)
                    time.sleep(backoff)
                else:
                    logger.error("FMP API call failed after %d retries: %s", MAX_RETRIES, path)
                    raise

    # ------------------------------------------------------------------ #
    # 1. Stock list
    # ------------------------------------------------------------------ #
    def get_stock_list(self) -> list[dict]:
        """Fetch full stock list using screener endpoint."""
        # Note: screener has a limit, we'll fetch in batches
        # For now, fetch a large batch (screener max is usually 10k-50k)
        raw = self._get("/company-screener", {"limit": 10000})
        filtered = [
            {
                "ticker": item.get("symbol"),
                "name": item.get("companyName") or item.get("symbol"),
                "sector": item.get("sector"),
                "exchange": item.get("exchange"),
                "market_cap": item.get("marketCap"),
                "type": "stock",
            }
            for item in raw
            if item.get("symbol") and item.get("marketCap") and item.get("marketCap") > 0
        ]
        logger.info("Fetched stock list: %d stocks", len(filtered))
        return filtered

    # ------------------------------------------------------------------ #
    # 2. Income statements
    # ------------------------------------------------------------------ #
    def get_income_statements(self, ticker: str, period: str = "quarter", limit: int = 12) -> list[dict]:
        """Fetch quarterly income statements for a ticker."""
        raw = self._get("/income-statement", {"symbol": ticker, "period": period, "limit": limit})
        return [
            {
                "date": item.get("date"),
                "period": item.get("period"),
                "shares_outstanding_diluted": item.get("weightedAverageShsOutDil"),
                "revenue": item.get("revenue"),
                "operating_income": item.get("operatingIncome"),
            }
            for item in raw
        ]

    # ------------------------------------------------------------------ #
    # 3. Cashflow statements
    # ------------------------------------------------------------------ #
    def get_cashflow_statements(self, ticker: str, period: str = "quarter", limit: int = 12) -> list[dict]:
        """Fetch quarterly cashflow statements for a ticker."""
        raw = self._get("/cash-flow-statement", {"symbol": ticker, "period": period, "limit": limit})
        return [
            {
                "date": item.get("date"),
                "period": item.get("period"),
                "free_cash_flow": item.get("freeCashFlow"),
                "stock_based_compensation": item.get("stockBasedCompensation"),
            }
            for item in raw
        ]

    # ------------------------------------------------------------------ #
    # 4. Balance sheets
    # ------------------------------------------------------------------ #
    def get_balance_sheets(self, ticker: str, period: str = "quarter", limit: int = 12) -> list[dict]:
        """Fetch quarterly balance sheets for a ticker."""
        raw = self._get("/balance-sheet-statement", {"symbol": ticker, "period": period, "limit": limit})
        return [
            {
                "date": item.get("date"),
                "period": item.get("period"),
                "cash_and_equivalents": item.get("cashAndCashEquivalents"),
            }
            for item in raw
        ]

    # ------------------------------------------------------------------ #
    # 5. Company profile
    # ------------------------------------------------------------------ #
    def get_company_profile(self, ticker: str) -> dict:
        """Fetch company profile."""
        raw = self._get("/profile", {"symbol": ticker})
        if isinstance(raw, list) and len(raw) > 0:
            return raw[0]
        return raw

    # ------------------------------------------------------------------ #
    # 6. Historical prices (split-adjusted)
    # ------------------------------------------------------------------ #
    def get_historical_prices(self, ticker: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[dict]:
        """Fetch daily split-adjusted prices. Returns oldest-first."""
        params = {"symbol": ticker}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        raw = self._get("/historical-price-eod/full", params)
        if not raw:
            return []
        # FMP returns newest-first; reverse to oldest-first
        rows = raw if isinstance(raw, list) else raw.get("historical", raw)
        if not isinstance(rows, list):
            return []
        return [
            {
                "date": item.get("date"),
                "close": item.get("adjClose") or item.get("close"),
                "volume": item.get("volume"),
            }
            for item in reversed(rows)
            if item.get("date")
        ]

    def get_price_change_12m(self, ticker: str) -> Optional[float]:
        """Compute trailing 12-month price change (split-adjusted). Returns decimal (e.g. -0.35 = -35%)."""
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        prices = self.get_historical_prices(ticker, from_date=from_date, to_date=to_date)
        if len(prices) < 2:
            return None
        old_price = prices[0]["close"]
        new_price = prices[-1]["close"]
        if not old_price or old_price <= 0:
            return None
        return (new_price - old_price) / old_price

    # ------------------------------------------------------------------ #
    # 7. Full fundamentals (merged)
    # ------------------------------------------------------------------ #
    def get_full_fundamentals(self, ticker: str, limit: int = 12) -> list[dict]:
        """
        Pull income, cashflow, and balance sheet data then merge by period
        into a unified list of quarterly records.
        """
        income = self.get_income_statements(ticker, limit=limit)
        cashflow = self.get_cashflow_statements(ticker, limit=limit)
        balance = self.get_balance_sheets(ticker, limit=limit)

        # Index cashflow and balance by date for merging
        cf_by_date = {item["date"]: item for item in cashflow}
        bs_by_date = {item["date"]: item for item in balance}

        merged = []
        for inc in income:
            dt = inc["date"]
            cf = cf_by_date.get(dt, {})
            bs = bs_by_date.get(dt, {})

            # Derive fiscal_period from date: "2024-09-30" -> "2024-Q3"
            fiscal_period = _date_to_fiscal_period(dt)

            merged.append({
                "date": dt,
                "fiscal_period": fiscal_period,
                "shares_outstanding": inc.get("shares_outstanding_diluted"),
                "fcf": cf.get("free_cash_flow"),
                "sbc": cf.get("stock_based_compensation"),
                "revenue": inc.get("revenue"),
                "cash": bs.get("cash_and_equivalents"),
            })

        logger.info("Merged %d quarterly records for %s", len(merged), ticker)
        return merged


def _date_to_fiscal_period(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to 'YYYY-QN'."""
    if not date_str or len(date_str) < 7:
        return "unknown"
    year = date_str[:4]
    month = int(date_str[5:7])
    quarter = (month - 1) // 3 + 1
    return f"{year}-Q{quarter}"
