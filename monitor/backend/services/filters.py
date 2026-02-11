"""Filters for identifying SPACs and other non-operating companies."""

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
