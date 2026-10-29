"""Source adapter interface. Adapters know a source's wire format; everything after
`parse()` (normalization, validation, skills, persistence) is shared."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.ingestion.config import SourceConfig
from backend.ingestion.http import HttpClient


class ParseError(ValueError):
    """A record could not be mapped to the canonical shape; the message is a safe reason code."""


@dataclass
class ParsedJob:
    """Source-agnostic, not yet normalized job record."""

    source_job_id: str | None
    url: str | None
    title: str | None
    company: str | None
    location: str | None
    description_html: str | None = None
    tags: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    employment_type_raw: str | None = None
    level_raw: str | None = None
    salary_min: Any = None
    salary_max: Any = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    # Note shown with the salary when the source omits currency or period.
    salary_note: str | None = None


@dataclass
class FetchResult:
    records: list[dict[str, Any]]
    complete: bool
    fetched_at: datetime
    source_updated_at: datetime | None = None
    errors: list[str] = field(default_factory=list)


class SourceAdapter(ABC):
    def __init__(self, config: SourceConfig, client: HttpClient | None = None) -> None:
        self.config = config
        self.client = client or HttpClient(
            list(config.allowed_hosts), min_interval=config.min_request_interval_seconds
        )

    @property
    def source_id(self) -> str:
        return self.config.id

    @property
    def request_count(self) -> int:
        return self.client.request_count

    @abstractmethod
    def fetch(self) -> FetchResult:
        """Retrieve raw records. Must not raise for partial failures: return what was
        collected with `complete=False` and safe error messages. Raise SourceFetchError only
        when nothing could be fetched."""

    @abstractmethod
    def parse(self, record: dict[str, Any]) -> ParsedJob:
        """Map one raw record to ParsedJob or raise ParseError."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Minimal request proving the source answers; returns safe status details."""

    def check_status(self, source_job_ids: list[str]) -> dict[str, str]:
        """Explicit active/closed/unknown status per id. Sources without such an API return {}."""
        return {}
