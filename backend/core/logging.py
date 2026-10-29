"""Structured JSON logging and secret-safe error summaries."""

import json
import logging
import re
import sys
from datetime import UTC, datetime

_URL_CREDENTIALS = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+)(:[^/\s@]*)?@")
_PASSWORD_KV = re.compile(r"(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*\S+", re.I)
_HOSTS = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:neon\.tech|neon\.build|aws\.neon\.tech)\b", re.I)


def redact(text: str) -> str:
    """Remove credentials, connection-string userinfo and database hostnames from text."""
    text = _URL_CREDENTIALS.sub(r"\1***:***@", text)
    text = _PASSWORD_KV.sub(r"\1=***", text)
    return _HOSTS.sub("<db-host>", text)


def safe_error_summary(exc: BaseException, limit: int = 300) -> str:
    """A short, redacted, single-line description of an exception, safe to store and display."""
    message = " ".join(str(exc).split())
    return redact(f"{type(exc).__name__}: {message}")[:limit]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update({k: v for k, v in extra.items()})
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level.upper())
    # SQLAlchemy echo is never enabled: statements could include parameters.
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(
    logger: logging.Logger, msg: str, level: int = logging.INFO, **fields: object
) -> None:
    logger.log(level, msg, extra={"fields": fields})
