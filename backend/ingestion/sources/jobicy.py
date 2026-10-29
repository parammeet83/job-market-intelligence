"""Jobicy public jobs API adapter.

Docs: https://jobicy.com/jobs-rss-feed  (GET https://jobicy.com/api/jobs, no key).
* The feed only contains jobs published within the last 7 days, so absence from the feed is
  NOT evidence that a listing closed. Closure is taken only from the batch status endpoint
  (GET /api/jobs/status?ids=...), which reports active / closed / unknown.
* Paginated with an opaque `cursor` (`nextCursor`/`hasMore`), up to 200 items per page.
* Terms: credit Jobicy with a link; apply links must point to the Jobicy listing; storing and
  redistributing job data is permitted.
"""

from datetime import UTC, datetime
from typing import Any

from backend.core.logging import safe_error_summary
from backend.ingestion.http import SourceFetchError
from backend.ingestion.sources.base import FetchResult, ParsedJob, ParseError, SourceAdapter

STATUS_BATCH = 100


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


class JobicyAdapter(SourceAdapter):
    def _page(self, params: dict[str, Any]) -> dict[str, Any]:
        payload = self.client.get_json(self.config.api_url, params=params)
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise SourceFetchError("unexpected payload shape")
        return payload

    def fetch(self) -> FetchResult:
        opts = self.config.options
        industries: list[str] = list(opts.get("industries", [])) or [""]
        page_size = int(opts.get("page_size", 200))
        max_pages = int(opts.get("max_pages_per_industry", 10))
        fetched_at = datetime.now(UTC)
        records: list[dict[str, Any]] = []
        errors: list[str] = []
        complete = True
        updated_at: datetime | None = None
        succeeded_pages = 0
        for industry in industries:
            cursor: str | None = None
            for _ in range(max_pages):
                params: dict[str, Any] = {"count": page_size}
                if industry:
                    params["industry"] = industry
                if cursor:
                    params["cursor"] = cursor
                try:
                    payload = self._page(params)
                except SourceFetchError as exc:
                    complete = False
                    errors.append(f"industry={industry or 'all'}: {safe_error_summary(exc)}")
                    break
                succeeded_pages += 1
                records.extend(payload["jobs"])
                updated_at = updated_at or _parse_dt(payload.get("lastUpdate"))
                cursor = payload.get("nextCursor")
                if not payload.get("hasMore") or not cursor:
                    break
            else:
                # Page limit reached while the source still reported more results.
                complete = False
                errors.append(f"industry={industry or 'all'}: stopped at max_pages={max_pages}")
        if succeeded_pages == 0:
            raise SourceFetchError("; ".join(errors) or "no pages fetched")
        return FetchResult(records, complete, fetched_at, updated_at, errors)

    def parse(self, record: dict[str, Any]) -> ParsedJob:
        job_id = record.get("id")
        if job_id in (None, ""):
            raise ParseError("missing_source_id")
        return ParsedJob(
            source_job_id=str(job_id),
            url=record.get("url"),
            title=record.get("jobTitle"),
            company=record.get("companyName"),
            location=record.get("jobGeo"),
            description_html=record.get("jobDescription") or record.get("jobExcerpt"),
            tags=[str(t) for t in record.get("jobIndustry") or []],
            published_at=_parse_dt(record.get("pubDate")),
            employment_type_raw=_first(record.get("jobType")),
            level_raw=record.get("jobLevel"),
            salary_min=record.get("salaryMin"),
            salary_max=record.get("salaryMax"),
            salary_currency=record.get("salaryCurrency"),
            salary_period=record.get("salaryPeriod"),
        )

    def health_check(self) -> dict[str, Any]:
        payload = self._page({"count": 1})
        return {"ok": bool(payload.get("success", True)), "last_update": payload.get("lastUpdate")}

    def check_status(self, source_job_ids: list[str]) -> dict[str, str]:
        status_url = self.config.options.get("status_url")
        if not status_url:
            return {}
        results: dict[str, str] = {}
        ids = [i for i in source_job_ids if i.isdigit()]
        for start in range(0, len(ids), STATUS_BATCH):
            batch = ids[start : start + STATUS_BATCH]
            payload = self.client.get_json(status_url, params={"ids": ",".join(batch)})
            for item in (payload or {}).get("jobs", []):
                status = str(item.get("status", "unknown"))
                if status in ("active", "closed", "unknown"):
                    results[str(item.get("id"))] = status
        return results
