# Implementation plan

Status legend: ✅ done and verified · 🟡 done locally, production verification pending · ⏳ not started / blocked.
Detailed checklist: [TASKS.md](TASKS.md).

## Environment findings (2026-10-29)
- Repo `parammeet83/job-market-intelligence` public, default branch `main`, **no commits/branches** on
  the remote; local repo initialised with `origin` set; Git identity `Parammeet <parammeet92@gmail.com>`.
- Tools: Python 3.12.10, uv 0.12.9, Node 24.19 / npm 11.17, GitHub CLI 2.103 (logged in as `parammeet83`),
  Vercel CLI logged in as `parammeet83`. No Docker; PostgreSQL 17 binaries present — a separate,
  throw-away cluster on port 55432 is used for development and tests (the existing system
  PostgreSQL service is untouched).
- Neon: not authenticated on this machine → creating the Neon project needs the owner's action.

## Phases

| # | Phase | Status | Notes |
|---|---|---|---|
| 1 | Inspection, source research, provider limits | ✅ | Jobicy + Remote OK enabled; Arbeitnow, Remotive disabled (terms) |
| 2 | Foundation: uv project, lockfiles, config, migrations, env template | ✅ | |
| 3 | Pipeline: adapters, normalization, validation, skills, dedup, observations, audit, CLI, dry run | ✅ | real data loaded into the local dev DB; idempotency verified |
| 4 | SQL analytics: views + parameterised queries + examples | ✅ | validated against real local data and integration tests |
| 5 | FastAPI read-only API + exports + role verification | ✅ | |
| 6 | React dashboard (7 pages), responsive, accessible | ✅ | Playwright on desktop + phone |
| 7 | GitHub Actions: CI, ingestion, migration, smoke | 🟡 | CI and manual ingestion green; first scheduled run pending |
| 8 | Deployment: Neon, roles, migrations, Vercel ×2, first ingestion | ✅ | live; see docs/DEPLOYMENT.md |
| 9 | QA: full test suites, secret scan, production smoke | ✅ | |
| 10 | Commits, push, verify remote, README verified results | ✅ | |

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Source terms change or access revoked | per-source enable flag; compliance doc with review checklist; failure isolation |
| Source format change | fixtures + contract validation; DQ fail visible on dashboard |
| Rolling feeds misread as closures | `unconfirmed` vs `expired`; strict preconditions; tests |
| Small/biased sample presented as the market | coverage notes on every page, small-sample flags, docs |
| Credential leak | three roles, secrets only in GitHub/Vercel, redaction, gitleaks, bundle scan in e2e |
| Free-tier limits | daily schedule, small payloads, description purge, Neon suspends rather than bills |
| GitHub disables schedule after 60 days idle | documented in runbook; re-enable in Actions tab |
| Vercel Python bundling of non-runtime deps | runtime deps separated into `[project.dependencies]`; build logs checked |
