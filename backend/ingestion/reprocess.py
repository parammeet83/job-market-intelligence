"""Re-run skill extraction with the current dictionary version for jobs whose description text
is still inside its retention window. Links produced by older dictionary versions are kept,
so statistics are always computed per version and never mix rule sets."""

from datetime import datetime
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.dialects.postgresql import insert

from backend.app.models import job_descriptions, job_skills, jobs
from backend.ingestion import persistence as db
from backend.ingestion.skills.extractor import SkillDictionary, load_skill_dictionary


def reprocess_skills(
    engine: Engine, now: datetime, dictionary: SkillDictionary | None = None
) -> dict[str, Any]:
    dictionary = dictionary or load_skill_dictionary()
    processed = links = 0
    with engine.begin() as conn:
        skill_ids = db.sync_skills(conn, dictionary)
        rows = conn.execute(
            select(
                jobs.c.id, jobs.c.title_original, jobs.c.source_tags, job_descriptions.c.text_plain
            )
            .join(job_descriptions, job_descriptions.c.job_id == jobs.c.id)
            .where(job_descriptions.c.purge_after >= now)
        ).all()
        for row in rows:
            found = dictionary.extract(
                {
                    "title": row.title_original,
                    "tags": " ; ".join(row.source_tags or []),
                    "description": row.text_plain,
                }
            )
            conn.execute(
                job_skills.delete().where(
                    job_skills.c.job_id == row.id,
                    job_skills.c.dictionary_version == dictionary.version,
                )
            )
            values = [
                {
                    "job_id": row.id,
                    "skill_id": skill_ids[slug],
                    "dictionary_version": dictionary.version,
                    "matched_in": where,
                    "detected_at": now,
                }
                for slug, where in found.items()
                if slug in skill_ids
            ]
            if values:
                conn.execute(insert(job_skills), values)
            conn.execute(
                update(jobs)
                .where(jobs.c.id == row.id)
                .values(skills_dictionary_version=dictionary.version)
            )
            processed += 1
            links += len(values)
    return {
        "dictionary_version": dictionary.version,
        "jobs_reprocessed": processed,
        "skill_links_written": links,
    }
