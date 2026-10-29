"""Loads the source registry (config/sources.toml) into typed settings."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import CONFIG_DIR


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    enabled: bool
    homepage_url: str
    api_url: str
    access_method: str
    allowed_hosts: tuple[str, ...]
    attribution: str
    allow_row_export: bool = False
    retain_description_days: int = 0
    docs_url: str | None = None
    disabled_reason: str | None = None
    min_request_interval_seconds: float = 2.0
    status_check_enabled: bool = False
    require_role_match: bool = True
    default_work_mode: str | None = None
    unconfirmed_after_misses: int = 2
    options: dict[str, Any] = field(default_factory=dict)


_KNOWN = set(SourceConfig.__dataclass_fields__) - {"id", "options"}


def load_source_configs(path: Path = CONFIG_DIR / "sources.toml") -> dict[str, SourceConfig]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    configs: dict[str, SourceConfig] = {}
    for source_id, raw in data["sources"].items():
        known = {k: v for k, v in raw.items() if k in _KNOWN}
        known["allowed_hosts"] = tuple(known.get("allowed_hosts", ()))
        options = {k: v for k, v in raw.items() if k not in _KNOWN}
        configs[source_id] = SourceConfig(id=source_id, options=options, **known)
    return configs
