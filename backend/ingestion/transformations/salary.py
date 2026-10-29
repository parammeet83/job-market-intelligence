"""Salary normalization.

Rules:
* Missing salary is unknown (None), never zero.
* Minimum, maximum, currency and pay period are kept separately with the original text.
* Values are normalized only when unambiguous; otherwise numeric fields stay None.
* Currencies are never converted and periods are never annualised here.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

PERIOD_ALIASES = {
    "hour": "hour",
    "hourly": "hour",
    "hr": "hour",
    "h": "hour",
    "per hour": "hour",
    "day": "day",
    "daily": "day",
    "per day": "day",
    "week": "week",
    "weekly": "week",
    "wk": "week",
    "month": "month",
    "monthly": "month",
    "mo": "month",
    "pm": "month",
    "per month": "month",
    "year": "year",
    "yearly": "year",
    "annual": "year",
    "annually": "year",
    "yr": "year",
    "pa": "year",
    "per annum": "year",
    "p.a.": "year",
    "per year": "year",
}
SALARY_PERIOD_VALUES = ("hour", "day", "week", "month", "year")
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
KNOWN_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "INR",
    "CAD",
    "AUD",
    "NZD",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "JPY",
    "SGD",
    "HKD",
    "BRL",
    "MXN",
    "ZAR",
    "AED",
    "ILS",
    "RON",
    "HUF",
    "CNY",
    "KRW",
    "PHP",
}
# Generous plausibility bounds per period (in any currency); values outside are rejected
# rather than guessed. They exist to catch unit errors (e.g. 120 as an annual salary).
PLAUSIBLE_RANGE = {
    "hour": (Decimal("1"), Decimal("20000")),
    "day": (Decimal("5"), Decimal("150000")),
    "week": (Decimal("20"), Decimal("750000")),
    "month": (Decimal("50"), Decimal("5000000")),
    "year": (Decimal("1000"), Decimal("500000000")),
}
MAX_RANGE_RATIO = Decimal("10")


@dataclass(frozen=True)
class Salary:
    text: str | None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    currency: str | None = None
    period: str | None = None
    issue: str | None = None  # why numeric normalization was refused, if it was

    @property
    def disclosed(self) -> bool:
        return self.text is not None or self.minimum is not None or self.maximum is not None


def normalize_period(value: str | None) -> str | None:
    if not value:
        return None
    return PERIOD_ALIASES.get(value.strip().lower())


def normalize_currency(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[value]
    upper = value.upper()
    return upper if upper in KNOWN_CURRENCIES else None


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None
    return number if number > 0 else None


def check_salary(
    minimum: Decimal | None, maximum: Decimal | None, currency: str | None, period: str | None
) -> str | None:
    """Return a rejection reason, or None if the structured salary is consistent."""
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum > maximum:
        return "min_greater_than_max"
    if minimum is not None and maximum is not None and maximum > minimum * MAX_RANGE_RATIO:
        return "implausible_range_width"
    if period is not None:
        low, high = PLAUSIBLE_RANGE[period]
        for value in (minimum, maximum):
            if value is not None and not (low <= value <= high):
                return "implausible_value_for_period"
    if currency is not None and currency not in KNOWN_CURRENCIES:
        return "unknown_currency"
    return None


def from_structured(
    minimum: object, maximum: object, currency: object, period: object, *, text: str | None = None
) -> Salary:
    """Salary from separate numeric source fields (e.g. Jobicy salaryMin/Max/Currency/Period)."""
    lo, hi = _to_decimal(minimum), _to_decimal(maximum)
    cur = normalize_currency(str(currency)) if currency else None
    per = normalize_period(str(period)) if period else None
    if lo is None and hi is None:
        return Salary(text=text)
    if text is None:
        amounts = [v for v in (lo, hi) if v is not None]
        text = "–".join(f"{v:,.0f}" for v in dict.fromkeys(amounts))
        unit = " ".join(x for x in (str(currency or "").strip(), str(period or "").strip()) if x)
        text = f"{text} {unit}".strip()
        if cur is None:
            text += " (currency not stated)"
    issue = check_salary(lo, hi, cur, per)
    if issue:
        return Salary(text=text, issue=issue)
    return Salary(text=text, minimum=lo, maximum=hi, currency=cur, period=per)


# Western grouping (1,200,000), Indian lakh/crore grouping (12,00,000) or plain digits.
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,2}(?:,\d{2})+,\d{3}|\d+(?:\.\d+)?"
_SUFFIX = r"[kKmM]\b|(?i:lpa|lakhs?|lacs?)\b"
# Currency symbol or an upper-case ISO-style code (validated by normalize_currency).
_CUR = r"[$€£₹]|\b[A-Z]{3}\b"
_RANGE = re.compile(
    rf"(?P<cur1>{_CUR})?\s*(?P<a>{_NUM})\s*(?P<asuf>{_SUFFIX})?"
    rf"\s*(?:-|–|—|\bto\b)\s*(?P<cur2>{_CUR})?\s*(?P<b>{_NUM})\s*(?P<bsuf>{_SUFFIX})?"
)
_SINGLE = re.compile(rf"(?P<cur1>{_CUR})\s*(?P<a>{_NUM})\s*(?P<asuf>{_SUFFIX})?")
_PERIOD_IN_TEXT = re.compile(
    r"(?P<pa>\bp\.?\s?a\.?(?!\w))"
    r"|(?:/|\bper\b|\ba\b|\ban\b)\s*(?P<unit>hour|hr|h|day|week|wk|month|mo|year|yr|annum)\b"
    r"|\b(?P<adj>hourly|daily|weekly|monthly|yearly|annual(?:ly)?)\b",
    re.I,
)
_TRAILING_CODE = re.compile(r"\b([A-Z]{3})\b")


def _scale(amount: str, suffix: str | None) -> Decimal | None:
    value = _to_decimal(amount)
    if value is None:
        return None
    s = (suffix or "").lower()
    if s == "k":
        return value * 1000
    if s == "m":
        return value * 1_000_000
    if s in {"lpa", "lakh", "lakhs", "lac", "lacs"}:
        return value * 100_000
    return value


def parse_salary_text(raw: str | None) -> Salary:
    """Parse free-text salaries such as "$100k - $140k per year", "€50,000–60,000 annually",
    "USD 40/hour" or "12-18 LPA". Ambiguous text is retained with numeric fields left None."""
    if raw is None or not raw.strip():
        return Salary(text=None)
    text = " ".join(raw.split())
    match = _RANGE.search(text) or _SINGLE.search(text)
    if not match:
        return Salary(text=text, issue="unparseable")
    groups = match.groupdict()
    lo = _scale(groups["a"], groups.get("asuf"))
    hi = _scale(groups["b"], groups.get("bsuf")) if groups.get("b") else lo
    if groups.get("b") and groups.get("bsuf") and not groups.get("asuf"):
        # "100-140k": the suffix applies to both ends.
        lo = _scale(groups["a"], groups["bsuf"])
    currency = normalize_currency(groups.get("cur1")) or normalize_currency(groups.get("cur2"))
    if currency is None:
        trailing = _TRAILING_CODE.search(text[match.end() :])
        currency = normalize_currency(trailing.group(1)) if trailing else None
    lowered = text.lower()
    if currency is None and re.search(r"\b(lpa|lakhs?|lacs?)\b", lowered):
        currency = "INR"
    period = None
    pm = _PERIOD_IN_TEXT.search(text)
    if pm and pm.group("pa"):
        period = "year"
    elif pm:
        unit = (pm.group("unit") or pm.group("adj")).lower()
        period = normalize_period("year" if unit == "annum" else unit)
    elif re.search(r"\b(lpa|ctc)\b", lowered):
        period = "year"
    if currency is None or period is None:
        return Salary(text=text, issue="missing_currency_or_period")
    issue = check_salary(lo, hi, currency, period)
    if issue:
        return Salary(text=text, issue=issue)
    return Salary(text=text, minimum=lo, maximum=hi, currency=currency, period=period)
