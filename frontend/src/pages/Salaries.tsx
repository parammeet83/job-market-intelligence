import { useCallback } from "react";
import { SalaryRange } from "../charts/charts";
import { FilterBar } from "../components/FilterBar";
import { Card, DataState, EmptyState, PageHeader, SampleNote } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { usePeriodFilters } from "../hooks/useFilters";
import { api } from "../services/api";
import { formatInt, formatMoney, formatPct, periodLabel } from "../utils/format";
import { salaryGroupsForChart } from "../utils/transform";

export function Salaries() {
  const { params, key } = usePeriodFilters();
  const salaries = useApi(useCallback((sig: AbortSignal) => api.salaries(params, sig), [params]), key);

  return (
    <>
      <PageHeader
        title="Salary insights"
        description="Published salary ranges, kept separate by currency and pay period. Currencies are never converted, hourly and annual figures are never mixed, and missing salaries are unknown — not zero."
      />
      <FilterBar />
      <DataState state={salaries} isEmpty={(s) => s.disclosure.listings === 0}
        empty={<EmptyState title="No listings in this period">Widen the period or remove filters.</EmptyState>}>
        {(s) => {
          const groups = salaryGroupsForChart(s.groups);
          const d = s.disclosure;
          return (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[
                  ["Listings in population", formatInt(d.listings), ""],
                  ["Any salary information", formatPct(d.disclosure_pct), `${formatInt(d.with_salary_info)} listings`],
                  ["Comparable salary", formatPct(d.comparable_pct), `${formatInt(d.with_comparable_salary)} with amount + currency + period`],
                  ["Amount without unit", formatInt(d.with_unit_unknown), "Source did not state currency or period; excluded below"],
                ].map(([label, value, hint]) => (
                  <div key={label} className="rounded-xl border border-line bg-panel p-4">
                    <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
                    <p className="tabular mt-2 text-2xl font-semibold text-accent">{value}</p>
                    {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
                  </div>
                ))}
              </div>

              <Card className="mt-4" title="Salary distribution by currency and pay period"
                subtitle="Each band shows the 25th–75th percentile of range midpoints (blue) and the median (yellow line), on its own scale.">
                {groups.length === 0 ? (
                  <p className="text-sm text-muted">No listings in this population publish a comparable salary.</p>
                ) : (
                  <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                    {groups.map((g) => (
                      <div key={g.key}>
                        <SalaryRange currency={g.currency} period={g.period} min={g.min_value} p25={g.p25} median={g.median} p75={g.p75} max={g.max_value} listings={g.listings} />
                        <SampleNote n={g.listings} threshold={10} what={`listings in ${g.currency} ${periodLabel(g.period)}`} />
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card className="mt-4" title="Median salary by role" subtitle={`Within one currency and period; groups with fewer than ${s.min_group_size} listings are hidden.`}>
                {s.by_role.length === 0 ? (
                  <p className="text-sm text-muted">Not enough salary data per role yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[480px] text-left text-sm">
                      <caption className="sr-only">Median salary midpoint by role</caption>
                      <thead className="text-xs text-muted">
                        <tr>
                          <th scope="col" className="py-2 pr-3 font-medium">Role</th>
                          <th scope="col" className="py-2 pr-3 font-medium">Currency · period</th>
                          <th scope="col" className="py-2 pr-3 text-right font-medium">Listings</th>
                          <th scope="col" className="py-2 text-right font-medium">Median midpoint</th>
                        </tr>
                      </thead>
                      <tbody>
                        {s.by_role.map((r) => (
                          <tr key={`${r.role}-${r.currency}-${r.period}`} className="border-t border-line/60">
                            <td className="py-1.5 pr-3 text-text">{r.role}</td>
                            <td className="py-1.5 pr-3 text-soft">{r.currency} · {periodLabel(r.period)}</td>
                            <td className="tabular py-1.5 pr-3 text-right">{formatInt(r.listings)}</td>
                            <td className="tabular py-1.5 text-right font-medium text-accent">{formatMoney(r.median, r.currency)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>

              <Card className="mt-4" title="Salary trend" subtitle="Monthly median midpoint per currency and period">
                {new Set(s.trend.map((t) => t.month)).size < 2 ? (
                  <p className="text-sm text-muted">
                    A salary trend needs at least two months of observations; this dataset does not have that yet.
                  </p>
                ) : (
                  <ul className="tabular text-sm">
                    {s.trend.map((t) => (
                      <li key={`${t.month}-${t.currency}-${t.period}`} className="flex justify-between border-t border-line/60 py-1.5">
                        <span className="text-soft">{t.month.slice(0, 7)} · {t.currency} {periodLabel(t.period)}</span>
                        <span>{formatMoney(t.median, t.currency)} <span className="text-muted">(n={t.listings})</span></span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </>
  );
}
