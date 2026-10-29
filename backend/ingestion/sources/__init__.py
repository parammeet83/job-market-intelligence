"""Registry mapping source ids (config/sources.toml) to adapter classes."""

from backend.ingestion.config import SourceConfig
from backend.ingestion.sources.base import SourceAdapter
from backend.ingestion.sources.jobicy import JobicyAdapter
from backend.ingestion.sources.remoteok import RemoteOkAdapter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "jobicy": JobicyAdapter,
    "remoteok": RemoteOkAdapter,
}


def build_adapter(config: SourceConfig) -> SourceAdapter:
    try:
        adapter_cls = ADAPTERS[config.id]
    except KeyError as exc:
        raise ValueError(f"no adapter implemented for source {config.id!r}") from exc
    return adapter_cls(config)
