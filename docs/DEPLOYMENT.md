# Deployment

All services run on free tiers. **No billing, payment method or paid trial is required or
permitted.** Provider facts below were checked on 2026-10-29 from the providers' own documentation;
re-check before relying on them.

| Component | Service | Plan | Relevant limits / caveats |
|---|---|---|---|
| Database | Neon (dedicated project) | Free | 1 GB storage per project (20 GB across projects); 100 CU-hours per project per month; compute suspends after 5 min idle (cannot be disabled); when limits are hit, compute is suspended / writes fail — no charges |
| API | Vercel (project `jobmarket-pulse-api`) | Hobby | Python function, 500 MB bundle limit; Hobby is for personal, non-commercial use |
| Dashboard | Vercel (project `jobmarket-pulse-web`) | Hobby | static build |
| Ingestion, CI, migrations | GitHub Actions | free for public repos | schedules can be delayed (busiest at the top of the hour); scheduled workflows auto-disable after 60 days without repository activity |

Vercel is **not** used for ingestion (no Vercel cron).

## 1. Database (Neon) — owner action required

1. Sign in at https://console.neon.tech (Free plan; do not add a payment method).
2. Create a **new project** `jobmarket-pulse` (region close to GitHub's US runners, e.g. AWS US East),
   database name **`jobmarket_pulse`**.
3. Copy the **direct** (non-pooled) connection string of the owner role into the git-ignored `.env`:
   ```
   MIGRATION_DATABASE_URL=postgresql://<owner>:<password>@<endpoint>.neon.tech/jobmarket_pulse?sslmode=require
   EXPECTED_DATABASE_NAME=jobmarket_pulse
   ```
   Never paste it into chat, issues or commits.
4. Apply migrations and create the two least-privilege roles (passwords are generated and written
   into `.env`, never printed):
   ```bash
   uv run alembic upgrade head
   uv run python -m backend.ops.roles provision --write-env .env
   uv run python -m backend.ops.roles verify      # 16 PASS lines expected
   ```
   `--write-env` builds `API_DATABASE_URL` and `INGEST_DATABASE_URL` on the Neon **pooled** host.

## 2. GitHub secrets and variables

Set from `.env` without displaying values:
```bash
R=parammeet83/job-market-intelligence
for k in INGEST_DATABASE_URL; do grep "^$k=" .env | cut -d= -f2- | gh secret set $k -R $R; done
gh api -X PUT repos/$R/environments/production >/dev/null      # environment for migrations
for k in MIGRATION_DATABASE_URL EXPECTED_DATABASE_NAME; do grep "^$k=" .env | cut -d= -f2- | gh secret set $k -R $R --env production; done
gh secret list -R $R; gh secret list -R $R --env production   # names only
```
Repository **variables** (public, used by the smoke test): `DASHBOARD_URL`, `API_URL`.

## 3. API on Vercel

The API project deploys from the **repository root** (`pyproject.toml` → `[tool.vercel] entrypoint = "backend.app.main:app"`; `.vercelignore` drops the frontend, docs and tests).
```bash
npx vercel link --yes --project jobmarket-pulse-api
grep '^API_DATABASE_URL=' .env | cut -d= -f2- | npx vercel env add API_DATABASE_URL production
printf 'production' | npx vercel env add APP_ENV production
printf 'https://<dashboard-domain>' | npx vercel env add CORS_ORIGINS production
npx vercel deploy --prod
```
Only the read-only `API_DATABASE_URL` is given to Vercel.

## 4. Dashboard on Vercel

```bash
cd frontend
npx vercel link --yes --project jobmarket-pulse-web
printf 'https://<api-domain>' | npx vercel env add VITE_API_BASE_URL production   # public URL, not a secret
npx vercel deploy --prod
```
`frontend/vercel.json` rewrites unknown paths to `index.html` (SPA routing) and sets security headers.
After the dashboard URL is known, set `CORS_ORIGINS` on the API project to exactly that origin and redeploy the API.

## 5. First ingestion and verification

```bash
gh workflow run ingest.yml -R parammeet83/job-market-intelligence
gh run watch -R parammeet83/job-market-intelligence
curl -s https://<api-domain>/api/v1/summary | python -m json.tool
cd frontend && E2E_BASE_URL=https://<dashboard> E2E_API_URL=https://<api> npx playwright test
```

## Current deployment status

See the README section *Verification status*; it lists only checks that were actually performed.
