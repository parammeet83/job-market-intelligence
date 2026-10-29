import { useCallback } from "react";
import { Card, PageHeader } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { api, API_BASE_URL } from "../services/api";
import { formatDateTime, relativeHours } from "../utils/format";

const REPO = "https://github.com/parammeet83/job-market-intelligence";

export function Methodology() {
  const summary = useApi(useCallback((sig: AbortSignal) => api.summary({}, sig), []), "summary-methodology");
  const s = summary.data;
  return (
    <>
      <PageHeader
        title="Methodology"
        description="How the dataset is collected, normalized and analysed — and what it cannot tell you."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Collection">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-soft">
            <li>A Python pipeline runs once a day on a GitHub Actions schedule (timing can be delayed by GitHub).</li>
            <li>Only documented public JSON APIs whose terms permit this use are queried; no HTML scraping, no login, no bypassing of limits.</li>
            <li>Each source is fetched politely: identified user agent, at least 2 s between requests, bounded retries, and <code>Retry-After</code> honoured.</li>
            <li>Every run is audited (counts, errors, data-quality checks) and visible on the Data Sources page.</li>
            <li>
              Data freshness: {s ? (s.latest_run ? `last successful run ${relativeHours(s.hours_since_last_success)} (${formatDateTime(s.latest_run.finished_at)})` : "no run yet") : "loading…"}.
            </li>
          </ul>
        </Card>
        <Card title="Listing lifecycle and dates">
          <dl className="space-y-2 text-sm">
            {[
              ["Published", "Publication time supplied by the source (if any)."],
              ["First seen", "When this pipeline first observed the listing — not when it was posted."],
              ["Last seen", "The most recent run in which the listing appeared in the source feed."],
              ["Reported closed", "The source's own status API reported the listing closed (Jobicy)."],
              ["Not seen recently", "Absent from 2+ consecutive complete feeds. Feeds are rolling windows of recent jobs, so this is a possible disappearance, not proof of closure."],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="font-medium text-text">{k}</dt>
                <dd className="text-soft">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted">Failed or partial fetches never change listing status, and historical observations are never deleted.</p>
        </Card>
        <Card title="Skill extraction">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-soft">
            <li>A deterministic, versioned dictionary (current version {s?.skills_dictionary_version ?? "—"}) of ~50 skills with aliases.</li>
            <li>Matching is bounded so short names do not match inside other words: "R" does not match "R&amp;D" or "React", "Git" does not match "GitHub", and "Excel at…" is not the spreadsheet.</li>
            <li>Title, source tags and description text are scanned; full descriptions are not displayed or exported.</li>
            <li><strong>Skill share</strong> = distinct listings mentioning the skill ÷ distinct listings observed in the selected period × 100.</li>
          </ul>
        </Card>
        <Card title="Salary normalization">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-soft">
            <li>Minimum, maximum, currency and pay period are stored separately with the original text.</li>
            <li>Values are normalized only when unambiguous; inconsistent ranges (e.g. min &gt; max) keep the text and drop the numbers.</li>
            <li>No currency conversion and no annualising: statistics are computed per currency and pay period.</li>
            <li>Missing salary is unknown, never zero. Remote OK amounts lack a stated currency/period and are excluded from salary statistics.</li>
          </ul>
        </Card>
        <Card title="Coverage and limitations">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-soft">
            <li>Both enabled sources are remote-focused international boards with a strong US/Europe skew. India-based listings appear only incidentally.</li>
            <li>Jobicy's feed covers jobs published in the last 7 days; Remote OK's API returns roughly the latest 100 listings, of which only tech/data roles are kept.</li>
            <li>Work mode is "remote" by board default unless a listing explicitly says hybrid or on-site.</li>
            <li>Role categories and locations are rule-based; ambiguous values are left unclassified rather than guessed.</li>
            <li>This is a sample of public postings, not a census of the job market.</li>
          </ul>
        </Card>
        <Card title="Open data and code">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-soft">
            <li>Source code, SQL and documentation: <a className="text-sky hover:underline" href={REPO} target="_blank" rel="noopener noreferrer">{REPO}</a></li>
            <li>API documentation: <a className="text-sky hover:underline" href={`${API_BASE_URL}/api/docs`} target="_blank" rel="noopener noreferrer">OpenAPI / Swagger UI</a></li>
            <li>CSV exports (Jobs, Skills pages) respect each source's redistribution terms.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
