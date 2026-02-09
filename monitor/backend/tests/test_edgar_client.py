import unittest
from unittest.mock import patch, MagicMock

import httpx

from backend.services.edgar_client import EdgarClient, classify_text, _extract_dollar_amount


# ------------------------------------------------------------------ #
# Mock SEC data
# ------------------------------------------------------------------ #

MOCK_COMPANY_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1499961, "ticker": "MULN", "title": "Mullen Automotive Inc."},
    "2": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
    "3": {"cik_str": 51, "ticker": "TINY", "title": "Tiny Corp"},  # short CIK to test zero-padding
}

MOCK_SUBMISSIONS = {
    "cik": "1499961",
    "entityType": "operating",
    "name": "Mullen Automotive Inc.",
    "filings": {
        "recent": {
            "accessionNumber": [
                "0001499961-24-000123",
                "0001499961-24-000100",
                "0001499961-24-000090",
                "0001499961-24-000080",
                "0001499961-24-000070",
            ],
            "filingDate": [
                "2024-09-15",
                "2024-08-01",
                "2024-07-10",
                "2024-06-05",
                "2024-05-20",
            ],
            "form": ["424B5", "S-3", "8-K", "10-Q", "8-K"],
            "primaryDocument": [
                "d424b5.htm",
                "ds3.htm",
                "d8k.htm",
                "d10q.htm",
                "d8k-2.htm",
            ],
        }
    },
}

# ------------------------------------------------------------------ #
# Realistic filing text samples
# ------------------------------------------------------------------ #

ATM_FILING_TEXT = """
PROSPECTUS SUPPLEMENT
(To Prospectus dated March 15, 2024)

Up to $75,000,000
Common Stock

We have entered into an At-The-Market Issuance Sales Agreement (the "Sales Agreement")
with B. Riley Securities, Inc. as sales agent, pursuant to which we may offer and sell,
from time to time, shares of our common stock having an aggregate offering price of up
to $75 million through an at-the-market offering program.
"""

REGISTERED_DIRECT_TEXT = """
PROSPECTUS SUPPLEMENT
(To Prospectus dated June 1, 2024)

5,000,000 Shares of Common Stock

We are offering 5,000,000 shares of our common stock in a registered direct offering
to select institutional investors at a purchase price of $2.50 per share. The aggregate
gross proceeds from this registered direct offering are approximately $12.5 million
before deducting placement agent fees.
"""

FOLLOW_ON_TEXT = """
PROSPECTUS SUPPLEMENT
(To Prospectus dated January 20, 2024)

10,000,000 Shares of Common Stock

This prospectus supplement relates to the public offering of 10,000,000 shares of
common stock of XYZ Corp. The underwriting agreement provides that the underwriters
are obligated to purchase all of the shares if any are purchased. We have granted
the underwriters a 30-day option to purchase up to an additional 1,500,000 shares.
The public offering price is $8.00 per share for aggregate proceeds of $80 million.
"""

CONVERTIBLE_NOTE_TEXT = """
FORM 8-K
CURRENT REPORT

Item 1.01 Entry into a Material Definitive Agreement

On September 10, 2024, the Company entered into a Securities Purchase Agreement
with certain institutional investors for the issuance and sale of $25 million
aggregate principal amount of 8% Senior Convertible Notes due 2027 (the "Notes").
The convertible notes are convertible into shares of common stock at a conversion
price of $3.50 per share, subject to adjustment.
"""

PIPE_FILING_TEXT = """
FORM 8-K
CURRENT REPORT

Item 3.02 Unregistered Sales of Equity Securities

On August 5, 2024, the Company closed a private placement (PIPE) transaction with
accredited investors for the sale of 8,000,000 shares of common stock and warrants
to purchase up to 4,000,000 additional shares. The aggregate gross proceeds from
this private placement were approximately $20 million.
"""

NON_DILUTION_8K_TEXT = """
FORM 8-K
CURRENT REPORT

Item 2.02 Results of Operations and Financial Condition

On October 15, 2024, the Company issued a press release announcing its financial
results for the third quarter ended September 30, 2024. Revenue increased 12%
year-over-year to $45.3 million. The Company reported net income of $3.2 million,
compared to a net loss of $1.1 million in the prior year period.
"""


def _mock_json_response(data, content_type="application/json"):
    mock = MagicMock()
    mock.json.return_value = data
    mock.text = str(data)
    mock.status_code = 200
    mock.headers = {"content-type": content_type}
    mock.raise_for_status.return_value = None
    return mock


def _mock_text_response(text):
    mock = MagicMock()
    mock.text = text
    mock.status_code = 200
    mock.headers = {"content-type": "text/html"}
    mock.raise_for_status.return_value = None
    return mock


class TestCIKLookup(unittest.TestCase):
    def setUp(self):
        self.client = EdgarClient(user_agent="TestAgent test@example.com")
        self.client._rate_limit = lambda: None

    @patch("backend.services.edgar_client.httpx.get")
    def test_lookup_cik_returns_padded(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_COMPANY_TICKERS)

        cik = self.client.lookup_cik("AAPL")
        self.assertEqual(cik, "0000320193")

    @patch("backend.services.edgar_client.httpx.get")
    def test_lookup_cik_case_insensitive(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_COMPANY_TICKERS)

        cik = self.client.lookup_cik("muln")
        self.assertEqual(cik, "0001499961")

    @patch("backend.services.edgar_client.httpx.get")
    def test_lookup_cik_zero_pads_short_cik(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_COMPANY_TICKERS)

        cik = self.client.lookup_cik("TINY")
        self.assertEqual(cik, "0000000051")
        self.assertEqual(len(cik), 10)

    @patch("backend.services.edgar_client.httpx.get")
    def test_lookup_cik_unknown_ticker(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_COMPANY_TICKERS)

        cik = self.client.lookup_cik("ZZZZZZ")
        self.assertIsNone(cik)

    @patch("backend.services.edgar_client.httpx.get")
    def test_ticker_map_cached(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_COMPANY_TICKERS)

        self.client.lookup_cik("AAPL")
        self.client.lookup_cik("MULN")
        # Should only fetch once
        mock_get.assert_called_once()


class TestRecentFilings(unittest.TestCase):
    def setUp(self):
        self.client = EdgarClient(user_agent="TestAgent test@example.com")
        self.client._rate_limit = lambda: None

    @patch("backend.services.edgar_client.httpx.get")
    def test_filters_by_filing_type(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_SUBMISSIONS)

        results = self.client.get_recent_filings("0001499961")

        # Should get 424B5, S-3, and two 8-Ks (not the 10-Q)
        forms = [r["form"] for r in results]
        self.assertIn("424B5", forms)
        self.assertIn("S-3", forms)
        self.assertIn("8-K", forms)
        self.assertNotIn("10-Q", forms)

    @patch("backend.services.edgar_client.httpx.get")
    def test_returns_correct_fields(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_SUBMISSIONS)

        results = self.client.get_recent_filings("0001499961")
        first = results[0]

        self.assertIn("accession_number", first)
        self.assertIn("form", first)
        self.assertIn("filing_date", first)
        self.assertIn("primary_doc_url", first)
        self.assertTrue(first["primary_doc_url"].startswith("https://"))

    @patch("backend.services.edgar_client.httpx.get")
    def test_respects_limit(self, mock_get):
        mock_get.return_value = _mock_json_response(MOCK_SUBMISSIONS)

        results = self.client.get_recent_filings("0001499961", limit=2)
        self.assertLessEqual(len(results), 2)


class TestClassifyFiling(unittest.TestCase):
    def setUp(self):
        self.client = EdgarClient(user_agent="TestAgent test@example.com")
        self.client._rate_limit = lambda: None

    def test_s3_auto_classified(self):
        result = self.client.classify_filing("S-3")

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "atm_shelf")
        self.assertEqual(result["confidence"], 0.7)

    def test_s3a_auto_classified(self):
        result = self.client.classify_filing("S-3/A")

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "atm_shelf")


class TestClassifyText(unittest.TestCase):
    """Test the keyword classifier against realistic filing text samples."""

    def test_atm_offering(self):
        result = classify_text(ATM_FILING_TEXT)

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "atm")
        self.assertEqual(result["offering_amount"], 75_000_000)
        self.assertGreater(result["confidence"], 0.5)

    def test_registered_direct(self):
        result = classify_text(REGISTERED_DIRECT_TEXT)

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "registered_direct")
        self.assertEqual(result["offering_amount"], 12_500_000)

    def test_follow_on_offering(self):
        result = classify_text(FOLLOW_ON_TEXT)

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "follow_on")
        self.assertEqual(result["offering_amount"], 80_000_000)

    def test_convertible_note(self):
        result = classify_text(CONVERTIBLE_NOTE_TEXT)

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "convertible")
        self.assertEqual(result["offering_amount"], 25_000_000)

    def test_pipe_private_placement(self):
        result = classify_text(PIPE_FILING_TEXT)

        self.assertTrue(result["is_dilution_event"])
        self.assertEqual(result["dilution_type"], "pipe")
        self.assertEqual(result["offering_amount"], 20_000_000)

    def test_non_dilution_8k(self):
        result = classify_text(NON_DILUTION_8K_TEXT)

        self.assertFalse(result["is_dilution_event"])
        self.assertIsNone(result["dilution_type"])


class TestDollarExtraction(unittest.TestCase):
    def test_millions(self):
        self.assertEqual(_extract_dollar_amount("raised $50 million in proceeds"), 50_000_000)

    def test_billions(self):
        self.assertEqual(_extract_dollar_amount("valued at $1.5 billion"), 1_500_000_000)

    def test_with_commas(self):
        self.assertEqual(_extract_dollar_amount("offering of $1,250 million"), 1_250_000_000)

    def test_no_match(self):
        self.assertIsNone(_extract_dollar_amount("revenue was strong this quarter"))


if __name__ == "__main__":
    unittest.main()
