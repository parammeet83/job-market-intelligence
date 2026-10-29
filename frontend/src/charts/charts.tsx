import { useId, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate, formatInt, formatMoney, formatPct, periodLabel } from "../utils/format";
import type { BarDatum, TrendRow } from "../utils/transform";
import { SERIES } from "./palette";

const AXIS = { stroke: "#24365c", tick: { fill: "#8ea3c7", fontSize: 12 } };
const GRID = "#1d2c4d";

function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="rounded-md border border-line bg-ink px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-text">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 text-soft">
          {r.color && <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} aria-hidden />}
          <span>{r.label}:</span>
          <span className="tabular ml-auto font-medium text-text">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

/** Chart container with a "table" view so every chart is readable without colour or hover. */
export function ChartFrame({ title, subtitle, table, children, height = 280 }: {
  title: string;
  subtitle?: ReactNode;
  table: { columns: string[]; rows: (string | number)[][] };
  children: ReactNode;
  height?: number;
}) {
  const [showTable, setShowTable] = useState(false);
  const id = useId();
  return (
    <section className="min-w-0 rounded-xl border border-line bg-panel p-4 md:p-5" aria-labelledby={`${id}-t`}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id={`${id}-t`} className="text-base font-semibold text-text">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          aria-pressed={showTable}
          className="rounded-md border border-line px-2 py-1 text-xs text-soft hover:text-text"
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {showTable ? (
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead className="text-xs text-muted">
              <tr>{table.columns.map((c) => <th key={c} scope="col" className="py-1 pr-3 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-line/60">
                  {r.map((v, j) => <td key={j} className="tabular py-1 pr-3 text-soft">{v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ height }} className="w-full min-w-0" role="img" aria-label={`${title}. Use "Show table" for the values.`}>
          {children}
        </div>
      )}
    </section>
  );
}

/** Ranked horizontal bars (single series: magnitude in one hue; the title names the series). */
export function HBarChart({ title, subtitle, data, valueLabel = "Listings", height }: {
  title: string;
  subtitle?: ReactNode;
  data: BarDatum[];
  valueLabel?: string;
  height?: number;
}) {
  const h = height ?? Math.max(160, data.length * 30 + 30);
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      height={h}
      table={{ columns: ["Label", valueLabel, "Share"], rows: data.map((d) => [d.label, formatInt(d.value), formatPct(d.share)]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 4 }} barCategoryGap={4}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" allowDecimals={false} {...AXIS} />
          <YAxis type="category" dataKey="label" width={150} {...AXIS} tickFormatter={(v: string) => (v.length > 22 ? `${v.slice(0, 21)}…` : v)} />
          <Tooltip
            cursor={{ fill: "rgba(142,163,199,0.08)" }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(payload[0].payload.label)}
                  rows={[
                    { label: valueLabel, value: formatInt(payload[0].payload.value) },
                    { label: "Share of population", value: formatPct(payload[0].payload.share) },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="value" fill={SERIES[0]} radius={[0, 4, 4, 0]} isAnimationActive={false}
            label={{ position: "right", fill: "#c3d0e8", fontSize: 11, formatter: (v: unknown) => formatInt(Number(v)) }} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function TimelineChart({ rows }: { rows: { date: string; observed: number; firstSeen: number }[] }) {
  const series = [
    { key: "observed", name: "Listings observed", color: SERIES[0] },
    { key: "firstSeen", name: "First seen that day", color: SERIES[3] },
  ];
  return (
    <ChartFrame
      title="Listings observed over time"
      subtitle="Distinct listings seen per daily run, and how many were seen for the first time. Days without a run are gaps."
      table={{ columns: ["Date", "Observed", "First seen"], rows: rows.map((r) => [r.date, r.observed, r.firstSeen]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="date" {...AXIS} tickFormatter={(d: string) => d.slice(5)} minTickGap={24} />
          <YAxis allowDecimals={false} {...AXIS} width={48} />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={formatDate(String(label))}
                  rows={series.map((s) => ({ label: s.name, value: formatInt(Number(payload[0].payload[s.key])), color: s.color }))}
                />
              ) : null
            }
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#c3d0e8" }} />
          {series.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: "#111c33", fill: s.color }} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function SkillTrendChart({ rows, skills }: { rows: TrendRow[]; skills: { slug: string; name: string }[] }) {
  return (
    <ChartFrame
      title="Skill share over time"
      subtitle="Share of listings observed in each period that mention the skill."
      table={{
        columns: ["Period", "Eligible", ...skills.map((s) => s.name)],
        rows: rows.map((r) => [String(r.period), formatInt(Number(r.eligible)), ...skills.map((s) => formatPct(r[s.slug] as number | null))]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="period" {...AXIS} tickFormatter={(d: string) => d.slice(5)} minTickGap={24} />
          <YAxis {...AXIS} width={48} unit="%" domain={[0, "auto"]} />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={`${formatDate(String(label))} · ${formatInt(Number(payload[0].payload.eligible))} listings`}
                  rows={skills.map((s, i) => ({ label: s.name, value: formatPct(payload[0].payload[s.slug] as number | null), color: SERIES[i] }))}
                />
              ) : null
            }
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#c3d0e8" }} />
          {skills.map((s, i) => (
            <Line key={s.slug} type="monotone" dataKey={s.slug} name={s.name} stroke={SERIES[i % SERIES.length]} strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: "#111c33", fill: SERIES[i % SERIES.length] }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** One salary distribution on its own axis (currencies/periods are never plotted together). */
export function SalaryRange({ currency, period, min, p25, median, p75, max, listings }: {
  currency: string; period: string; min: number; p25: number; median: number; p75: number; max: number; listings: number;
}) {
  const span = max - min || 1;
  const pos = (v: number) => `${(((v - min) / span) * 100).toFixed(2)}%`;
  return (
    <figure className="rounded-lg border border-line bg-panel-2 p-3">
      <figcaption className="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span className="font-semibold text-text">{currency} · {periodLabel(period)}</span>
        <span className="text-xs text-muted">{formatInt(listings)} listings</span>
      </figcaption>
      <div className="relative h-6" aria-hidden>
        <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-line" />
        <div className="absolute top-1 h-4 rounded-sm" style={{ left: pos(p25), width: `calc(${pos(p75)} - ${pos(p25)})`, background: SERIES[0], minWidth: 3 }} />
        <div className="absolute top-0 h-6 w-0.5 bg-accent" style={{ left: pos(median) }} />
      </div>
      <dl className="tabular mt-2 grid grid-cols-3 gap-1 text-xs sm:grid-cols-5">
        {[["Min", min], ["25th pct", p25], ["Median", median], ["75th pct", p75], ["Max", max]].map(([k, v]) => (
          <div key={k as string}>
            <dt className="text-muted">{k}</dt>
            <dd className={k === "Median" ? "font-semibold text-accent" : "text-soft"}>{formatMoney(v as number, currency)}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
