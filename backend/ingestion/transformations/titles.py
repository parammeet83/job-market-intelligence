"""Conservative job-title normalization. The original title is always preserved separately."""

import re

from backend.ingestion.transformations.text import clean_inline

# Abbreviations expanded to a canonical word (word-bounded, case-insensitive).
_ABBREVIATIONS = [
    (re.compile(r"\bSr\.?(?=\s|$)", re.I), "Senior"),
    (re.compile(r"\bJr\.?(?=\s|$)", re.I), "Junior"),
    (re.compile(r"\bEng\.?(?=\s|$)", re.I), "Engineer"),
    (re.compile(r"\bMgr\.?(?=\s|$)", re.I), "Manager"),
]
# Trailing location/remote qualifiers that boards append to titles, e.g. "Analyst | Remote",
# "Engineer - Remote (US)", "Developer (Remote)". Only removed when they are clearly suffixes.
_REMOTE_SUFFIX = re.compile(
    r"\s*[\(\[]\s*(?:100%\s*)?(?:fully\s+)?remote[^\)\]]*[\)\]]\s*$|\s+[-–—]\s*(?:100%\s*)?remote\b.*$",
    re.I,
)

_SENIORITY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("intern", re.compile(r"\b(intern|internship|trainee)\b", re.I)),
    ("executive", re.compile(r"\b(chief|cto|cdo|vp|vice president|head of)\b", re.I)),
    ("director", re.compile(r"\bdirector\b", re.I)),
    ("principal", re.compile(r"\b(principal|distinguished)\b", re.I)),
    ("staff", re.compile(r"\bstaff\b", re.I)),
    ("lead", re.compile(r"\b(lead|tech lead|team lead)\b", re.I)),
    ("manager", re.compile(r"\bmanager\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr)\b|\b(iii|iv)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr|entry[- ]level|graduate|associate)\b|\bi\b", re.I)),
    ("mid", re.compile(r"\b(mid[- ]level|intermediate|ii)\b", re.I)),
]

_SOURCE_LEVELS = {
    "senior": "senior",
    "midweight": "mid",
    "mid-level": "mid",
    "middle": "mid",
    "junior": "junior",
    "entry": "junior",
    "lead": "lead",
    "manager": "manager",
    "director": "director",
    "executive": "executive",
    "internship": "intern",
}


def normalize_title(title: str) -> str:
    """Whitespace/entity cleanup, pipe-separated location suffixes and remote markers removed,
    common abbreviations expanded. Wording that changes meaning is never altered."""
    text = clean_inline(title) or ""
    if "|" in text:
        text = text.split("|", 1)[0].strip() or text
    text = _REMOTE_SUFFIX.sub("", text).strip(" -–—,")
    for pattern, replacement in _ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip() or (clean_inline(title) or "")


def infer_seniority(title: str, source_level: str | None = None) -> str | None:
    """Seniority from an explicit source field when recognised, otherwise from title keywords."""
    if source_level:
        mapped = _SOURCE_LEVELS.get(source_level.strip().lower())
        if mapped:
            return mapped
    for level, pattern in _SENIORITY_RULES:
        if pattern.search(title):
            return level
    return None
