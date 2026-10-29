"""Loads the parameterised analytics queries in sql/analytics/.

Two template directives are expanded at load time (never with user input):
  {{job_filters}}            -> contents of _job_filters.sql
  {{population(a, b)}}       -> _population.sql with :start/:end renamed to :a/:b
All user-supplied values are passed as bound parameters.
"""

import re
from functools import cache

from sqlalchemy import TextClause, text

from backend.core.config import SQL_DIR

ANALYTICS_DIR = SQL_DIR / "analytics"
_POPULATION = re.compile(r"\{\{population\((\w+),\s*(\w+)\)\}\}")


def _strip_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


@cache
def render(name: str) -> str:
    sql = (ANALYTICS_DIR / f"{name}.sql").read_text(encoding="utf-8")
    filters = _strip_comments((ANALYTICS_DIR / "_job_filters.sql").read_text(encoding="utf-8"))
    population = _strip_comments(
        (ANALYTICS_DIR / "_population.sql").read_text(encoding="utf-8")
    ).replace("{{job_filters}}", filters)

    def expand(match: re.Match[str]) -> str:
        start, end = match.group(1), match.group(2)
        return re.sub(r":start\b", f":{start}", re.sub(r":end\b", f":{end}", population))

    sql = _POPULATION.sub(expand, sql)
    return sql.replace("{{job_filters}}", filters)


@cache
def query(name: str) -> TextClause:
    return text(render(name))
