"""Rule-based role categorisation driven by config/roles.toml."""

import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.core.config import CONFIG_DIR


@dataclass(frozen=True)
class RoleRules:
    version: str
    rules: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]

    def classify(self, normalized_title: str) -> str | None:
        for category, patterns in self.rules:
            if any(p.search(normalized_title) for p in patterns):
                return category
        return None


@lru_cache
def load_role_rules(path: Path = CONFIG_DIR / "roles.toml") -> RoleRules:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rules = tuple(
        (r["category"], tuple(re.compile(p, re.I) for p in r["patterns"])) for r in data["roles"]
    )
    return RoleRules(version=data["version"], rules=rules)
