import logging
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

RATE_LIMIT_DELAY = 0.12  # max 10 req/sec to SEC
MAX_RETRIES = 3
BACKOFF_BASE = 1.0

# Keyword patterns for filing classification
DILUTION_PATTERNS = [
    (r"at[- ]the[- ]market|(?<!\w)ATM(?!\w)", "atm"),
    (r"registered\s+direct", "registered_direct"),
    (r"public\s+offering[\s\S]{0,500}underwriting|underwriting[\s\S]{0,500}public\s+offering", "follow_on"),
    (r"convertible.*note|note.*convertible", "convertible"),
    (r"private\s+placement|(?<!\w)PIPE(?!\w)", "pipe"),
]

DOLLAR_REGEX = re.compile(r"\$([\d,.]+)\s*(million|billion)", re.IGNORECASE)


class EdgarClient:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._last_call_time: float = 0
        self._ticker_to_cik: Optional[dict[str, str]] = None

    def _rate_limit(self):
        elapsed = time.time() - self._last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call_time = time.time()

    def _get(self, url: str) -> dict | list | str:
        headers = {"User-Agent": self.user_agent}

        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limit()
            try:
                logger.info("EDGAR API call: GET %s (attempt %d)", url, attempt)
                resp = httpx.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                if "json" in resp.headers.get("content-type", ""):
                    return resp.json()
                return resp.text
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("EDGAR API error on %s (attempt %d): %s", url, attempt, exc)
                if attempt < MAX_RETRIES:
                    backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                    time.sleep(backoff)
                else:
                    raise

    def _get_text(self, url: str, max_chars: int = 5000) -> str:
        """Fetch a document and return the first max_chars of text."""
        headers = {"User-Agent": self.user_agent}

        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limit()
            try:
                logger.info("EDGAR doc fetch: GET %s (attempt %d)", url, attempt)
                resp = httpx.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                return resp.text[:max_chars]
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("EDGAR doc error on %s (attempt %d): %s", url, attempt, exc)
                if attempt < MAX_RETRIES:
                    backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                    time.sleep(backoff)
                else:
                    raise

    # ------------------------------------------------------------------ #
    # 1. CIK lookup
    # ------------------------------------------------------------------ #
    def _load_ticker_map(self):
        """Load and cache the full ticker->CIK mapping from SEC."""
        if self._ticker_to_cik is not None:
            return
        raw = self._get(COMPANY_TICKERS_URL)
        self._ticker_to_cik = {}
        for entry in raw.values():
            ticker = entry.get("ticker", "").upper()
            cik = entry.get("cik_str")
            if ticker and cik is not None:
                self._ticker_to_cik[ticker] = str(cik).zfill(10)
        logger.info("Loaded %d ticker->CIK mappings from SEC", len(self._ticker_to_cik))

    def lookup_cik(self, ticker: str) -> Optional[str]:
        """Look up a zero-padded 10-digit CIK for a ticker."""
        self._load_ticker_map()
        return self._ticker_to_cik.get(ticker.upper())

    # ------------------------------------------------------------------ #
    # 2. Recent filings
    # ------------------------------------------------------------------ #
    def get_recent_filings(
        self,
        cik: str,
        filing_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch recent SEC filings for a CIK, filtered by form type."""
        if filing_types is None:
            filing_types = ["S-3", "S-3/A", "424B5", "8-K"]

        url = SUBMISSIONS_URL.format(cik=cik)
        data = self._get(url)

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        # The entity CIK (without leading zeros) for building doc URLs
        entity_cik = cik.lstrip("0") or "0"

        results = []
        for i in range(len(forms)):
            if forms[i] not in filing_types:
                continue
            accession_no_dashes = accessions[i].replace("-", "")
            doc_url = f"{ARCHIVES_BASE}/{entity_cik}/{accession_no_dashes}/{primary_docs[i]}"
            results.append({
                "accession_number": accessions[i],
                "form": forms[i],
                "filing_date": dates[i],
                "primary_doc_url": doc_url,
            })
            if len(results) >= limit:
                break

        logger.info("Found %d filings (types=%s) for CIK %s", len(results), filing_types, cik)
        return results

    # ------------------------------------------------------------------ #
    # 3. Filing classifier
    # ------------------------------------------------------------------ #
    def classify_filing(self, filing_type: str, primary_doc_url: Optional[str] = None) -> dict:
        """
        Classify a filing as a dilution event.
        S-3 filings are auto-flagged. 424B5 and 8-K are keyword-classified.
        """
        # S-3 auto-classification
        if filing_type in ("S-3", "S-3/A"):
            return {
                "is_dilution_event": True,
                "dilution_type": "atm_shelf",
                "offering_amount": None,
                "confidence": 0.7,
            }

        # For 424B5 and 8-K, fetch and classify document text
        if filing_type in ("424B5", "8-K") and primary_doc_url:
            try:
                text = self._get_text(primary_doc_url, max_chars=5000)
            except Exception:
                logger.warning("Could not fetch document for classification: %s", primary_doc_url)
                return _no_dilution()

            return classify_text(text)

        return _no_dilution()


def classify_text(text: str) -> dict:
    """Run keyword classifier on filing text."""
    text_lower = text.lower()

    for pattern, dilution_type in DILUTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            amount = _extract_dollar_amount(text)
            confidence = 0.85 if dilution_type in ("atm", "registered_direct") else 0.7
            return {
                "is_dilution_event": True,
                "dilution_type": dilution_type,
                "offering_amount": amount,
                "confidence": confidence,
            }

    return _no_dilution()


def _extract_dollar_amount(text: str) -> Optional[float]:
    """Extract the first dollar amount near offering keywords."""
    match = DOLLAR_REGEX.search(text)
    if not match:
        return None
    raw_number = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower()
    if unit == "billion":
        return raw_number * 1_000_000_000
    return raw_number * 1_000_000


def _no_dilution() -> dict:
    return {
        "is_dilution_event": False,
        "dilution_type": None,
        "offering_amount": None,
        "confidence": 0.0,
    }
