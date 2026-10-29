import { useCallback } from "react";
import { api } from "../services/api";
import type { FilterOptions } from "../types/api";
import { useApi } from "./useApi";

/** Distinct values (with counts) for filter dropdowns. */
export function useFilterOptions() {
  const fetcher = useCallback((s: AbortSignal) => api.filters(s), []);
  return useApi<FilterOptions>(fetcher, "filters");
}
