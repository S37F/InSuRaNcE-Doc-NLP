"""Formatting helpers for currency and date normalization."""

from __future__ import annotations

import logging
import re

from dateutil import parser

logger = logging.getLogger(__name__)


def normalise_currency(value: str) -> float | None:
    """Normalise a currency-like string to float.

    Args:
        value: Raw text that may contain currency symbols, codes, and separators.

    Returns:
        Parsed numeric value as float, or None when parsing fails.
    """
    if not value:
        return None

    try:
        cleaned: str = re.sub(r"(?i)\b(?:usd|inr|rs)\b", "", value)
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        if cleaned.count(".") > 1:
            parts: list[str] = cleaned.split(".")
            cleaned = f"{''.join(parts[:-1])}.{parts[-1]}"
        if cleaned in {"", ".", "-", "-."}:
            return None
        return float(cleaned)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to normalise currency '%s': %s", value, exc)
        return None


def normalise_date(value: str) -> str | None:
    """Normalise a date-like string to ISO format (YYYY-MM-DD).

    Args:
        value: Raw date text.

    Returns:
        ISO-formatted date string, or None when parsing fails.
    """
    if not value:
        return None

    if not re.search(r"\d", value):
        return None
    explicit_date_pattern = (
        r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"[a-z]*\s+\d{1,2},?\s+\d{4})"
    )
    match = re.search(explicit_date_pattern, value, flags=re.IGNORECASE)
    if not match:
        return None
    date_text: str = match.group(0)

    try:
        parsed = parser.parse(date_text, dayfirst=False, fuzzy=False)
        return parsed.date().isoformat()
    except (ValueError, TypeError, OverflowError):
        try:
            parsed = parser.parse(date_text, dayfirst=False, fuzzy=True)
            return parsed.date().isoformat()
        except (ValueError, TypeError, OverflowError) as exc:
            logger.warning("Failed to normalise date '%s': %s", value, exc)
            return None
