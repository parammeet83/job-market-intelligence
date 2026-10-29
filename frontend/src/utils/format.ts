// Formatting helpers. Unknown values are rendered as an explicit "Not stated"/"—", never 0.

const intFmt = new Intl.NumberFormat("en-US");

export const UNKNOWN = "Not stated";

export function formatInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : intFmt.format(value);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatPctPoints(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}${Math.abs(value).toFixed(1)} pts`;
}

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function shiftDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return isoDate(d);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return `${new Date(value).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  })} UTC`;
}

export function relativeHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "never";
  if (hours < 1) return "less than an hour ago";
  if (hours < 48) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

const PERIOD_LABEL: Record<string, string> = {
  hour: "per hour",
  day: "per day",
  week: "per week",
  month: "per month",
  year: "per year",
};

export function periodLabel(period: string | null | undefined): string {
  return period ? (PERIOD_LABEL[period] ?? period) : "period not stated";
}

export function formatMoney(value: number | null | undefined, currency: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (!currency) return intFmt.format(Math.round(value));
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${intFmt.format(Math.round(value))} ${currency}`;
  }
}

/** Human salary for a listing; amounts without currency/period are labelled, not guessed. */
export function formatSalary(job: {
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: string | null;
  salary_text: string | null;
}): string {
  const { salary_min: lo, salary_max: hi, salary_currency: cur, salary_period: per } = job;
  if (lo === null && hi === null) return job.salary_text ?? UNKNOWN;
  if (!cur || !per) return job.salary_text ?? UNKNOWN;
  const range = lo !== null && hi !== null && lo !== hi
    ? `${formatMoney(lo, cur)}–${formatMoney(hi, cur)}`
    : formatMoney(lo ?? hi, cur);
  return `${range} ${periodLabel(per)}`;
}

const LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "On-site",
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  temporary: "Temporary",
  internship: "Internship",
  freelance: "Freelance",
  active: "Active",
  unconfirmed: "Not seen recently",
  expired: "Reported closed",
  unknown: "Unknown",
};

export function humanize(value: string | null | undefined): string {
  if (!value) return UNKNOWN;
  return LABELS[value] ?? value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}
