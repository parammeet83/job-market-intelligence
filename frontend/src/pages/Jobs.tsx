import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useFilterOptions } from "../hooks/useFilterOptions";
import { Badge, EmptyState, ErrorState, ExternalLink, Loading, PageHeader, SelectField } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { api, exportUrl, type Params } from "../services/api";
import type { JobListItem } from "../types/api";
import { formatDate, formatInt, formatSalary, humanize, UNKNOWN } from "../utils/format";

const SORTS = [
  { value: "first_seen_desc", label: "Newest first seen" },
  { value: "last_seen_desc", label: "Most recently seen" },
  { value: "published_desc", label: "Newest published" },
  { value: "title_asc", label: "Title A–Z" },
  { value: "company_asc", label: "Company A–Z" },
  { value: "salary_desc", label: "Salary (within currency)" },
];
const STATUSES = [
  { value: "active", label: "Active" },
  { value: "unconfirmed", label: "Not seen recently" },
  { value: "expired", label: "Reported closed" },
  { value: "all", label: "Any status" },
];
const FILTER_KEYS = ["q", "company", "role", "country", "source", "work_mode", "employment_type", "skill", "salary_disclosed", "status", "sort"] as const;
const PAGE_SIZE = 20;

function statusTone(status: string) {
  return status === "active" ? "good" : status === "expired" ? "bad" : "warn";
}

function JobRow({ job }: { job: JobListItem }) {
  return (
    <li className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-text">
            <ExternalLink href={job.url} className="!text-text">{job.title}</ExternalLink>
          </h3>
          <p className="mt-0.5 text-sm text-soft">
            {job.company ?? <span className="text-muted">Company {UNKNOWN.toLowerCase()}</span>} · {job.location ?? <span className="text-muted">Location not stated</span>}
          </p>
        </div>
        <Badge tone={statusTone(job.status)}>{humanize(job.status)}</Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3 lg:grid-cols-6">
        <div><dt className="text-muted">Role</dt><dd className="text-soft">{job.role_category ?? "Unclassified"}</dd></div>
        <div><dt className="text-muted">Work mode</dt><dd className="text-soft">{humanize(job.work_mode)}{job.work_mode_basis === "source_default" && <span className="text-muted"> (board default)</span>}</dd></div>
        <div><dt className="text-muted">Employment</dt><dd className="text-soft">{humanize(job.employment_type)}</dd></div>
        <div className="col-span-2 sm:col-span-1 lg:col-span-1"><dt className="text-muted">Salary</dt><dd className="text-soft break-words">{formatSalary(job)}</dd></div>
        <div><dt className="text-muted">Published</dt><dd className="text-soft">{job.published_at ? formatDate(job.published_at) : UNKNOWN}</dd></div>
        <div><dt className="text-muted">First / last seen</dt><dd className="text-soft">{formatDate(job.first_seen_at)} → {formatDate(job.last_seen_at)}</dd></div>
      </dl>
      {job.skills.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Detected skills">
          {job.skills.map((s) => (
            <li key={s.slug} className="rounded-full bg-panel-2 px-2 py-0.5 text-xs text-soft">{s.name}</li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">
        Source: {job.source_name} · <ExternalLink href={job.url}>View original listing</ExternalLink>
      </p>
    </li>
  );
}

export function Jobs() {
  const [search, setSearch] = useSearchParams();
  const options = useFilterOptions().data;
  const get = (k: string) => search.get(k) ?? "";
  const page = Math.max(1, Number(search.get("page") ?? "1") || 1);

  const params: Params = useMemo(() => {
    const p: Params = { page, page_size: PAGE_SIZE };
    FILTER_KEYS.forEach((k) => {
      const v = search.get(k);
      if (v) p[k] = v;
    });
    return p;
  }, [search, page]);
  const key = JSON.stringify(params);
  const jobs = useApi(useCallback((sig: AbortSignal) => api.jobs(params, sig), [params]), key);

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(search);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    if (!("page" in patch)) next.delete("page");
    setSearch(next, { replace: true });
  };
  const clear = () => {
    const next = new URLSearchParams(search);
    [...FILTER_KEYS, "page"].forEach((k) => next.delete(k));
    setSearch(next, { replace: true });
  };
  const opt = (items?: { label: string; listings: number }[], human = false) =>
    (items ?? []).map((i) => ({ value: i.label, label: `${human ? humanize(i.label) : i.label} (${i.listings})` }));
  const exportParams: Params = { ...params, page: undefined, page_size: undefined, sort: undefined, salary_disclosed: undefined, company: undefined, employment_type: undefined };

  return (
    <>
      <PageHeader
        title="Job listings"
        description="Normalized listings with links to the original posting. Full descriptions are not reproduced here."
        actions={
          <a href={exportUrl("jobs", exportParams)} className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-accent-ink hover:brightness-110" download>
            Export CSV
          </a>
        }
      />
      <form
        role="search"
        aria-label="Job filters"
        className="mb-4 rounded-xl border border-line bg-panel p-3"
        onSubmit={(e) => {
          e.preventDefault();
          const value = new FormData(e.currentTarget).get("q");
          set({ q: String(value ?? "").trim() });
        }}
      >
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="job-search">Search title or company</label>
          <input
            id="job-search"
            key={get("q")}
            name="q"
            type="search"
            defaultValue={get("q")}
            maxLength={100}
            placeholder="Search title or company"
            className="min-w-0 flex-1 rounded-md border border-line bg-panel-2 px-3 py-2 text-sm text-text placeholder:text-muted"
          />
          <button type="submit" className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">Search</button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-5">
          <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
            Company
            <input defaultValue={get("company")} key={`c-${get("company")}`} maxLength={120} placeholder="Any"
              onBlur={(e) => e.target.value.trim() !== get("company") && set({ company: e.target.value.trim() })}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); set({ company: (e.target as HTMLInputElement).value.trim() }); } }}
              className="min-w-0 rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm text-text" />
          </label>
          <SelectField label="Role" value={get("role")} onChange={(role) => set({ role })} options={opt(options?.roles)} />
          <SelectField label="Country" value={get("country")} onChange={(country) => set({ country })} options={opt(options?.countries)} />
          <SelectField label="Skill" value={get("skill")} onChange={(skill) => set({ skill })} options={(options?.skills ?? []).map((s) => ({ value: s.slug, label: s.name }))} />
          <SelectField label="Source" value={get("source")} onChange={(source) => set({ source })} options={opt(options?.sources)} />
          <SelectField label="Work mode" value={get("work_mode")} onChange={(work_mode) => set({ work_mode })} options={opt(options?.work_modes, true)} />
          <SelectField label="Employment type" value={get("employment_type")} onChange={(employment_type) => set({ employment_type })} options={opt(options?.employment_types, true)} />
          <SelectField label="Salary" value={get("salary_disclosed")} onChange={(salary_disclosed) => set({ salary_disclosed })}
            options={[{ value: "true", label: "Salary disclosed" }, { value: "false", label: "No salary info" }]} allLabel="Any" />
          <SelectField label="Status" value={get("status") || "active"} allLabel={null} onChange={(status) => set({ status: status === "active" ? "" : status })} options={STATUSES} />
          <SelectField label="Sort by" value={get("sort") || "first_seen_desc"} allLabel={null} onChange={(sort) => set({ sort: sort === "first_seen_desc" ? "" : sort })} options={SORTS} />
        </div>
        <div className="mt-2 text-right">
          <button type="button" onClick={clear} className="text-xs text-soft underline-offset-2 hover:underline">Clear all filters</button>
        </div>
      </form>

      {jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : !jobs.data ? (
        <Loading label="Loading listings" />
      ) : jobs.data.total === 0 ? (
        <EmptyState title="No listings match these filters">Try removing a filter or widening the status.</EmptyState>
      ) : (
        <>
          <p className="mb-3 text-sm text-muted" aria-live="polite">
            <span className="tabular font-semibold text-text">{formatInt(jobs.data.total)}</span> listings · page {jobs.data.page} of {jobs.data.pages}
            {jobs.loading && " · updating…"}
          </p>
          <ul className="flex flex-col gap-3">
            {jobs.data.items.map((j) => <JobRow key={j.id} job={j} />)}
          </ul>
          <nav aria-label="Pagination" className="mt-4 flex items-center justify-between gap-2">
            <button type="button" disabled={page <= 1} onClick={() => set({ page: String(page - 1) })}
              className="rounded-md border border-line px-3 py-1.5 text-sm text-soft disabled:opacity-40">← Previous</button>
            <span className="tabular text-sm text-muted">Page {jobs.data.page} / {jobs.data.pages}</span>
            <button type="button" disabled={page >= jobs.data.pages} onClick={() => set({ page: String(page + 1) })}
              className="rounded-md border border-line px-3 py-1.5 text-sm text-soft disabled:opacity-40">Next →</button>
          </nav>
          <p className="mt-4 text-xs text-muted">
            CSV export includes only sources whose terms permit redistribution of listing data (see Data Sources).
          </p>
        </>
      )}
    </>
  );
}
