"""Remote OK public API adapter.

Endpoint: GET https://remoteok.com/api (single JSON array; element 0 is a legal notice).
* Terms (from the API's own `legal` field): link back to the Remote OK listing URL and name
  Remote OK as the source; do not use the Remote OK logo.
* The feed is a rolling window of recent listings, so absence is not evidence of closure.
* `salary_min`/`salary_max` are integers where 0 means "not provided". The API does not
  state currency or pay period, so those stay unknown and the figures are excluded from
  currency-specific salary statistics.
"""

from datetime import UTC, datetime
from typing import Any

from backend.ingestion.http import SourceFetchError
from backend.ingestion.sources.base import FetchResult, ParsedJob, ParseError, SourceAdapter

SALARY_NOTE = "Currency and pay period not stated by Remote OK"


def _parse_dt(record: dict[str, Any]) -> datetime | None:
    value = record.get("date")
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    epoch = record.get("epoch")
    if isinstance(epoch, int | float) and epoch > 0:
        return datetime.fromtimestamp(epoch, UTC)
    return None


def _positive(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class RemoteOkAdapter(SourceAdapter):
    def _payload(self) -> list[Any]:
        payload = self.client.get_json(self.config.api_url)
        if not isinstance(payload, list) or not payload:
            raise SourceFetchError("unexpected payload shape")
        return payload

    def fetch(self) -> FetchResult:
        fetched_at = datetime.now(UTC)
        payload = self._payload()
        records = [r for r in payload if isinstance(r, dict) and "id" in r and "position" in r]
        meta = payload[0] if isinstance(payload[0], dict) and "legal" in payload[0] else {}
        updated = meta.get("last_updated")
        updated_at = datetime.fromtimestamp(updated, UTC) if isinstance(updated, int) else None
        return FetchResult(records, True, fetched_at, updated_at)

    def parse(self, record: dict[str, Any]) -> ParsedJob:
        job_id = record.get("id")
        if job_id in (None, ""):
            raise ParseError("missing_source_id")
        lo, hi = _positive(record.get("salary_min")), _positive(record.get("salary_max"))
        salary_text = None
        if lo or hi:
            salary_text = "–".join(str(v) for v in (lo, hi) if v) + f" ({SALARY_NOTE})"
        return ParsedJob(
            source_job_id=str(job_id),
            url=record.get("url"),
            title=record.get("position"),
            company=record.get("company"),
            location=record.get("location"),
            description_html=record.get("description"),
            tags=[str(t) for t in record.get("tags") or []],
            published_at=_parse_dt(record),
            salary_min=lo,
            salary_max=hi,
            salary_text=salary_text,
            salary_note=SALARY_NOTE if salary_text else None,
        )

    def health_check(self) -> dict[str, Any]:
        payload = self._payload()
        return {"ok": True, "records": max(0, len(payload) - 1)}
