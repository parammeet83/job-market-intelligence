from decimal import Decimal

import pytest

from backend.ingestion.transformations.dedup import canonical_url, cross_source_key, dedup_key
from backend.ingestion.transformations.locations import classify_work_mode, normalize_location
from backend.ingestion.transformations.roles import load_role_rules
from backend.ingestion.transformations.salary import (
    check_salary,
    from_structured,
    normalize_currency,
    normalize_period,
    parse_salary_text,
)
from backend.ingestion.transformations.text import clean_inline, html_to_text
from backend.ingestion.transformations.titles import infer_seniority, normalize_title

# --- titles -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Senior Product Marketing Manager | Sweden | Remote", "Senior Product Marketing Manager"),
        ("Sr. DevOps Engineer", "Senior DevOps Engineer"),
        ("Jr Data Analyst", "Junior Data Analyst"),
        ("  Data   Engineer  ", "Data Engineer"),
        ("Machine Learning Engineer (Remote)", "Machine Learning Engineer"),
        ("Backend Engineer - Remote (US)", "Backend Engineer"),
        ("Data &amp; Analytics Lead", "Data & Analytics Lead"),
        # Meaningful qualifiers are not removed.
        ("Data Analyst (SQL, Python)", "Data Analyst (SQL, Python)"),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


def test_normalize_title_never_empty() -> None:
    assert normalize_title("| Remote") == "| Remote"


@pytest.mark.parametrize(
    ("title", "level", "expected"),
    [
        ("Senior Data Analyst", None, "senior"),
        ("Data Analyst", "Midweight", "mid"),
        ("Staff Engineer", None, "staff"),
        ("Head of Data", None, "executive"),
        ("Data Analyst Intern", None, "intern"),
        ("Data Analyst", None, None),
        ("Data Analyst", "Any", None),
    ],
)
def test_infer_seniority(title: str, level: str | None, expected: str | None) -> None:
    assert infer_seniority(title, level) == expected


# --- roles --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Data Analyst", "Data Analyst"),
        ("Analytics Engineer", "Analytics Engineer"),
        ("Machine Learning Engineer", "Machine Learning Engineer"),
        ("Data Engineer", "Data Engineer"),
        ("BI Analyst", "Business Intelligence Analyst"),
        ("Business Analyst", "Business Analyst"),
        ("Data Scientist II", "Data Scientist"),
        ("Senior Software Engineer", "Software Engineer"),
        ("Full-Stack Developer", "Software Engineer"),
        ("Site Reliability Engineer", "DevOps / Cloud Engineer"),
        ("Account Executive", None),
        ("Uber Driver", None),
    ],
)
def test_role_classification(title: str, expected: str | None) -> None:
    assert load_role_rules().classify(title) == expected


def test_specific_roles_win_over_generic() -> None:
    # "Data Engineer" must not swallow "Analytics Engineer"; "ML Engineer" not "Software".
    rules = load_role_rules()
    assert rules.classify("Senior Analytics Engineer (dbt)") == "Analytics Engineer"
    assert rules.classify("ML Engineer, Platform") == "Machine Learning Engineer"


# --- locations ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "city", "region", "country"),
    [
        ("USA", None, None, "United States"),
        ("UK", None, None, "United Kingdom"),
        ("India", None, None, "India"),
        ("Seattle, Washington", "Seattle", "Washington", "United States"),
        ("Austin, TX", "Austin", "Texas", "United States"),
        ("Bengaluru, Karnataka", "Bengaluru", "Karnataka", "India"),
        ("Berlin, Germany", "Berlin", None, "Germany"),
        ("Pune, Maharashtra, India", "Pune", "Maharashtra", "India"),
        # Ambiguous or multi-place strings stay unstructured.
        ("Canada, USA", None, None, None),
        ("Europe, Israel", None, None, None),
        ("EMEA", None, None, None),
        ("Berlin; Munich", None, None, None),
        ("Springfield", None, None, None),
    ],
)
def test_normalize_location(
    raw: str, city: str | None, region: str | None, country: str | None
) -> None:
    loc = normalize_location(raw)
    assert (loc.city, loc.region, loc.country) == (city, region, country)
    assert loc.original == raw


def test_location_worldwide_and_empty() -> None:
    assert normalize_location("Anywhere").worldwide is True
    assert normalize_location("Remote").country is None
    assert normalize_location("").original is None
    assert normalize_location(None).original is None


def test_work_mode_classification() -> None:
    assert classify_work_mode("Data Analyst (Hybrid)", None, source_default="remote") == (
        "hybrid",
        "text",
    )
    assert classify_work_mode("Engineer", "On-site in Pune", source_default="remote") == (
        "onsite",
        "text",
    )
    assert classify_work_mode("Engineer", "USA", source_default="remote") == (
        "remote",
        "source_default",
    )
    assert classify_work_mode("Engineer", None, source_default=None) == (None, None)


# --- salary -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lo", "hi", "cur", "per"),
    [
        ("$100k - $140k per year", 100000, 140000, "USD", "year"),
        ("€50,000–60,000 annually", 50000, 60000, "EUR", "year"),
        ("£45,000 - £55,000 p.a.", 45000, 55000, "GBP", "year"),
        ("USD 40/hour", 40, 40, "USD", "hour"),
        ("12-18 LPA", 1200000, 1800000, "INR", "year"),
        ("₹8,00,000 - ₹12,00,000 per annum", 800000, 1200000, "INR", "year"),
        ("100-140k USD a year", 100000, 140000, "USD", "year"),
        ("CAD 6,000 to 7,500 monthly", 6000, 7500, "CAD", "month"),
    ],
)
def test_parse_salary_text(
    text: str, lo: int | None, hi: int | None, cur: str | None, per: str | None
) -> None:
    s = parse_salary_text(text)
    if lo is None:
        assert s.minimum is None and s.maximum is None
    else:
        assert (s.minimum, s.maximum, s.currency, s.period) == (Decimal(lo), Decimal(hi), cur, per)
    assert s.text is not None


@pytest.mark.parametrize("text", ["Competitive", "$120,000", "100000 - 150000", "DOE"])
def test_ambiguous_salary_keeps_text_without_numbers(text: str) -> None:
    s = parse_salary_text(text)
    assert s.text == text
    assert s.minimum is None and s.maximum is None and s.currency is None


def test_missing_salary_is_unknown_not_zero() -> None:
    s = parse_salary_text(None)
    assert s.text is None and s.minimum is None and not s.disclosed
    s = from_structured(0, 0, "USD", "yearly")
    assert s.minimum is None and s.maximum is None and not s.disclosed


def test_structured_salary() -> None:
    s = from_structured(82988, 99586, "EUR", "yearly")
    assert (s.minimum, s.maximum, s.currency, s.period) == (
        Decimal(82988),
        Decimal(99586),
        "EUR",
        "year",
    )
    assert s.text == "82,988–99,586 EUR yearly"


def test_structured_salary_without_currency_keeps_unit_unknown() -> None:
    s = from_structured(10, 10, "", "hourly")
    assert s.currency is None and s.period == "hour"
    assert "currency not stated" in (s.text or "")


@pytest.mark.parametrize(
    ("lo", "hi", "cur", "per", "issue"),
    [
        (80000, 60000, "GBP", "year", "min_greater_than_max"),
        (10000, 900000, "USD", "year", "implausible_range_width"),
        (120, 150, "USD", "year", "implausible_value_for_period"),
        (50000, 60000, "USD", "hour", "implausible_value_for_period"),
    ],
)
def test_inconsistent_salary_is_rejected(lo: int, hi: int, cur: str, per: str, issue: str) -> None:
    assert check_salary(Decimal(lo), Decimal(hi), cur, per) == issue
    s = from_structured(lo, hi, cur, per)
    assert s.issue == issue and s.minimum is None and s.text is not None


def test_currency_and_period_normalization() -> None:
    assert normalize_currency("$") == "USD"
    assert normalize_currency("inr") == "INR"
    assert normalize_currency("XYZ") is None
    assert normalize_period("Yearly") == "year"
    assert normalize_period("per hour") == "hour"
    assert normalize_period("fortnightly") is None


# --- text, urls, dedup --------------------------------------------------------------------


def test_html_to_text_handles_double_escaping() -> None:
    assert html_to_text("&lt;p&gt;SQL &amp;amp; Python&lt;/p&gt;") == "SQL & Python"
    assert html_to_text("<div><script>x()</script>Hi <b>there</b></div>") == "Hi there"
    assert html_to_text(None) == ""
    assert clean_inline("  a \n b ") == "a b"
    assert clean_inline("   ") is None


def test_canonical_url() -> None:
    assert canonical_url("HTTP://RemoteOK.com/remote-jobs/x-1/?utm_source=a&b=2#frag") == (
        "https://remoteok.com/remote-jobs/x-1?b=2"
    )
    assert canonical_url("https://jobicy.com/jobs/1?ref=feed") == "https://jobicy.com/jobs/1"


def test_dedup_key_priority() -> None:
    assert dedup_key("jobicy", "123", "https://jobicy.com/jobs/1", "T", "C", "L") == "jobicy:id:123"
    assert dedup_key("x", None, "https://x.com/a?utm_source=z", "T", "C", "L") == (
        "x:url:https://x.com/a"
    )
    fp1 = dedup_key("x", None, None, "Data  Analyst", "ACME", "USA")
    fp2 = dedup_key("x", None, None, "data analyst", "acme", "usa")
    assert fp1 == fp2 and fp1.startswith("x:fp:")


def test_cross_source_key_ignores_company_suffix() -> None:
    assert cross_source_key("Data Engineer", "Acme Inc.") == cross_source_key(
        "data engineer", "ACME"
    )
