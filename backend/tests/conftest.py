"""Shared test helpers. Integration tests need TEST_DATABASE_URL pointing at a DISPOSABLE
database whose name contains "test"; its public schema is dropped and rebuilt."""

import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from backend.ingestion.config import SourceConfig, load_source_configs
from backend.ingestion.http import SourceFetchError
from backend.ingestion.sources.base import FetchResult
from backend.ingestion.sources.jobicy import JobicyAdapter
from backend.ingestion.sources.remoteok import RemoteOkAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def source_configs() -> dict[str, SourceConfig]:
    return load_source_configs()


class FakeClient:
    """Stands in for HttpClient; never touches the network."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.request_count = 0
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.request_count += 1
        self.calls.append((url, params))
        value = self.responses.get(url)
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value(params)
        return deepcopy(value)


class StaticJobicy(JobicyAdapter):
    """Jobicy adapter whose fetch returns given records (for pipeline tests)."""

    def __init__(
        self,
        config: SourceConfig,
        records: list[dict[str, Any]],
        *,
        fetched_at: datetime,
        complete: bool = True,
        status: dict[str, str] | None = None,
        fail: bool = False,
    ) -> None:
        super().__init__(config, client=FakeClient())  # type: ignore[arg-type]
        self._records, self._fetched_at, self._complete = records, fetched_at, complete
        self._status, self._fail = status or {}, fail

    def fetch(self) -> FetchResult:
        if self._fail:
            raise SourceFetchError("HTTP 503")
        return FetchResult(
            deepcopy(self._records),
            self._complete,
            self._fetched_at,
            errors=[] if self._complete else ["page 2: HTTP 503"],
        )

    def check_status(self, source_job_ids: list[str]) -> dict[str, str]:
        return {i: self._status[i] for i in source_job_ids if i in self._status}


class StaticRemoteOk(RemoteOkAdapter):
    def __init__(
        self,
        config: SourceConfig,
        records: list[dict[str, Any]],
        *,
        fetched_at: datetime,
        fail: bool = False,
    ) -> None:
        super().__init__(config, client=FakeClient())  # type: ignore[arg-type]
        self._records, self._fetched_at, self._fail = records, fetched_at, fail

    def fetch(self) -> FetchResult:
        if self._fail:
            raise SourceFetchError("ConnectTimeout")
        return FetchResult(deepcopy(self._records), True, self._fetched_at)


def day(n: int) -> datetime:
    return datetime(2026, 11, n, 6, 0, tzinfo=UTC)


def get_test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or _dotenv_value("TEST_DATABASE_URL")


def _dotenv_value(key: str) -> str | None:
    env = Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip() or None
    return None
