// Types mirroring backend/app/schemas (the public API contract, /api/v1).

export interface Period {
  start: string;
  end: string;
  days: number;
}

export interface Health {
  status: "ok" | "degraded";
  database: "ok" | "unavailable" | "not_configured";
  version: string;
}

export interface LatestRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  trigger: string;
}

export type Freshness = "fresh" | "delayed" | "stale" | "no_data";

export interface Summary {
  period: Period;
  jobs_total: number;
  jobs_active: number;
  jobs_unconfirmed: number;
  jobs_expired: number;
  listings_in_period: number;
  new_in_period: number;
  observations_total: number;
  skills_identified_active: number;
  active_with_salary_info: number;
  salary_disclosure_pct: number | null;
  sources_enabled: number;
  sources_healthy: number;
  first_observation_date: string | null;
  last_observation_date: string | null;
  latest_run: LatestRun | null;
  freshness: Freshness;
  hours_since_last_success: number | null;
  skills_dictionary_version: string | null;
}

export interface CountItem {
  label: string;
  listings: number;
  share_pct: number | null;
}

export interface TimelinePoint {
  date: string;
  listings_observed: number;
  listings_first_seen: number;
  reported_closed: number;
}

export interface Timeline {
  period: Period;
  points: TimelinePoint[];
}

export interface JobSkill {
  slug: string;
  name: string;
  category: string;
}

export interface JobListItem {
  id: number;
  source_id: string;
  source_name: string;
  url: string;
  title: string;
  title_normalized: string;
  role_category: string | null;
  company: string | null;
  location: string | null;
  country: string | null;
  work_mode: string | null;
  work_mode_basis: string | null;
  employment_type: string | null;
  seniority: string | null;
  salary_text: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: string | null;
  published_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  status: string;
  skills: JobSkill[];
}

export interface JobPage {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SkillStat {
  slug: string;
  name: string;
  category: string;
  listings: number;
  eligible_listings: number;
  share_pct: number | null;
  prev_listings: number;
  prev_eligible_listings: number;
  prev_share_pct: number | null;
  change_pct_points: number | null;
}

export interface SkillList {
  period: Period;
  previous_period: Period;
  eligible_listings: number;
  previous_eligible_listings: number;
  dictionary_version: string | null;
  small_sample: boolean;
  items: SkillStat[];
}

export interface SkillTrendPoint {
  period: string;
  slug: string;
  listings: number;
  eligible_listings: number;
  share_pct: number | null;
}

export interface SkillTrends {
  period: Period;
  grain: "day" | "week";
  skills: string[];
  points: SkillTrendPoint[];
}

export interface RoleAnalytics {
  period: Period;
  population: number;
  roles: CountItem[];
  top_titles: CountItem[];
  seniority: CountItem[];
  top_companies: CountItem[];
  listings_without_company: number;
}

export interface WorkModeItem {
  work_mode: string;
  basis: string;
  listings: number;
}

export interface LocationAnalytics {
  period: Period;
  population: number;
  countries: CountItem[];
  locations: CountItem[];
  work_modes: WorkModeItem[];
}

export interface SalaryDisclosure {
  listings: number;
  with_salary_info: number;
  with_comparable_salary: number;
  with_unit_unknown: number;
  disclosure_pct: number | null;
  comparable_pct: number | null;
}

export interface SalaryGroup {
  currency: string;
  period: string;
  listings: number;
  min_value: number;
  p25: number;
  median: number;
  p75: number;
  max_value: number;
}

export interface SalaryRole {
  currency: string;
  period: string;
  role: string;
  listings: number;
  median: number;
}

export interface SalaryTrendPoint {
  month: string;
  currency: string;
  period: string;
  listings: number;
  median: number;
}

export interface SalaryAnalytics {
  period: Period;
  disclosure: SalaryDisclosure;
  groups: SalaryGroup[];
  by_role: SalaryRole[];
  trend: SalaryTrendPoint[];
  min_group_size: number;
}

export interface LifecycleItem {
  status: string;
  listings: number;
  avg_days_observed: number | null;
  observed_7_days_or_more: number;
}

export interface CoverageItem {
  source_id: string;
  role: string;
  listings: number;
  with_country: number;
}

export interface LifecycleAnalytics {
  period: Period;
  statuses: LifecycleItem[];
  coverage: CoverageItem[];
}

export type SourceHealth = "healthy" | "degraded" | "failing" | "never_run" | "disabled";

export interface SourceInfo {
  source_id: string;
  name: string;
  enabled: boolean;
  access_method: string;
  homepage_url: string;
  attribution: string;
  allow_row_export: boolean;
  disabled_reason: string | null;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_fetch_complete: boolean | null;
  last_record_count: number | null;
  last_error_at: string | null;
  last_error_summary: string | null;
  jobs_total: number;
  jobs_active: number;
  observations_total: number;
  first_seen_at: string | null;
  health: SourceHealth;
}

export interface IngestionRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  trigger: string;
  status: string;
  skills_dictionary_version: string;
  sources_attempted: number;
  sources_succeeded: number;
  records_fetched: number;
  records_valid: number;
  records_invalid: number;
  records_out_of_scope: number;
  duplicates: number;
  jobs_inserted: number;
  jobs_updated: number;
  observations_written: number;
  status_checks: number;
  jobs_marked_expired: number;
  jobs_marked_unconfirmed: number;
  error_count: number;
  error_summary: string | null;
  quality_warnings: number;
  quality_failures: number;
}

export interface QualityResult {
  run_id: number;
  source_id: string | null;
  check_name: string;
  outcome: "pass" | "warn" | "fail";
  failed_count: number;
  details: Record<string, unknown>;
  created_at: string;
}

export interface FilterOptions {
  roles: CountItem[];
  countries: CountItem[];
  sources: CountItem[];
  work_modes: CountItem[];
  employment_types: CountItem[];
  skill_categories: CountItem[];
  skills: JobSkill[];
}
