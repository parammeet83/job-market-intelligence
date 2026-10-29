"""Canonical URLs and deterministic deduplication keys.

Priority for `dedup_key`:
1. `<source>:id:<source-native id>`  — stable even if the slug/URL changes.
2. `<source>:url:<canonical url>`     — when a source has no native id.
3. `<source>:fp:<sha256(title|company|location)>` — last resort; two genuinely different
   postings with identical title/company/location would merge (documented trade-off).

`cross_source_key` (title+company fingerprint) is stored for analysis of the same vacancy
appearing on several boards; it is NOT used to merge records.
"""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = re.compile(r"^(utm_|ref$|ref_|source$|fbclid$|gclid$|mc_)", re.I)


def canonical_url(url: str) -> str:
    """Lower-case scheme/host, force https, drop fragments and tracking parameters,
    sort remaining parameters and strip a trailing slash."""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k))
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, query, ""))


def _fingerprint(*values: str | None) -> str:
    joined = "|".join(re.sub(r"\s+", " ", (v or "").strip().lower()) for v in values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def dedup_key(
    source_id: str,
    source_job_id: str | None,
    url: str | None,
    title: str,
    company: str | None,
    location: str | None,
) -> str:
    if source_job_id:
        return f"{source_id}:id:{source_job_id}"
    if url:
        return f"{source_id}:url:{canonical_url(url)}"
    return f"{source_id}:fp:{_fingerprint(title, company, location)}"


def cross_source_key(title_normalized: str, company: str | None) -> str:
    company_clean = re.sub(r"\b(inc|llc|ltd|gmbh|corp|co|plc)\.?$", "", (company or "").lower())
    return _fingerprint(title_normalized, company_clean)[:32]
