import { useCallback } from "react";
import { Link } from "react-router-dom";
import { HBarChart, TimelineChart } from "../charts/charts";
import { FilterBar } from "../components/FilterBar";
import { Badge, Card, DataState, EmptyState, ErrorState, KpiTile, Loading, PageHeader, SampleNote } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { usePeriodFilters } from "../hooks/useFilters";
import { api } from "../services/api";
import type { Freshness, Summary } from "../types/api";
import { formatDateTime, formatInt, formatPct, relativeHours } from "../utils/format";
import { timelineRows, toBars } from "../utils/transform";

const FRESHNESS: Record<Freshness, { tone: "good" | "warn" | "bad" | "neutral"; label: string }> = {
  fresh: { tone: "good", label: "Fresh" },
  delayed: { tone: "warn", label: "Delayed" },
  stale: { tone: "bad", label: "Stale" },
  no_data: { tone: "neutral", label: "No data yet" },
};

function Kpis({ s }: { s: Summary }) {
  const fresh = FRESHNESS[s.freshness];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <KpiTile label="Active listings" value={formatInt(s.jobs_active)} hint={`${formatInt(s.jobs_total)} stored in total`} />
      <KpiTile label="New in period" value={formatInt(s.new_in_period)} hint="First observed by this pipeline" />
      <KpiTile label="Skills identified" value={formatInt(s.skills_identified_active)} hint={`In active listings · dictionary ${s.skills_dictionary_version ?? "—"}`} />
      <KpiTile label="Working sources" value={`${s.sources_healthy}/${s.sources_enabled}`} hint="Healthy / enabled" />
      <KpiTile label="Salary disclosed" value={formatPct(s.salary_disclosure_pct)} hint="Of active listings" />
      <div className="min-w-0 rounded-xl border border-line bg-panel p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Data freshness</p>
        <div className="mt-2"><Badge tone={fresh.tone}>{fresh.label}</Badge></div>
        <p className="mt-2 text-xs text-muted">
          Last successful run {relativeHours(s.hours_since_last_success)}
          {s.latest_run && <><br />{formatDateTime(s.latest_run.finished_at ?? s.latest_run.started_at)}</>}
        </p>
      </div>
    </div>
  );
}

export function Overview() {
  const { params, key } = usePeriodFilters();
  const summary = useApi(useCallback((sig: AbortSignal) => api.summary(params, sig), [params]), key);
  const timeline = useApi(useCallback((sig: AbortSignal) => api.timeline(params, sig), [params]), key);
  const skills = useApi(useCallback((sig: AbortSignal) => api.skills(params, sig), [params]), key);
  const roles = useApi(useCallback((sig: AbortSignal) => api.roles(params, sig), [params]), key);
  const locations = useApi(useCallback((sig: AbortSignal) => api.locations(params, sig), [params]), key);
  const salaries = useApi(useCallback((sig: AbortSignal) => api.salaries(params, sig), [params]), key);
  const sources = useApi(useCallback((sig: AbortSignal) => api.sources(sig), []), "sources");

  return (
    <>
      <PageHeader
        title="Job market overview"
        description="Tech and data job listings collected daily from public job APIs. All figures come from the live database; nothing here is sample data."
      />
      <FilterBar />
      {summary.error ? (
        <ErrorState error={summary.error} onRetry={summary.reload} />
      ) : !summary.data ? (
        <Loading label="Loading overview" />
      ) : summary.data.jobs_total === 0 ? (
        <EmptyState title="No listings collected yet">
          The database is connected but no ingestion run has stored data. Figures will appear after the first
          successful daily run.
        </EmptyState>
      ) : (
        <>
          <Kpis s={summary.data} />
          <SampleNote n={summary.data.listings_in_period} what="listings in this period" />
          {summary.data.first_observation_date && (
            <p className="mt-2 text-xs text-muted">
              History available since {summary.data.first_observation_date}. Trends need several days of
              observations before they mean much.
            </p>
          )}
        </>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <DataState state={timeline} isEmpty={(t) => t.points.length === 0}>
          {(t) => (
            <div>
              <TimelineChart rows={timelineRows(t.points)} />
              {t.points.length < 3 && (
                <p className="mt-2 text-xs text-warn">
                  Only {t.points.length} daily snapshot(s) so far — this is not yet a trend.
                </p>
              )}
            </div>
          )}
        </DataState>
        <DataState state={skills} isEmpty={(s) => s.eligible_listings === 0}>
          {(s) => (
            <HBarChart
              title="Most frequently mentioned skills"
              subtitle={<>Share of {formatInt(s.eligible_listings)} listings in the period. <Link className="text-sky hover:underline" to="/skills">Skill intelligence →</Link></>}
              data={toBars(s.items.filter((i) => i.listings > 0).map((i) => ({ label: i.name, listings: i.listings, share_pct: i.share_pct })), 10, null)}
            />
          )}
        </DataState>
        <DataState state={roles} isEmpty={(r) => r.population === 0}>
          {(r) => <HBarChart title="Listings by role" subtitle="Rule-based role categories from normalized titles." data={toBars(r.roles, 9)} />}
        </DataState>
        <DataState state={locations} isEmpty={(l) => l.population === 0}>
          {(l) => (
            <HBarChart
              title="Location distribution"
              subtitle="'Unspecified' = worldwide, multi-country or unresolvable location text — not a country."
              data={toBars(l.countries, 8)}
            />
          )}
        </DataState>
        <DataState state={salaries} isEmpty={(s) => s.disclosure.listings === 0}>
          {(s) => (
            <Card title="Salary disclosure" subtitle="Listings observed in the period">
              <dl className="tabular grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  ["Listings", formatInt(s.disclosure.listings)],
                  ["Any salary info", `${formatInt(s.disclosure.with_salary_info)} (${formatPct(s.disclosure.disclosure_pct)})`],
                  ["Comparable salary", `${formatInt(s.disclosure.with_comparable_salary)} (${formatPct(s.disclosure.comparable_pct)})`],
                  ["Unit not stated", formatInt(s.disclosure.with_unit_unknown)],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-muted">{k}</dt>
                    <dd className="mt-1 text-lg font-semibold text-text">{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-muted">
                Missing salaries are treated as unknown, never as zero. <Link className="text-sky hover:underline" to="/salaries">Salary insights →</Link>
              </p>
            </Card>
          )}
        </DataState>
        <DataState state={sources} isEmpty={(s) => s.length === 0}>
          {(list) => (
            <HBarChart
              title="Source activity"
              subtitle="Active listings per enabled source"
              data={list.filter((s) => s.enabled).map((s) => ({ label: s.name, value: s.jobs_active, share: null }))}
            />
          )}
        </DataState>
      </div>
    </>
  );
}
