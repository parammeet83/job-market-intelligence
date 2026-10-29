import { useCallback } from "react";
import { HBarChart } from "../charts/charts";
import { FilterBar } from "../components/FilterBar";
import { Card, DataState, PageHeader, SampleNote } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { usePeriodFilters } from "../hooks/useFilters";
import { api } from "../services/api";
import { formatInt, formatPct, humanize } from "../utils/format";
import { sourceDefaultShare, toBars, workModeTotals } from "../utils/transform";

export function LocationsRoles() {
  const { params, key } = usePeriodFilters();
  const roles = useApi(useCallback((sig: AbortSignal) => api.roles(params, sig), [params]), key);
  const locations = useApi(useCallback((sig: AbortSignal) => api.locations(params, sig), [params]), key);
  const lifecycle = useApi(useCallback((sig: AbortSignal) => api.lifecycle(params, sig), [params]), key);

  return (
    <>
      <PageHeader
        title="Locations & roles"
        description="Who is hiring, for which roles, and where — within the coverage of the enabled sources. Both sources are remote-focused boards, so this is not a picture of local job markets."
      />
      <FilterBar />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <DataState state={roles} isEmpty={(r) => r.population === 0}>
          {(r) => (
            <>
              <div className="xl:col-span-2"><SampleNote n={r.population} what="listings in this population" /></div>
              <HBarChart title="Role categories" subtitle={`${formatInt(r.population)} listings · 'Unclassified' titles match no configured role rule`} data={toBars(r.roles, 10)} />
              <HBarChart title="Most frequent job titles" subtitle="Normalized titles (abbreviations expanded, location suffixes removed)" data={toBars(r.top_titles, 15, null)} />
              <HBarChart title="Top employers" subtitle={`${formatInt(r.listings_without_company)} listings have no company name`} data={toBars(r.top_companies, 15, null)} />
              <HBarChart title="Seniority" subtitle="Source-provided level where available, otherwise title keywords" data={r.seniority.map((s) => ({ label: humanize(s.label), value: s.listings, share: s.share_pct }))} />
            </>
          )}
        </DataState>
        <DataState state={locations} isEmpty={(l) => l.population === 0}>
          {(l) => {
            const defaulted = sourceDefaultShare(l.work_modes);
            return (
              <>
                <HBarChart title="Listings by country" subtitle="'Unspecified' = worldwide, multi-country or unresolvable — not a country" data={toBars(l.countries, 12)} />
                <HBarChart title="Location text as published" subtitle="Original location strings, most frequent first" data={toBars(l.locations, 15, null)} />
                <Card title="Remote, hybrid and on-site">
                  <ul className="flex flex-col gap-2 text-sm">
                    {workModeTotals(l.work_modes).map((w) => (
                      <li key={w.label} className="flex justify-between border-b border-line/60 pb-2">
                        <span className="text-soft">{humanize(w.label)}</span>
                        <span className="tabular"><span className="font-semibold text-accent">{formatPct(w.share)}</span> <span className="text-muted">({formatInt(w.value)})</span></span>
                      </li>
                    ))}
                  </ul>
                  {defaulted !== null && defaulted > 0 && (
                    <p className="mt-3 text-xs text-muted">
                      {formatPct(defaulted)} of these are classified "remote" only because the source is a remote-jobs board
                      (no explicit wording in the listing). Hybrid/on-site are detected from explicit title or location text.
                    </p>
                  )}
                </Card>
              </>
            );
          }}
        </DataState>
        <DataState state={lifecycle} isEmpty={(l) => l.statuses.length === 0}>
          {(l) => (
            <Card title="Listing persistence" subtitle="How long listings stay visible, and how many are no longer observed">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Listing status and persistence</caption>
                <thead className="text-xs text-muted">
                  <tr><th scope="col" className="py-1 font-medium">Status</th><th scope="col" className="py-1 text-right font-medium">Listings</th><th scope="col" className="py-1 text-right font-medium">Avg. days observed</th><th scope="col" className="py-1 text-right font-medium">Seen ≥ 7 days</th></tr>
                </thead>
                <tbody>
                  {l.statuses.map((s) => (
                    <tr key={s.status} className="border-t border-line/60">
                      <td className="py-1.5 text-soft">{humanize(s.status)}</td>
                      <td className="tabular py-1.5 text-right">{formatInt(s.listings)}</td>
                      <td className="tabular py-1.5 text-right">{s.avg_days_observed ?? "—"}</td>
                      <td className="tabular py-1.5 text-right">{formatInt(s.observed_7_days_or_more)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-muted">
                "Reported closed" means the source's status API said so. "Not seen recently" means the listing was absent from
                consecutive complete feeds — a possible disappearance, not a verified closure.
              </p>
            </Card>
          )}
        </DataState>
      </div>
    </>
  );
}
