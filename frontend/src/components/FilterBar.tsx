import { useFilterOptions } from "../hooks/useFilterOptions";
import { RANGE_PRESETS, usePeriodFilters } from "../hooks/useFilters";
import { humanize } from "../utils/format";
import { SelectField } from "./ui";

/** One row of filters above the charts; values live in the URL. */
export function FilterBar({ showSource = true }: { showSource?: boolean }) {
  const { state, update, reset, activeCount } = usePeriodFilters();
  const options = useFilterOptions().data;
  const toOptions = (items?: { label: string; listings: number }[], human = false) =>
    (items ?? []).map((i) => ({ value: i.label, label: `${human ? humanize(i.label) : i.label} (${i.listings})` }));

  return (
    <div className="mb-6 rounded-xl border border-line bg-panel p-3" role="search" aria-label="Filters">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <SelectField
          label="Period"
          value={state.range}
          allLabel={null}
          onChange={(range) => update({ range, ...(range === "custom" ? { start: state.start, end: state.end } : {}) })}
          options={[...RANGE_PRESETS.map((p) => ({ value: p.value, label: p.label })), { value: "custom", label: "Custom range" }]}
        />
        {state.range === "custom" && (
          <>
            <label className="flex flex-col gap-1 text-xs text-muted">
              From
              <input type="date" value={state.start} max={state.end} onChange={(e) => update({ start: e.target.value })}
                className="rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm text-text" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted">
              To
              <input type="date" value={state.end} min={state.start} onChange={(e) => update({ end: e.target.value })}
                className="rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm text-text" />
            </label>
          </>
        )}
        <SelectField label="Role" value={state.role} onChange={(role) => update({ role })} options={toOptions(options?.roles)} />
        <SelectField label="Country" value={state.country} onChange={(country) => update({ country })} options={toOptions(options?.countries)} />
        {showSource && (
          <SelectField label="Source" value={state.source} onChange={(source) => update({ source })} options={toOptions(options?.sources)} />
        )}
        <SelectField label="Work mode" value={state.work_mode} onChange={(work_mode) => update({ work_mode })} options={toOptions(options?.work_modes, true)} />
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="tabular">
          {state.start} → {state.end} (UTC) · listings observed at least once in this window
        </span>
        {(activeCount > 0 || state.range !== "30") && (
          <button type="button" onClick={reset} className="rounded px-2 py-1 text-soft underline-offset-2 hover:underline">
            Reset filters
          </button>
        )}
      </div>
    </div>
  );
}
