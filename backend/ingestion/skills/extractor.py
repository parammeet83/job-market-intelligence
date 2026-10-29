"""Deterministic, versioned skill extraction (config/skills.toml).

Each alias is compiled into a bounded regular expression so short names do not match inside
other words: "R" does not match "React" or "R&D", "Git" does not match "GitHub",
"Java" does not match "JavaScript", "Spark" does not match "PySpark".
"""

import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.core.config import CONFIG_DIR

_BEFORE = r"(?<![A-Za-z0-9_+#])"
_AFTER = r"(?![A-Za-z0-9_+#])(?!\.[A-Za-z0-9])"


@dataclass(frozen=True)
class SkillDefinition:
    slug: str
    name: str
    category: str
    aliases: tuple[str, ...]
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SkillDictionary:
    version: str
    categories: tuple[str, ...]
    skills: tuple[SkillDefinition, ...]

    def extract(self, fields: dict[str, str | None]) -> dict[str, list[str]]:
        """Map skill slug -> sorted list of field names in which it was found."""
        found: dict[str, set[str]] = {}
        for field, text in fields.items():
            if not text:
                continue
            for skill in self.skills:
                if skill.pattern.search(text):
                    found.setdefault(skill.slug, set()).add(field)
        return {slug: sorted(where) for slug, where in sorted(found.items())}


def _alias_regex(alias: str, case_sensitive: bool) -> str:
    body = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    return f"{_BEFORE}{body}{_AFTER}" if case_sensitive else f"{_BEFORE}(?i:{body}){_AFTER}"


def compile_skill(entry: dict) -> SkillDefinition:
    aliases = list(entry.get("aliases", []))
    cs_aliases = list(entry.get("cs_aliases", []))
    alternatives = [_alias_regex(a, False) for a in aliases] + [
        _alias_regex(a, True) for a in cs_aliases
    ]
    if not alternatives:
        raise ValueError(f"skill {entry['slug']!r} has no aliases")
    veto = entry.get("not_followed_by")
    pattern = "(?:" + "|".join(alternatives) + ")" + (f"(?!{veto})" if veto else "")
    return SkillDefinition(
        slug=entry["slug"],
        name=entry["name"],
        category=entry["category"],
        aliases=tuple(aliases + cs_aliases),
        pattern=re.compile(pattern),
    )


def load_skill_dictionary_from(path: Path) -> SkillDictionary:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    skills = tuple(compile_skill(e) for e in data["skills"])
    slugs = [s.slug for s in skills]
    if len(slugs) != len(set(slugs)):
        raise ValueError("duplicate skill slugs in dictionary")
    unknown = {s.category for s in skills} - set(data["categories"])
    if unknown:
        raise ValueError(f"skills reference unknown categories: {sorted(unknown)}")
    return SkillDictionary(
        version=data["version"], categories=tuple(data["categories"]), skills=skills
    )


@lru_cache
def load_skill_dictionary() -> SkillDictionary:
    return load_skill_dictionary_from(CONFIG_DIR / "skills.toml")
