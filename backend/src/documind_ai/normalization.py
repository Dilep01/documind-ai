"""Conservative conversions: ambiguous or malformed values require review."""

import re
from datetime import date, datetime
from decimal import Decimal


class AmbiguousDateError(ValueError):
    pass


def parse_money(raw: str) -> Decimal:
    value = re.sub(r"^(?:INR\s*|Rs\.?\s*|₹\s*)", "", raw.strip(), flags=re.IGNORECASE)
    number = r"-?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?"
    if not re.fullmatch(number, value, flags=re.ASCII):
        raise ValueError("Expected an amount with at most two decimal places")
    digits = value.replace(",", "").lstrip("-")
    if len(digits.split(".")[0]) > 16:
        raise ValueError("Amount is outside the supported range")
    return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))


def parse_date(raw: str) -> date:
    value = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, flags=re.ASCII):
        return date.fromisoformat(value)
    numeric = re.fullmatch(r"(\d{1,2})([/-])(\d{1,2})\2(\d{4})", value, flags=re.ASCII)
    if numeric:
        first, second, year = int(numeric[1]), int(numeric[3]), int(numeric[4])
        if 1 <= first <= 12 and 1 <= second <= 12 and first != second:
            raise AmbiguousDateError("Use an ISO date or a written month to resolve this date")
        if first > 12 or first == second:
            return date(year, second, first)
        return date(year, first, second)
    for pattern in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError("Unrecognized or invalid date")


def parse_text(raw: str) -> str:
    value = raw.strip()
    if not value or len(value) > 256:
        raise ValueError("Expected between 1 and 256 characters")
    return value


def parse_currency(raw: str) -> str:
    value = raw.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError("Expected an explicit three-letter currency code")
    return value
