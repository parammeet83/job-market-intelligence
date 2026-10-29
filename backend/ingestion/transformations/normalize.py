"""Shared normalization: ParsedJob (source-specific shape) -> validated JobRecord."""

import re
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from backend.ingestion.config import SourceConfig
from backend.ingestion.skills.extractor import SkillDictionary
from backend.ingestion.sources.base import ParsedJob
from backend.ingestion.transformations.dedup import canonical_url, cross_source_key, dedup_key
from backend.ingestion.transformations.locations import classify_work_mode, normalize_location
from backend.ingestion.transformations.roles import RoleRules
from backend.ingestion.transformations.salary import from_structured, parse_salary_text
from backend.ingestion.transformations.text import clean_inline, html_to_text
from backend.ingestion.transformations.titles import infer_seniority, normalize_title
from backend.ingestion.validation.contracts import JobRecord, reason_code

_EMPLOYMENT = {
    "full-time": "full_time",
    "full time": "full_time",
    "fulltime": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "temporary": "temporary",
    "temp": "temporary",
    "internship": "internship",
    "intern": "internship",
    "freelance": "freelance",
}


class InvalidRecord(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class NormalizeOutcome:
    record: JobRecord | None
    out_of_scope: bool = False
    salary_issue: str | None = None


def normalize_employment_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return _EMPLOYMENT.get(re.sub(r"\s+", " ", raw.strip().lower()))


def normalize_job(
    parsed: ParsedJob,
    *,
    source: SourceConfig,
    observed_at: datetime,
    skills: SkillDictionary,
    roles: RoleRules,
) -> NormalizeOutcome:
    """Raise InvalidRecord with a safe reason when required data is missing or malformed."""
    title_original = clean_inline(parsed.title)
    if not title_original:
        raise InvalidRecord("missing_title")
    if not parsed.url:
        raise InvalidRecord("missing_url")
    try:
        url = canonical_url(parsed.url)
    except ValueError as exc:
        raise InvalidRecord("invalid_url") from exc

    title = normalize_title(title_original)
    role = roles.classify(title)
    if role is None and source.require_role_match:
        return NormalizeOutcome(record=None, out_of_scope=True)

    company = clean_inline(parsed.company)
    location = normalize_location(parsed.location)
    work_mode, basis = classify_work_mode(
        title_original, location.original, source_default=source.default_work_mode
    )
    if parsed.salary_text is not None and parsed.salary_currency is None and parsed.salary_note:
        # Source states amounts without currency/period: keep the amounts, leave units unknown.
        salary = from_structured(
            parsed.salary_min, parsed.salary_max, None, None, text=parsed.salary_text
        )
    elif parsed.salary_min is not None or parsed.salary_max is not None:
        salary = from_structured(
            parsed.salary_min,
            parsed.salary_max,
            parsed.salary_currency,
            parsed.salary_period,
            text=parsed.salary_text,
        )
    else:
        salary = parse_salary_text(parsed.salary_text)

    description = html_to_text(parsed.description_html)
    tags = tuple(dict.fromkeys(t.strip() for t in parsed.tags if t and t.strip()))[:50]
    found_skills = skills.extract(
        {"title": title_original, "tags": " ; ".join(tags), "description": description}
    )
    try:
        record = JobRecord.model_validate(
            {
                "source_id": source.id,
                "source_job_id": parsed.source_job_id,
                "canonical_url": url,
                "allowed_hosts": tuple(h.lower() for h in source.allowed_hosts),
                "dedup_key": dedup_key(
                    source.id, parsed.source_job_id, url, title, company, location.original
                ),
                "cross_source_key": cross_source_key(title, company),
                "title_original": title_original[:500],
                "title_normalized": title[:500],
                "role_category": role,
                "company": company[:300] if company else None,
                "location_original": location.original,
                "city": location.city,
                "region": location.region,
                "country": location.country,
                "work_mode": work_mode,
                "work_mode_basis": basis,
                "employment_type": normalize_employment_type(parsed.employment_type_raw),
                "seniority": infer_seniority(title, parsed.level_raw),
                "salary_text": salary.text[:300] if salary.text else None,
                "salary_min": salary.minimum,
                "salary_max": salary.maximum,
                "salary_currency": salary.currency,
                "salary_period": salary.period,
                "source_tags": tags,
                "published_at": parsed.published_at,
                "observed_at": observed_at,
                "description_text": description,
                "skills": found_skills,
            }
        )
    except ValidationError as exc:
        raise InvalidRecord(reason_code(exc)) from exc
    return NormalizeOutcome(record=record, salary_issue=salary.issue)
