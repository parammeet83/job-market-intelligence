# Technical requirements and design decisions

## Stack (as implemented)

| Layer | Choice | Version (locked) |
|---|---|---|
| Language | Python | 3.12 (`.python-version`, `requires-python >=3.12,<3.13`) |
| Package manager | uv | `uv.lock` |
| HTTP | requests | 2.34 |
| HTML → text | BeautifulSoup | 4.15 |
| Contracts | Pydantic 2 / pydantic-settings | 2.14 / 2.16 |
| Batch validation | pandas + Pandera | 3.1 / 0.35 |
| DB access | SQLAlchemy 2 Core + psycopg 3 | — |
| Migrations | Alembic | 1.20 |
| API | FastAPI | 0.162 |
| Tests | pytest, pytest-cov, httpx TestClient | — |
| Lint / types | ruff, mypy | — |
| Frontend | React 19, TypeScript 7, Vite 8, Tailwind CSS 4, Recharts 3, React Router 7 | `package-lock.json` |
| Frontend tests | Vitest 5, Testing Library, axe-core, Playwright 1.64 | — |
| Database | PostgreSQL (Neon Free in production; 17 locally and in CI) | — |
| Hosting | Vercel Hobby (API function + static site), GitHub Actions | — |

Dependency groups: `[project.dependencies]` contains only what the API needs; `ingestion` adds
requests/bs4/pandas/pandera/alembic; `dev` adds test and lint tools.

## Key design decisions

| Decision | Rationale |
|---|---|
| Documented JSON APIs only | Compliance and stability; no HTML scraping needed |
| TOML config for sources, roles, skills | Configurable without code changes; stdlib `tomllib` |
| One orchestrator, injectable adapters | Same code path for CLI, Actions and tests |
| Dedup priority native id → canonical URL → fingerprint | Native ids survive slug changes; fingerprint is last resort |
| Snapshot table unique per job per UTC day | Daily granularity matches the schedule; idempotent reruns |
| Status `unconfirmed` vs `expired` | Feeds are rolling windows; only explicit source status proves closure |
| Absence inference only after complete fetches, ≥ 2 misses, no count anomaly, non-empty | Prevents mass false expirations after outages |
| Skill links keyed by dictionary version | Changing rules never silently mixes statistics |
| Descriptions stored transiently (Jobicy 30 days, Remote OK never) | Allows re-extraction while respecting terms and copyright |
| SQL in versioned `.sql` files with bound params | Reviewable metric definitions; reused by docs |
| Three DB roles | Least privilege; public API cannot write even if compromised |
| Read-only transaction per request + statement timeout | Defence in depth; bounded queries |
| Prepared statements disabled | Compatible with Neon's PgBouncer pooled endpoint |
| Per-source transactions | Partial success keeps good data |
| No Vercel cron for ingestion | Requirement: ingestion runs in GitHub Actions only |

## Non-functional targets
- Ingestion run: < 5 minutes (observed locally: ~40–60 s for two sources; most time is source latency and the 2 s request spacing).
- API p95: < 1 s on warm instances for analytics endpoints at current data volume.
- Storage: well under Neon Free's per-project limit (descriptions purged after 30 days; ~1–2 KB per observation row).

## Error handling
- Source errors → recorded in `sources.last_error_summary`, run `details`, DQ results; never raised to crash the run.
- Error text is redacted (URL credentials, passwords/tokens, Neon hostnames) and truncated.
- API: DB connectivity errors → 503 with `Retry-After`; other DB errors → 500 generic; validation → 422 without values.

## Configuration (environment variables)

| Variable | Used by | Secret |
|---|---|---|
| `API_DATABASE_URL` | API | yes (Vercel env) |
| `INGEST_DATABASE_URL` | pipeline | yes (GitHub secret) |
| `MIGRATION_DATABASE_URL` | Alembic, role provisioning | yes (GitHub environment secret; local `.env`) |
| `EXPECTED_DATABASE_NAME` | Alembic safety check | no, but stored as secret for convenience |
| `CORS_ORIGINS` | API | no |
| `APP_ENV` | all (`local`, `ci`, `test`, `production`) | no |
| `LOG_LEVEL` | all | no |
| `TEST_DATABASE_URL` | integration tests (database name must contain `test`) | local only |
| `VITE_API_BASE_URL` | frontend build | **no — public** |
| `JMP_API_RO_PASSWORD`, `JMP_INGEST_PASSWORD` | optional, role re-provisioning | yes |
