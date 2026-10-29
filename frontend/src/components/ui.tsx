import type { ReactNode } from "react";
import type { ApiError } from "../services/api";

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-text md:text-3xl">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ title, subtitle, children, className = "", actions }: {
  title?: string;
  subtitle?: ReactNode;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={`min-w-0 rounded-xl border border-line bg-panel p-4 md:p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title && <h2 className="text-base font-semibold text-text">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function KpiTile({ label, value, hint, tone = "accent" }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "accent" | "plain";
}) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-panel p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`tabular mt-2 text-3xl font-semibold ${tone === "accent" ? "text-accent" : "text-text"}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function Loading({ label = "Loading data" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-8 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" aria-hidden />
      {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-bad/40 bg-bad/10 p-4 text-sm">
      <p className="font-medium text-text">Data could not be loaded.</p>
      <p className="mt-1 text-soft">{error.message} No figures are shown instead of guessing.</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-accent-ink hover:brightness-110">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line p-6 text-center">
      <p className="font-medium text-soft">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

/** Wraps a data-dependent block with consistent loading / error / empty handling. */
export function DataState<T>({ state, isEmpty, empty, children }: {
  state: { data: T | null; error: ApiError | null; loading: boolean; reload: () => void };
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (state.loading && state.data === null) return <Loading />;
  if (state.data === null) return <Loading />;
  if (isEmpty?.(state.data)) return <>{empty ?? <EmptyState title="No data for this selection" />}</>;
  return <>{children(state.data)}</>;
}

const BADGE_TONES: Record<string, string> = {
  good: "bg-good/15 text-good border-good/40",
  warn: "bg-warn/15 text-warn border-warn/40",
  bad: "bg-bad/15 text-bad border-bad/40",
  neutral: "bg-panel-2 text-soft border-line",
};

const ICONS: Record<string, string> = { good: "●", warn: "▲", bad: "■", neutral: "○" };

/** Status badge: colour is never the only signal (icon + text label). */
export function Badge({ tone, children }: { tone: "good" | "warn" | "bad" | "neutral"; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${BADGE_TONES[tone]}`}>
      <span aria-hidden>{ICONS[tone]}</span>
      {children}
    </span>
  );
}

export function SampleNote({ n, threshold = 30, what = "listings" }: { n: number; threshold?: number; what?: string }) {
  if (n >= threshold) return null;
  return (
    <p className="mt-2 rounded-md bg-warn/10 px-3 py-2 text-xs text-warn">
      Small sample (n = {n} {what}): treat these figures as indicative, not representative.
    </p>
  );
}

export function SelectField({ label, value, onChange, options, allLabel = "All" }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  allLabel?: string | null;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-0 rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
      >
        {allLabel !== null && <option value="">{allLabel}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ExternalLink({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={`text-sky underline-offset-2 hover:underline ${className}`}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
