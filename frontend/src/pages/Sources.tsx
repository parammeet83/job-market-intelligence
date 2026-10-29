import { useCallback } from "react";
import { Badge, Card, DataState, ExternalLink, PageHeader } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import type { SourceHealth } from "../types/api";
import { formatDateTime, formatInt, humanize } from "../utils/format";

const HEALTH: Record<SourceHealth, { tone: "good" | "warn" | "bad" | "neutral"; label: string }> = {
  healthy: { tone: "good", label: "Healthy" },
  degraded: { tone: "warn", label: "Degraded" },
  failing: { tone: "bad", label: "Failing" },
  never_run: { tone: "neutral", label: "Not run yet" },
  disabled: { tone: "neutral", label: "Disabled" },
};

export function Sources() {
  const sources = useApi(useCallback((sig: AbortSignal) => api.sources(sig), []), "sources");
  const runs = useApi(useCallback((sig: AbortSignal) => api.runs({ limit: 15 }, sig), []), "runs");
  const quality = useApi(useCallback((sig: AbortSignal) => api.quality({}, sig), []), "quality");

  return (
    <>
      <PageHeader
        title="Data sources"
        description="Every source, its permitted access method, health and attribution. Sources whose terms are unclear stay disabled."
      />
      <DataState state={sources} isEmpty={(s) => s.length === 0}>
        {(list) => (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {list.map((s) => {
              const h = HEALTH[s.health];
              return (
                <Card key={s.source_id} title={s.name} actions={<Badge tone={h.tone}>{h.label}</Badge>}
                  subtitle={<ExternalLink href={s.homepage_url}>{s.homepage_url}</ExternalLink>}>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <div><dt className="text-xs text-muted">Access method</dt><dd className="text-soft">{s.access_method}</dd></div>
                    <div><dt className="text-xs text-muted">Row-level CSV export</dt><dd className="text-soft">{s.allow_row_export ? "Permitted" : "Aggregates only"}</dd></div>
                    <div><dt className="text-xs text-muted">Last successful fetch</dt><dd className="text-soft">{formatDateTime(s.last_success_at)}</dd></div>
                    <div><dt className="text-xs text-muted">Last fetch complete</dt><dd className="text-soft">{s.last_fetch_complete === null ? "—" : s.last_fetch_complete ? "Yes" : "No (partial)"}</dd></div>
                    <div><dt className="text-xs text-muted">Records in last fetch</dt><dd className="tabular text-soft">{formatInt(s.last_record_count)}</dd></div>
                    <div><dt className="text-xs text-muted">Listings stored / active</dt><dd className="tabular text-soft">{formatInt(s.jobs_total)} / {formatInt(s.jobs_active)}</dd></div>
                    <div><dt className="text-xs text-muted">Observations</dt><dd className="tabular text-soft">{formatInt(s.observations_total)}</dd></div>
                    <div><dt className="text-xs text-muted">Collecting since</dt><dd className="text-soft">{formatDateTime(s.first_seen_at)}</dd></div>
                  </dl>
                  {s.disabled_reason && <p className="mt-3 rounded-md bg-panel-2 p-2 text-xs text-soft"><strong>Why disabled:</strong> {s.disabled_reason}</p>}
                  {s.last_error_summary && s.enabled && (
                    <p className="mt-3 rounded-md bg-warn/10 p-2 text-xs text-warn">Latest issue ({formatDateTime(s.last_error_at)}): {s.last_error_summary}</p>
                  )}
                  <p className="mt-3 text-xs text-muted">{s.attribution}</p>
                </Card>
              );
            })}
          </div>
        )}
      </DataState>

      <Card className="mt-6" title="Ingestion runs" subtitle="Audit log of the daily pipeline (GitHub Actions schedule or manual runs)">
        <DataState state={runs} isEmpty={(r) => r.length === 0}>
          {(list) => (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <caption className="sr-only">Recent ingestion runs</caption>
                <thead className="text-xs text-muted">
                  <tr>
                    {["Run", "Started (UTC)", "Trigger", "Status", "Sources ok", "Fetched", "Valid", "Invalid", "New", "Updated", "Quality"].map((c) => (
                      <th key={c} scope="col" className="py-2 pr-3 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => (
                    <tr key={r.id} className="border-t border-line/60">
                      <td className="tabular py-1.5 pr-3">#{r.id}</td>
                      <td className="py-1.5 pr-3 text-soft">{formatDateTime(r.started_at)}</td>
                      <td className="py-1.5 pr-3 text-soft">{humanize(r.trigger)}</td>
                      <td className="py-1.5 pr-3"><Badge tone={r.status === "succeeded" ? "good" : r.status === "partial" ? "warn" : r.status === "failed" ? "bad" : "neutral"}>{humanize(r.status)}</Badge></td>
                      <td className="tabular py-1.5 pr-3">{r.sources_succeeded}/{r.sources_attempted}</td>
                      <td className="tabular py-1.5 pr-3">{formatInt(r.records_fetched)}</td>
                      <td className="tabular py-1.5 pr-3">{formatInt(r.records_valid)}</td>
                      <td className="tabular py-1.5 pr-3">{formatInt(r.records_invalid)}</td>
                      <td className="tabular py-1.5 pr-3">{formatInt(r.jobs_inserted)}</td>
                      <td className="tabular py-1.5 pr-3">{formatInt(r.jobs_updated)}</td>
                      <td className="py-1.5 pr-3 text-xs text-soft">{r.quality_failures} fail · {r.quality_warnings} warn</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </Card>

      <Card className="mt-6" title="Data-quality checks (latest run)">
        <DataState state={quality} isEmpty={(q) => q.length === 0}>
          {(list) => (
            <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {list.map((q) => (
                <li key={`${q.source_id}-${q.check_name}`} className="flex items-center justify-between gap-2 rounded-md border border-line/60 px-3 py-2 text-sm">
                  <span className="min-w-0 text-soft">{q.source_id ?? "all sources"} · {humanize(q.check_name)}</span>
                  <Badge tone={q.outcome === "pass" ? "good" : q.outcome === "warn" ? "warn" : "bad"}>
                    {humanize(q.outcome)}{q.failed_count ? ` (${q.failed_count})` : ""}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Card>
    </>
  );
}
