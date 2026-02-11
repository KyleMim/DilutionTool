"""Filters for identifying SPACs, ETFs, funds, bonds, and other non-equity securities."""

import re

SPAC_PATTERNS = [
    r"\bAcquisition\b",
    r"\bBlank\s+Check\b",
    r"\bSPAC\b",
    r"\bMerger\s+Corp",
    r"\bMerger\s+Sub\b",
    r"\bSpecial\s+Purpose\b",
]

_SPAC_REGEX = re.compile("|".join(SPAC_PATTERNS), re.IGNORECASE)


def is_spac_name(name: str) -> bool:
    """Check if a company name matches SPAC patterns."""
    if not name:
        return False
    return bool(_SPAC_REGEX.search(name))


# Patterns that indicate non-equity securities (ETFs, funds, bonds, notes, preferred, etc.)
NON_EQUITY_NAME_PATTERNS = [
    r"\bETF\b",
    r"\bIndex\s+Fund\b",
    r"\bMutual\s+Fund\b",
    r"\bMunicipal\b",
    r"\bSenior\s+Notes\b",
    r"\bSubordinated\s+Notes\b",
    r"\bDebenture",
    r"\bPerpetual\s+(Subordinated|Preferred)",
    r"\d+(\.\d+)?%",  # "5.875% Senior Notes", "9.125% Seni..."
    r"\bProShares\b",
    r"\biShares\b",
    r"\bSPDR\b",
    r"\bVanguard\b",
    r"\bIncome\s+Trust\b",
    r"\bBond\s+Trust\b",
    r"\bFloating\s+Rate\b",
    r"\bIncome\s+Term\s+Trust\b",
    r"\bEquity\s+Trust\b",
    r"\bUtility\s+Trust\b",
    r"\bValue\s+Trust\b",
    r"\bMicro-Cap\s+Trust\b",
    r"\bStrategic\s+Value\b",
    r"\bNatural\s+Gas\s+Fund\b",
    r"\bPhysical\s+(Platinum|Palladium|Gold|Silver)\b",
]

_NON_EQUITY_NAME_REGEX = re.compile("|".join(NON_EQUITY_NAME_PATTERNS), re.IGNORECASE)

# Closed-end funds / mutual funds often have these in the name
FUND_NAME_PATTERNS = [
    r"\bFund\b(?!.*(Funding|Fundamental))",  # "Fund" but not "Funding" or "Fundamental"
]

_FUND_NAME_REGEX = re.compile("|".join(FUND_NAME_PATTERNS), re.IGNORECASE)


def is_non_equity(ticker: str, name: str) -> bool:
    """Check if a security is a non-equity product (ETF, fund, bond, note, preferred).

    Returns True for securities that should be excluded from dilution tracking.
    """
    if not name:
        return False

    # Name-based patterns (ETFs, bonds, notes)
    if _NON_EQUITY_NAME_REGEX.search(name):
        return True

    # Fund names
    if _FUND_NAME_REGEX.search(name):
        return True

    # 5-letter tickers ending in X are almost always mutual funds
    if ticker and re.match(r"^[A-Z]{5}$", ticker) and ticker.endswith("X"):
        return True

    # Tickers with -P (preferred shares) e.g. EFC-PE
    if ticker and "-P" in ticker:
        return True

    return False
