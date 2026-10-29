"""HTML/entity cleanup for source text fields."""

import html
import re

from bs4 import BeautifulSoup

_WS = re.compile(r"\s+")


def clean_inline(value: str | None) -> str | None:
    """Unescape entities and collapse whitespace; empty strings become None."""
    if value is None:
        return None
    text = _WS.sub(" ", html.unescape(str(value))).strip()
    return text or None


def html_to_text(value: str | None) -> str:
    """Plain text from an HTML fragment (descriptions may be double-escaped by sources)."""
    if not value:
        return ""
    raw = str(value)
    if "&lt;" in raw and "<" not in raw:
        raw = html.unescape(raw)
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return _WS.sub(" ", html.unescape(soup.get_text(" "))).strip()
