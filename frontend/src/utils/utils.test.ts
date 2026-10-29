import { describe, expect, it } from "vitest";
import { buildUrl } from "../services/api";
import { formatInt, formatMoney, formatPct, formatPctPoints, formatSalary, humanize, shiftDays, UNKNOWN } from "./format";
import { pivotTrends, salaryGroupsForChart, sourceDefaultShare, toBars, workModeTotals } from "./transform";

describe("format", () => {
  it("never renders unknown values as zero", () => {
    expect(formatInt(null)).toBe("—");
    expect(formatPct(undefined)).toBe("—");
    expect(formatMoney(null, "USD")).toBe("—");
    expect(formatInt(0)).toBe("0");
  });

  it("formats percentages and point changes", () => {
    expect(formatPct(48.084)).toBe("48.1%");
    expect(formatPctPoints(2.5)).toBe("+2.5 pts");
    expect(formatPctPoints(-1.04)).toBe("−1.0 pts");
    expect(formatPctPoints(0)).toBe("±0.0 pts");
  });

  it("formats salaries per currency and period without guessing units", () => {
    const base = { salary_text: null, salary_currency: "EUR", salary_period: "year" };
    expect(formatSalary({ ...base, salary_min: 70000, salary_max: 85000 })).toBe("€70,000–€85,000 per year");
    expect(formatSalary({ ...base, salary_min: 50, salary_max: 50, salary_period: "hour", salary_currency: "USD" })).toBe("$50 per hour");
    expect(formatSalary({ salary_min: 100000, salary_max: 140000, salary_currency: null, salary_period: null, salary_text: "100000–140000 (Currency and pay period not stated by Remote OK)" })).toContain("not stated");
    expect(formatSalary({ salary_min: null, salary_max: null, salary_currency: null, salary_period: null, salary_text: null })).toBe(UNKNOWN);
    expect(formatMoney(996819, "SEK")).toContain("996,819");
  });

  it("humanizes enums", () => {
    expect(humanize("onsite")).toBe("On-site");
    expect(humanize("unconfirmed")).toBe("Not seen recently");
    expect(humanize(null)).toBe(UNKNOWN);
    expect(humanize("required_fields_and_formats")).toBe("Required fields and formats");
  });

  it("shifts UTC dates", () => {
    expect(shiftDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(shiftDays("2026-10-29", -29)).toBe("2026-09-30");
  });
});

describe("api urls", () => {
  it("drops empty params and repeats arrays", () => {
    expect(buildUrl("/skills/trends", { skill: ["sql", "python"], role: "", country: undefined, grain: "day" }))
      .toBe("/api/v1/skills/trends?skill=sql&skill=python&grain=day");
    expect(buildUrl("/jobs", { q: "Data & AI" })).toBe("/api/v1/jobs?q=Data+%26+AI");
  });
});

describe("transform", () => {
  const items = [
    { label: "A", listings: 5, share_pct: 50 },
    { label: "B", listings: 3, share_pct: 30 },
    { label: "C", listings: 1, share_pct: 10 },
    { label: "D", listings: 1, share_pct: 10 },
  ];

  it("folds the tail into an 'All other' bar so totals are preserved", () => {
    const bars = toBars(items, 2);
    expect(bars.map((b) => b.label)).toEqual(["A", "B", "All other (2)"]);
    expect(bars.reduce((a, b) => a + b.value, 0)).toBe(10);
    expect(bars[2].share).toBe(20);
  });

  it("supports pure top-N without folding", () => {
    expect(toBars(items, 2, null).map((b) => b.label)).toEqual(["A", "B"]);
  });

  it("pivots long trend rows into one row per period", () => {
    const rows = pivotTrends([
      { period: "2026-11-02", slug: "sql", listings: 2, eligible_listings: 10, share_pct: 20 },
      { period: "2026-11-01", slug: "sql", listings: 1, eligible_listings: 5, share_pct: 20 },
      { period: "2026-11-01", slug: "python", listings: 0, eligible_listings: 5, share_pct: 0 },
    ]);
    expect(rows).toEqual([
      { period: "2026-11-01", eligible: 5, sql: 20, python: 0 },
      { period: "2026-11-02", eligible: 10, sql: 20 },
    ]);
  });

  it("keeps salary groups separate and ordered by sample size", () => {
    const g = (currency: string, period: string, listings: number) => ({ currency, period, listings, min_value: 1, p25: 1, median: 1, p75: 1, max_value: 1 });
    const out = salaryGroupsForChart([g("EUR", "year", 3), g("USD", "year", 9), g("USD", "hour", 3)]);
    expect(out.map((x) => x.key)).toEqual(["USD · year", "EUR · year", "USD · hour"]);
  });

  it("aggregates work modes and the share classified by source default", () => {
    const wm = [
      { work_mode: "remote", basis: "source_default", listings: 8 },
      { work_mode: "hybrid", basis: "text", listings: 2 },
    ];
    expect(workModeTotals(wm)).toEqual([
      { label: "remote", value: 8, share: 80 },
      { label: "hybrid", value: 2, share: 20 },
    ]);
    expect(sourceDefaultShare(wm)).toBe(80);
    expect(sourceDefaultShare([])).toBeNull();
  });
});
