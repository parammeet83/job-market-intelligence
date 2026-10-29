"""Polite, bounded HTTP client for source adapters.

* Only hosts on the source's allow-list can be requested (SSRF protection).
* Bounded connect/read timeouts, at most `max_attempts` attempts, exponential backoff.
* HTTP 429/503 honour `Retry-After` up to `max_retry_after` seconds; longer waits fail fast.
* A minimum interval is enforced between requests to the same source.
"""

import logging
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests

from backend.core.logging import log_event

USER_AGENT = (
    "JobMarketPulse/0.1 (+https://github.com/parammeet83/job-market-intelligence; "
    "open-source job-market analytics; daily)"
)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_REDIRECTS = 3
logger = logging.getLogger(__name__)


class SourceFetchError(Exception):
    """A request to a source failed after the permitted retries."""


class DisallowedHostError(SourceFetchError):
    """A URL outside the source's allow-list was requested."""


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    if value.strip().isdigit():
        return float(value.strip())
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


class HttpClient:
    def __init__(
        self,
        allowed_hosts: list[str],
        *,
        min_interval: float = 1.0,
        timeout: tuple[float, float] = (10.0, 45.0),
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        max_retry_after: float = 120.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.max_retry_after = max_retry_after
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.request_count = 0

    def check_host(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or (parts.hostname or "").lower() not in self.allowed_hosts:
            raise DisallowedHostError(f"host not allowed for this source: {parts.hostname}")

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.check_host(url)
        last_error = "no attempt made"
        attempt = 0
        redirects = 0
        while attempt < self.max_attempts:
            attempt += 1
            self._throttle()
            self._last_request = self._clock()
            self.request_count += 1
            try:
                response = self.session.get(
                    url, params=params, timeout=self.timeout, allow_redirects=False
                )
            except requests.RequestException as exc:
                last_error = type(exc).__name__
                delay = self.backoff_base**attempt
            else:
                status = response.status_code
                if status in (301, 302, 303, 307, 308) and redirects < MAX_REDIRECTS:
                    # Redirects are followed only to allow-listed hosts.
                    target = urljoin(url, response.headers.get("Location", ""))
                    self.check_host(target)
                    url, params = target, None
                    redirects += 1
                    attempt -= 1
                    continue
                if status == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise SourceFetchError("response was not valid JSON") from exc
                last_error = f"HTTP {status}"
                if status not in RETRYABLE_STATUS:
                    raise SourceFetchError(last_error)
                retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                if retry_after is not None and retry_after > self.max_retry_after:
                    raise SourceFetchError(f"{last_error}; Retry-After {retry_after:.0f}s too long")
                delay = retry_after if retry_after is not None else self.backoff_base**attempt
            if attempt < self.max_attempts:
                log_event(
                    logger,
                    "retrying source request",
                    logging.WARNING,
                    host=urlsplit(url).hostname,
                    attempt=attempt,
                    error=last_error,
                    delay_s=round(delay, 1),
                )
                self._sleep(delay)
        raise SourceFetchError(f"failed after {self.max_attempts} attempts: {last_error}")
