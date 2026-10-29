// Thin typed client for the read-only JobMarket Pulse API. Only GET requests exist.
import type {
  FilterOptions,
  Health,
  IngestionRun,
  JobListItem,
  JobPage,
  LifecycleAnalytics,
  LocationAnalytics,
  QualityResult,
  RoleAnalytics,
  SalaryAnalytics,
  SkillList,
  SkillTrends,
  SourceInfo,
  Summary,
  Timeline,
} from "../types/api";

// Public base URL of the API (not a secret). Empty string = same origin (dev proxy / tests).
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export type Params = Record<string, string | number | boolean | string[] | null | undefined>;

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function buildUrl(path: string, params: Params = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.append(key, String(value));
  }
  const query = search.toString();
  return `${API_BASE_URL}/api/v1${path}${query ? `?${query}` : ""}`;
}

function messageFor(status: number): string {
  if (status === 503) return "The data service is temporarily unavailable.";
  if (status === 422) return "Some filter values were not accepted.";
  if (status === 404) return "The requested item was not found.";
  if (status >= 500) return "The data service returned an error.";
  return `Request failed (${status}).`;
}

export async function getJson<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach the data service. Check your connection.");
  }
  if (!response.ok) throw new ApiError(response.status, messageFor(response.status));
  return (await response.json()) as T;
}

export const api = {
  health: (s?: AbortSignal) => getJson<Health>("/health", undefined, s),
  summary: (p: Params, s?: AbortSignal) => getJson<Summary>("/summary", p, s),
  timeline: (p: Params, s?: AbortSignal) => getJson<Timeline>("/analytics/timeline", p, s),
  jobs: (p: Params, s?: AbortSignal) => getJson<JobPage>("/jobs", p, s),
  job: (id: number, s?: AbortSignal) => getJson<JobListItem>(`/jobs/${id}`, undefined, s),
  skills: (p: Params, s?: AbortSignal) => getJson<SkillList>("/skills", p, s),
  skillTrends: (p: Params, s?: AbortSignal) => getJson<SkillTrends>("/skills/trends", p, s),
  roles: (p: Params, s?: AbortSignal) => getJson<RoleAnalytics>("/analytics/roles", p, s),
  locations: (p: Params, s?: AbortSignal) =>
    getJson<LocationAnalytics>("/analytics/locations", p, s),
  salaries: (p: Params, s?: AbortSignal) => getJson<SalaryAnalytics>("/analytics/salaries", p, s),
  lifecycle: (p: Params, s?: AbortSignal) =>
    getJson<LifecycleAnalytics>("/analytics/lifecycle", p, s),
  sources: (s?: AbortSignal) => getJson<SourceInfo[]>("/sources", undefined, s),
  runs: (p: Params, s?: AbortSignal) => getJson<IngestionRun[]>("/ingestion-runs", p, s),
  quality: (p: Params, s?: AbortSignal) => getJson<QualityResult[]>("/data-quality", p, s),
  filters: (s?: AbortSignal) => getJson<FilterOptions>("/meta/filters", undefined, s),
};

export const exportUrl = (name: "jobs" | "skills" | "observations", params: Params = {}) =>
  buildUrl(`/exports/${name}.csv`, params);
