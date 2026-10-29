"""Batch-level (tabular) quality checks with Pandera, run on each source's validated records
before anything is written. Row-level rules live in contracts.JobRecord; these checks catch
problems that only show up across a batch (duplicate keys, enum drift, salary consistency)."""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from backend.ingestion.validation.contracts import JobRecord

_ENUMS = {
    "work_mode": ["remote", "hybrid", "onsite"],
    "salary_period": ["hour", "day", "week", "month", "year"],
}

JOB_BATCH_SCHEMA = pa.DataFrameSchema(
    {
        "dedup_key": pa.Column(str, unique=True, nullable=False),
        "source_id": pa.Column(str, nullable=False),
        "canonical_url": pa.Column(str, pa.Check.str_startswith("https://"), nullable=False),
        "title_normalized": pa.Column(str, pa.Check.str_length(1, 500), nullable=False),
        "work_mode": pa.Column(object, pa.Check.isin(_ENUMS["work_mode"]), nullable=True),
        "salary_period": pa.Column(object, pa.Check.isin(_ENUMS["salary_period"]), nullable=True),
        "salary_currency": pa.Column(object, pa.Check.str_matches(r"^[A-Z]{3}$"), nullable=True),
        "salary_min": pa.Column(float, pa.Check.gt(0), nullable=True),
        "salary_max": pa.Column(float, pa.Check.gt(0), nullable=True),
    },
    checks=[
        pa.Check(
            lambda df: (
                df["salary_min"].isna()
                | df["salary_max"].isna()
                | (df["salary_min"] <= df["salary_max"])
            ),
            name="salary_min_le_max",
        ),
        pa.Check(lambda df: df["source_id"].nunique() <= 1, name="single_source_per_batch"),
    ],
    strict=False,
    coerce=False,
)


@dataclass(frozen=True)
class BatchCheck:
    passed: bool
    failures: list[str]


def records_frame(records: Sequence[JobRecord]) -> pd.DataFrame:
    rows = [
        {
            "dedup_key": r.dedup_key,
            "source_id": r.source_id,
            "canonical_url": r.canonical_url,
            "title_normalized": r.title_normalized,
            "work_mode": r.work_mode,
            "salary_period": r.salary_period,
            "salary_currency": r.salary_currency,
            "salary_min": float(r.salary_min) if r.salary_min is not None else None,
            "salary_max": float(r.salary_max) if r.salary_max is not None else None,
        }
        for r in records
    ]
    frame = pd.DataFrame(rows, columns=list(JOB_BATCH_SCHEMA.columns))
    for col in ("dedup_key", "source_id", "canonical_url", "title_normalized"):
        frame[col] = frame[col].astype(str)
    for col in ("work_mode", "salary_period", "salary_currency"):
        frame[col] = frame[col].astype(object)
    for col in ("salary_min", "salary_max"):
        frame[col] = frame[col].astype(float)
    return frame


def validate_batch(records: Sequence[JobRecord]) -> BatchCheck:
    if not records:
        return BatchCheck(True, [])
    try:
        JOB_BATCH_SCHEMA.validate(records_frame(records), lazy=True)
    except SchemaErrors as exc:
        cases = exc.failure_cases
        failures = sorted(
            {f"{row['column']}: {row['check']}" for _, row in cases.head(20).iterrows()}
        )
        return BatchCheck(False, failures)
    return BatchCheck(True, [])


def count_anomaly(
    current: int,
    history: Sequence[int],
    *,
    min_history: int = 3,
    ratio: float = 0.5,
    min_baseline: int = 20,
) -> str | None:
    """Flag a sudden drop in fetched records relative to recent complete fetches."""
    if len(history) < min_history:
        return None
    baseline = median(history)
    if baseline >= min_baseline and current < baseline * ratio:
        return f"fetched {current} records vs recent median {baseline:g}"
    return None
