// Test doubles for the API. These are TEST FIXTURES only — the app never ships sample data.
import { vi } from "vitest";
import type { FilterOptions, JobListItem, JobPage, SkillList, SourceInfo, Summary } from "../types/api";

const period = { start: "2026-10-01", end: "2026-10-30", days: 30 };

export const summary: Summary = {
  period, jobs_total: 42, jobs_active: 40, jobs_unconfirmed: 1, jobs_expired: 1, listings_in_period: 42,
  new_in_period: 12, observations_total: 120, skills_identified_active: 18, active_with_salary_info: 20,
  salary_disclosure_pct: 50, sources_enabled: 2, sources_healthy: 2, first_observation_date: "2026-10-20",
  last_observation_date: "2026-10-30", latest_run: { id: 7, started_at: "2026-10-30T03:17:00Z", finished_at: "2026-10-30T03:18:00Z", status: "succeeded", trigger: "schedule" },
  freshness: "fresh", hours_since_last_success: 3, skills_dictionary_version: "2026.10.1",
};

export const emptySummary: Summary = {
  ...summary, jobs_total: 0, jobs_active: 0, jobs_unconfirmed: 0, jobs_expired: 0, listings_in_period: 0, new_in_period: 0,
  observations_total: 0, skills_identified_active: 0, active_with_salary_info: 0, salary_disclosure_pct: null,
  first_observation_date: null, last_observation_date: null, latest_run: null, freshness: "no_data", hours_since_last_success: null,
};

export function job(id: number, extra: Partial<JobListItem> = {}): JobListItem {
  return {
    id, source_id: "jobicy", source_name: "Jobicy", url: `https://jobicy.com/jobs/${id}`, title: `Data Analyst ${id}`,
    title_normalized: `Data Analyst ${id}`, role_category: "Data Analyst", company: "Example Co", location: "USA", country: "United States",
    work_mode: "remote", work_mode_basis: "source_default", employment_type: "full_time", seniority: null, salary_text: null,
    salary_min: null, salary_max: null, salary_currency: null, salary_period: null, published_at: null,
    first_seen_at: "2026-10-28T06:00:00Z", last_seen_at: "2026-10-30T06:00:00Z", status: "active",
    skills: [{ slug: "sql", name: "SQL", category: "Databases & SQL" }], ...extra,
  };
}

export function jobPage(page: number, total = 45): JobPage {
  const size = 20;
  const count = Math.max(0, Math.min(size, total - (page - 1) * size));
  return { items: Array.from({ length: count }, (_, i) => job((page - 1) * size + i + 1)), total, page, page_size: size, pages: Math.ceil(total / size) };
}

const skillStat = (slug: string, name: string, listings: number) => ({
  slug, name, category: "Databases & SQL", listings, eligible_listings: 42, share_pct: Math.round((10000 * listings) / 42) / 100,
  prev_listings: 0, prev_eligible_listings: 0, prev_share_pct: null, change_pct_points: null,
});

export const skills: SkillList = {
  period, previous_period: { start: "2026-09-01", end: "2026-09-30", days: 30 }, eligible_listings: 42, previous_eligible_listings: 0,
  dictionary_version: "2026.10.1", small_sample: false,
  items: [skillStat("sql", "SQL", 20), skillStat("python", "Python", 15), skillStat("tableau", "Tableau", 0)],
};

export const filters: FilterOptions = {
  roles: [{ label: "Data Analyst", listings: 30, share_pct: null }, { label: "Data Engineer", listings: 12, share_pct: null }],
  countries: [{ label: "United States", listings: 20, share_pct: null }],
  sources: [{ label: "jobicy", listings: 40, share_pct: null }],
  work_modes: [{ label: "remote", listings: 42, share_pct: null }],
  employment_types: [{ label: "full_time", listings: 30, share_pct: null }],
  skill_categories: [{ label: "Databases & SQL", listings: 8, share_pct: null }],
  skills: [{ slug: "sql", name: "SQL", category: "Databases & SQL" }, { slug: "python", name: "Python", category: "Programming languages" }],
};

export const sources: SourceInfo[] = [{
  source_id: "jobicy", name: "Jobicy", enabled: true, access_method: "Public JSON API (no key)", homepage_url: "https://jobicy.com",
  attribution: "Job listings courtesy of Jobicy", allow_row_export: true, disabled_reason: null, last_attempt_at: "2026-10-30T03:17:00Z",
  last_success_at: "2026-10-30T03:17:00Z", last_fetch_complete: true, last_record_count: 300, last_error_at: null, last_error_summary: null,
  jobs_total: 40, jobs_active: 38, observations_total: 110, first_seen_at: "2026-10-20T03:00:00Z", health: "healthy",
}];

type Handler = (url: URL) => unknown | Response;

/** Installs a fetch mock routing by API path. Unknown paths answer with empty-but-valid data. */
export function mockApi(overrides: Record<string, Handler> = {}) {
  const routes: Record<string, Handler> = {
    "/api/v1/summary": () => summary,
    "/api/v1/analytics/timeline": () => ({ period, points: [{ date: "2026-10-29", listings_observed: 40, listings_first_seen: 5, reported_closed: 0 }] }),
    "/api/v1/skills": () => skills,
    "/api/v1/skills/trends": () => ({ period, grain: "day", skills: ["sql"], points: [] }),
    "/api/v1/analytics/roles": () => ({ period, population: 42, roles: [{ label: "Data Analyst", listings: 30, share_pct: 71.4 }], top_titles: [], seniority: [], top_companies: [], listings_without_company: 0 }),
    "/api/v1/analytics/locations": () => ({ period, population: 42, countries: [{ label: "United States", listings: 20, share_pct: 47.6 }], locations: [], work_modes: [] }),
    "/api/v1/analytics/salaries": () => ({ period, disclosure: { listings: 42, with_salary_info: 20, with_comparable_salary: 18, with_unit_unknown: 2, disclosure_pct: 47.6, comparable_pct: 42.9 }, groups: [], by_role: [], trend: [], min_group_size: 3 }),
    "/api/v1/analytics/lifecycle": () => ({ period, statuses: [], coverage: [] }),
    "/api/v1/sources": () => sources,
    "/api/v1/ingestion-runs": () => [],
    "/api/v1/data-quality": () => [],
    "/api/v1/meta/filters": () => filters,
    "/api/v1/jobs": (url) => jobPage(Number(url.searchParams.get("page") ?? "1")),
    ...overrides,
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const handler = routes[url.pathname];
    const body = handler ? handler(url) : {};
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
