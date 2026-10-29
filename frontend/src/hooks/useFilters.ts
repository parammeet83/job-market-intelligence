import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { Params } from "../services/api";
import { isoDate, shiftDays } from "../utils/format";

export const RANGE_PRESETS = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
  { value: "365", label: "Last 12 months" },
] as const;

export interface PeriodFilterState {
  range: string;
  start: string;
  end: string;
  role: string;
  country: string;
  source: string;
  work_mode: string;
}

const FILTER_KEYS = ["role", "country", "source", "work_mode"] as const;

const TODAY = new Date();

/** Period + dimension filters stored in the URL so views are shareable and survive reloads. */
export function usePeriodFilters(today: Date = TODAY) {
  const [search, setSearch] = useSearchParams();
  const state = useMemo<PeriodFilterState>(() => {
    const range = search.get("range") ?? "30";
    const end = range === "custom" ? (search.get("end") ?? isoDate(today)) : isoDate(today);
    const days = Number(range) > 0 ? Number(range) : 30;
    const start =
      range === "custom" ? (search.get("start") ?? shiftDays(end, -29)) : shiftDays(end, -(days - 1));
    return {
      range,
      start,
      end,
      role: search.get("role") ?? "",
      country: search.get("country") ?? "",
      source: search.get("source") ?? "",
      work_mode: search.get("work_mode") ?? "",
    };
  }, [search, today]);

  const update = useCallback(
    (patch: Partial<PeriodFilterState>) => {
      const next = new URLSearchParams(search);
      for (const [key, value] of Object.entries(patch)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (patch.range && patch.range !== "custom") {
        next.delete("start");
        next.delete("end");
      }
      setSearch(next, { replace: true });
    },
    [search, setSearch],
  );

  const reset = useCallback(() => {
    const next = new URLSearchParams(search);
    ["range", "start", "end", ...FILTER_KEYS].forEach((k) => next.delete(k));
    setSearch(next, { replace: true });
  }, [search, setSearch]);

  const params: Params = useMemo(
    () => ({
      start: state.start,
      end: state.end,
      role: state.role || undefined,
      country: state.country || undefined,
      source: state.source || undefined,
      work_mode: state.work_mode || undefined,
    }),
    [state],
  );

  const activeCount = FILTER_KEYS.filter((k) => state[k]).length;
  return { state, params, key: JSON.stringify(params), update, reset, activeCount };
}
