// Pure transformations from API responses to chart-ready rows (unit tested).
import type { CountItem, SalaryGroup, SkillTrendPoint, TimelinePoint, WorkModeItem } from "../types/api";

export interface BarDatum {
  label: string;
  value: number;
  share: number | null;
}

/** Top-N bars. By default the remainder folds into one "All other" bar so totals stay honest;
 * pass `otherLabel = null` for pure top-N rankings (e.g. "top titles"). */
export function toBars(items: CountItem[], limit = 10, otherLabel: string | null = "All other"): BarDatum[] {
  const sorted = [...items].sort((a, b) => b.listings - a.listings || a.label.localeCompare(b.label));
  const head = sorted.slice(0, limit).map((i) => ({ label: i.label, value: i.listings, share: i.share_pct }));
  const rest = sorted.slice(limit);
  if (rest.length > 0 && otherLabel !== null) {
    const value = rest.reduce((sum, i) => sum + i.listings, 0);
    const shares = rest.map((i) => i.share_pct);
    const share = shares.every((s) => s !== null)
      ? Math.round(shares.reduce<number>((a, s) => a + (s ?? 0), 0) * 100) / 100
      : null;
    head.push({ label: `${otherLabel} (${rest.length})`, value, share });
  }
  return head;
}

export interface TrendRow {
  period: string;
  [slug: string]: string | number | null;
}

/** Long (period, slug, share) rows -> one row per period with a column per skill. */
export function pivotTrends(points: SkillTrendPoint[], metric: "share_pct" | "listings" = "share_pct"): TrendRow[] {
  const rows = new Map<string, TrendRow>();
  for (const p of points) {
    const row = rows.get(p.period) ?? { period: p.period, eligible: p.eligible_listings };
    row[p.slug] = p[metric];
    rows.set(p.period, row);
  }
  return [...rows.values()].sort((a, b) => a.period.localeCompare(b.period));
}

/** Days without an ingestion run stay absent (shown as gaps); zeros are never invented. */
export function timelineRows(points: TimelinePoint[]) {
  return points.map((p) => ({
    date: p.date,
    observed: p.listings_observed,
    firstSeen: p.listings_first_seen,
  }));
}

export function groupKey(g: Pick<SalaryGroup, "currency" | "period">): string {
  return `${g.currency} · ${g.period}`;
}

/** Salary groups ordered by sample size; each group stays in its own currency and period. */
export function salaryGroupsForChart(groups: SalaryGroup[], minListings = 1) {
  return groups
    .filter((g) => g.listings >= minListings)
    .sort((a, b) => b.listings - a.listings)
    .map((g) => ({ ...g, key: groupKey(g) }));
}

export function workModeTotals(items: WorkModeItem[]): BarDatum[] {
  const totals = new Map<string, number>();
  for (const i of items) totals.set(i.work_mode, (totals.get(i.work_mode) ?? 0) + i.listings);
  const sum = [...totals.values()].reduce((a, b) => a + b, 0);
  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, value]) => ({ label, value, share: sum ? Math.round((1000 * value) / sum) / 10 : null }));
}

export function sourceDefaultShare(items: WorkModeItem[]): number | null {
  const total = items.reduce((a, i) => a + i.listings, 0);
  if (!total) return null;
  const defaulted = items.filter((i) => i.basis === "source_default").reduce((a, i) => a + i.listings, 0);
  return Math.round((1000 * defaulted) / total) / 10;
}
