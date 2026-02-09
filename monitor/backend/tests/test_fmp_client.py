import unittest
from unittest.mock import patch, MagicMock

import httpx

from backend.services.fmp_client import FMPClient, _date_to_fiscal_period


# ------------------------------------------------------------------ #
# Realistic mock responses based on actual FMP API data shapes
# ------------------------------------------------------------------ #

MOCK_STOCK_LIST = [
    {"symbol": "AAPL", "companyName": "Apple Inc.", "price": 182.52,
     "marketCap": 2850000000000},
    {"symbol": "MULN", "companyName": "Mullen Automotive", "price": 0.15,
     "marketCap": 50000000},
    {"symbol": "BHP", "companyName": "BHP Group", "price": 45.0,
     "marketCap": 150000000000},
    {"symbol": "SPY", "companyName": "SPDR S&P 500", "price": 450.0,
     "marketCap": None},
    {"symbol": "TSLA", "companyName": "Tesla Inc.", "price": 248.50,
     "marketCap": 790000000000},
]

MOCK_INCOME_STATEMENTS = [
    {"date": "2024-09-30", "symbol": "MULN", "period": "Q3",
     "revenue": 1200000, "operatingIncome": -45000000,
     "weightedAverageShsOutDil": 500000000},
    {"date": "2024-06-30", "symbol": "MULN", "period": "Q2",
     "revenue": 800000, "operatingIncome": -52000000,
     "weightedAverageShsOutDil": 350000000},
    {"date": "2024-03-31", "symbol": "MULN", "period": "Q1",
     "revenue": 500000, "operatingIncome": -48000000,
     "weightedAverageShsOutDil": 200000000},
]

MOCK_CASHFLOW_STATEMENTS = [
    {"date": "2024-09-30", "symbol": "MULN", "period": "Q3",
     "freeCashFlow": -40000000, "stockBasedCompensation": 3000000},
    {"date": "2024-06-30", "symbol": "MULN", "period": "Q2",
     "freeCashFlow": -38000000, "stockBasedCompensation": 2500000},
    {"date": "2024-03-31", "symbol": "MULN", "period": "Q1",
     "freeCashFlow": -35000000, "stockBasedCompensation": 2000000},
]

MOCK_BALANCE_SHEETS = [
    {"date": "2024-09-30", "symbol": "MULN", "period": "Q3",
     "cashAndCashEquivalents": 15000000},
    {"date": "2024-06-30", "symbol": "MULN", "period": "Q2",
     "cashAndCashEquivalents": 55000000},
    {"date": "2024-03-31", "symbol": "MULN", "period": "Q1",
     "cashAndCashEquivalents": 90000000},
]

MOCK_PROFILE = [
    {"symbol": "MULN", "companyName": "Mullen Automotive Inc.", "currency": "USD",
     "mktCap": 50000000, "exchange": "NASDAQ", "exchangeShortName": "NASDAQ",
     "industry": "Auto Manufacturers", "sector": "Consumer Cyclical",
     "country": "US", "isActivelyTrading": True, "cik": "0001499961"},
]


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status.return_value = None
    return mock


class TestFMPClient(unittest.TestCase):
    def setUp(self):
        self.client = FMPClient(api_key="test_key_123")
        # Disable rate limiting in tests
        self.client._rate_limit = lambda: None

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_stock_list_filters_us_stocks(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_STOCK_LIST)

        result = self.client.get_stock_list()

        # Should include all with marketCap > 0
        # Should exclude SPY (marketCap = None)
        self.assertEqual(len(result), 4)
        tickers = [r["ticker"] for r in result]
        self.assertIn("AAPL", tickers)
        self.assertIn("MULN", tickers)
        self.assertIn("TSLA", tickers)
        self.assertNotIn("SPY", tickers)

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_stock_list_returns_correct_fields(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_STOCK_LIST)

        result = self.client.get_stock_list()
        aapl = next(r for r in result if r["ticker"] == "AAPL")

        self.assertEqual(aapl["name"], "Apple Inc.")
        self.assertEqual(aapl["market_cap"], 2850000000000)
        self.assertEqual(aapl["type"], "stock")

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_income_statements(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_INCOME_STATEMENTS)

        result = self.client.get_income_statements("MULN", limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["date"], "2024-09-30")
        self.assertEqual(result[0]["shares_outstanding_diluted"], 500000000)
        self.assertEqual(result[0]["revenue"], 1200000)
        self.assertEqual(result[0]["operating_income"], -45000000)

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_cashflow_statements(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_CASHFLOW_STATEMENTS)

        result = self.client.get_cashflow_statements("MULN", limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["free_cash_flow"], -40000000)
        self.assertEqual(result[0]["stock_based_compensation"], 3000000)

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_balance_sheets(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_BALANCE_SHEETS)

        result = self.client.get_balance_sheets("MULN", limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["cash_and_equivalents"], 15000000)

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_company_profile(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_PROFILE)

        result = self.client.get_company_profile("MULN")

        self.assertEqual(result["symbol"], "MULN")
        self.assertEqual(result["sector"], "Consumer Cyclical")
        self.assertEqual(result["cik"], "0001499961")

    @patch("backend.services.fmp_client.httpx.get")
    def test_get_full_fundamentals_merges_data(self, mock_get):
        # Return different data for each sequential call
        mock_get.side_effect = [
            _mock_response(MOCK_INCOME_STATEMENTS),
            _mock_response(MOCK_CASHFLOW_STATEMENTS),
            _mock_response(MOCK_BALANCE_SHEETS),
        ]

        result = self.client.get_full_fundamentals("MULN", limit=3)

        self.assertEqual(len(result), 3)

        # Check Q3 2024 record has data from all three sources
        q3 = result[0]
        self.assertEqual(q3["fiscal_period"], "2024-Q3")
        self.assertEqual(q3["shares_outstanding"], 500000000)
        self.assertEqual(q3["fcf"], -40000000)
        self.assertEqual(q3["sbc"], 3000000)
        self.assertEqual(q3["revenue"], 1200000)
        self.assertEqual(q3["cash"], 15000000)

        # Check Q1 2024
        q1 = result[2]
        self.assertEqual(q1["fiscal_period"], "2024-Q1")
        self.assertEqual(q1["shares_outstanding"], 200000000)

    @patch("backend.services.fmp_client.httpx.get")
    def test_retry_on_failure(self, mock_get):
        # Fail twice, succeed on third attempt
        mock_get.side_effect = [
            httpx.RequestError("Connection timeout"),
            httpx.RequestError("Connection timeout"),
            _mock_response(MOCK_PROFILE),
        ]

        result = self.client.get_company_profile("MULN")
        self.assertEqual(result["symbol"], "MULN")
        self.assertEqual(mock_get.call_count, 3)

    @patch("backend.services.fmp_client.httpx.get")
    def test_raises_after_max_retries(self, mock_get):
        mock_get.side_effect = httpx.RequestError("Connection timeout")

        with self.assertRaises(httpx.RequestError):
            self.client.get_company_profile("MULN")

        self.assertEqual(mock_get.call_count, 3)


class TestDateToFiscalPeriod(unittest.TestCase):
    def test_q1(self):
        self.assertEqual(_date_to_fiscal_period("2024-03-31"), "2024-Q1")

    def test_q2(self):
        self.assertEqual(_date_to_fiscal_period("2024-06-30"), "2024-Q2")

    def test_q3(self):
        self.assertEqual(_date_to_fiscal_period("2024-09-30"), "2024-Q3")

    def test_q4(self):
        self.assertEqual(_date_to_fiscal_period("2024-12-31"), "2024-Q4")

    def test_january_is_q1(self):
        self.assertEqual(_date_to_fiscal_period("2024-01-15"), "2024-Q1")

    def test_invalid_returns_unknown(self):
        self.assertEqual(_date_to_fiscal_period(""), "unknown")
        self.assertEqual(_date_to_fiscal_period(None), "unknown")


if __name__ == "__main__":
    unittest.main()
