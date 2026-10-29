import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { HBarChart, SkillTrendChart } from "../charts/charts";
import { SERIES } from "../charts/palette";
import { FilterBar } from "../components/FilterBar";
import { useFilterOptions } from "../hooks/useFilterOptions";
import { Card, DataState, PageHeader, SampleNote, SelectField } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { usePeriodFilters } from "../hooks/useFilters";
import { api, exportUrl } from "../services/api";
import type { SkillStat } from "../types/api";
import { formatInt, formatPct, formatPctPoints } from "../utils/format";
import { pivotTrends } from "../utils/transform";

// The analyst toolkit called out in the project brief; shown by default in the trend chart.
const DEFAULT_TREND_SKILLS = ["sql", "python", "excel", "power-bi", "tableau"];
const MAX_TREND = 6;

function ChangeCell({ s, prevEligible }: { s: SkillStat; prevEligible: number }) {
  if (prevEligible === 0 || s.change_pct_points === null) return <span className="text-muted">No prior data</span>;
  const tone = s.change_pct_points > 0 ? "text-good" : s.change_pct_points < 0 ? "text-bad" : "text-soft";
  const arrow = s.change_pct_points > 0 ? "▲" : s.change_pct_points < 0 ? "▼" : "■";
  return <span className={tone}><span aria-hidden>{arrow} </span>{formatPctPoints(s.change_pct_points)}</span>;
}

export function Skills() {
  const { params } = usePeriodFilters();
  const [search, setSearch] = useSearchParams();
  const category = search.get("category") ?? "";
  const q = search.get("skill_q") ?? "";
  const grain = (search.get("grain") as "day" | "week") ?? "day";
  const trendSkills = (search.get("trend") ?? DEFAULT_TREND_SKILLS.join(",")).split(",").filter(Boolean).slice(0, MAX_TREND);
  const [draftQ, setDraftQ] = useState(q);
  const options = useFilterOptions().data;

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(search);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setSearch(next, { replace: true });
  };

  const listParams = useMemo(() => ({ ...params, category: category || undefined, q: q || undefined }), [params, category, q]);
  const skills = useApi(useCallback((sig: AbortSignal) => api.skills(listParams, sig), [listParams]), JSON.stringify(listParams));
  const trendKey = trendSkills.join(",");
  const trendParams = useMemo(() => ({ ...params, skill: trendKey.split(","), grain }), [params, trendKey, grain]);
  const trends = useApi(useCallback((sig: AbortSignal) => api.skillTrends(trendParams, sig), [trendParams]), JSON.stringify(trendParams));
  const nameOf = (slug: string) => options?.skills.find((s) => s.slug === slug)?.name ?? slug;

  const toggleTrend = (slug: string) => {
    const current = new Set(trendSkills);
    if (current.has(slug)) current.delete(slug);
    else if (current.size < MAX_TREND) current.add(slug);
    set({ trend: [...current].join(",") || DEFAULT_TREND_SKILLS[0] });
  };

  return (
    <>
      <PageHeader
        title="Skill intelligence"
        description={<>How often each skill is mentioned. <strong className="text-soft">Share = distinct listings mentioning the skill ÷ distinct listings observed in the period</strong>, using a versioned rule-based dictionary.</>}
        actions={<a className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-accent-ink" href={exportUrl("skills", params)} download>Export skills CSV</a>}
      />
      <FilterBar />
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SelectField label="Skill category" value={category} onChange={(category) => set({ category })}
          options={(options?.skill_categories ?? []).map((c) => ({ value: c.label, label: c.label }))} />
        <form className="flex min-w-0 flex-col gap-1 text-xs text-muted sm:col-span-2" onSubmit={(e) => { e.preventDefault(); set({ skill_q: draftQ.trim() }); }}>
          <label htmlFor="skill-search">Search skills</label>
          <div className="flex gap-2">
            <input id="skill-search" type="search" value={draftQ} maxLength={60} onChange={(e) => setDraftQ(e.target.value)} placeholder="e.g. Power BI"
              className="min-w-0 flex-1 rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm text-text placeholder:text-muted" />
            <button type="submit" className="rounded-md border border-line px-3 text-sm text-soft">Search</button>
          </div>
        </form>
      </div>

      <DataState state={skills}>
        {(data) => (
          <>
            <SampleNote n={data.eligible_listings} what="listings in this population" />
            <div className="mt-2 grid grid-cols-1 gap-4 xl:grid-cols-2">
              {data.eligible_listings === 0 ? (
                <Card title="Skill ranking"><p className="text-sm text-muted">No listings were observed in this period for the selected filters.</p></Card>
              ) : (
                <HBarChart
                  title="Top skills by listing share"
                  subtitle={`${formatInt(data.eligible_listings)} eligible listings · dictionary ${data.dictionary_version ?? "—"}`}
                  data={data.items.filter((s) => s.listings > 0).slice(0, 15).map((s) => ({ label: s.name, value: s.listings, share: s.share_pct }))}
                />
              )}
              <Card
                title="Analyst toolkit"
                subtitle="SQL, Python, Excel, Power BI and Tableau — shown even when absent from the data"
              >
                <ul className="flex flex-col gap-2">
                  {DEFAULT_TREND_SKILLS.map((slug) => {
                    const s = data.items.find((i) => i.slug === slug);
                    return (
                      <li key={slug} className="flex items-center justify-between gap-3 border-b border-line/60 pb-2 text-sm">
                        <span className="text-soft">{s?.name ?? nameOf(slug)}</span>
                        <span className="tabular text-right">
                          {s && s.listings > 0 ? (
                            <><span className="font-semibold text-accent">{formatPct(s.share_pct)}</span> <span className="text-muted">({formatInt(s.listings)} listings)</span></>
                          ) : (
                            <span className="text-muted">Not found in this population (0 listings)</span>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </Card>
            </div>

            <section className="mt-4 rounded-xl border border-line bg-panel p-4" aria-labelledby="skill-table">
              <h2 id="skill-table" className="text-base font-semibold">All skills</h2>
              <p className="mt-0.5 text-xs text-muted">
                Previous period {data.previous_period.start} → {data.previous_period.end} ({formatInt(data.previous_eligible_listings)} listings).
                Tick up to {MAX_TREND} skills to compare them in the trend chart below.
              </p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <caption className="sr-only">Skill counts and shares</caption>
                  <thead className="text-xs text-muted">
                    <tr>
                      <th scope="col" className="py-2 pr-2 font-medium">Trend</th>
                      <th scope="col" className="py-2 pr-3 font-medium">Skill</th>
                      <th scope="col" className="py-2 pr-3 font-medium">Category</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Listings</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Share</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Previous share</th>
                      <th scope="col" className="py-2 font-medium">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((s) => (
                      <tr key={s.slug} className="border-t border-line/60">
                        <td className="py-1.5 pr-2">
                          <input type="checkbox" aria-label={`Show ${s.name} in trend chart`} checked={trendSkills.includes(s.slug)}
                            disabled={!trendSkills.includes(s.slug) && trendSkills.length >= MAX_TREND} onChange={() => toggleTrend(s.slug)} />
                        </td>
                        <td className="py-1.5 pr-3 text-text">{s.name}</td>
                        <td className="py-1.5 pr-3 text-muted">{s.category}</td>
                        <td className="tabular py-1.5 pr-3 text-right">{formatInt(s.listings)}</td>
                        <td className="tabular py-1.5 pr-3 text-right font-medium text-accent">{formatPct(s.share_pct)}</td>
                        <td className="tabular py-1.5 pr-3 text-right text-soft">{data.previous_eligible_listings ? formatPct(s.prev_share_pct) : "—"}</td>
                        <td className="tabular py-1.5"><ChangeCell s={s} prevEligible={data.previous_eligible_listings} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.items.length === 0 && <p className="py-4 text-sm text-muted">No skills match this search.</p>}
              </div>
            </section>
          </>
        )}
      </DataState>

      <div className="mt-4">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <SelectField label="Trend granularity" value={grain} allLabel={null} onChange={(g) => set({ grain: g === "day" ? "" : g })}
            options={[{ value: "day", label: "Daily" }, { value: "week", label: "Weekly" }]} />
          <ul className="flex flex-wrap gap-2 self-end text-xs" aria-label="Skills in trend chart">
            {trendSkills.map((slug, i) => (
              <li key={slug} className="flex items-center gap-1 rounded-full bg-panel-2 px-2 py-1 text-soft">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: SERIES[i] }} aria-hidden />{nameOf(slug)}
              </li>
            ))}
          </ul>
        </div>
        <DataState state={trends} isEmpty={(t) => t.points.length === 0}
          empty={<Card title="Skill share over time"><p className="text-sm text-muted">No observations in this period yet.</p></Card>}>
          {(t) => {
            const rows = pivotTrends(t.points);
            return (
              <>
                <SkillTrendChart rows={rows} skills={trendSkills.map((slug) => ({ slug, name: nameOf(slug) }))} />
                {rows.length < 3 && (
                  <p className="mt-2 text-xs text-warn">
                    Only {rows.length} {t.grain === "day" ? "day(s)" : "week(s)"} of history so far — this is not yet a trend.
                  </p>
                )}
              </>
            );
          }}
        </DataState>
      </div>
    </>
  );
}
