import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../services/api";

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

interface Result<T> {
  requestKey: string;
  data: T | null;
  error: ApiError | null;
}

/**
 * Runs `fetcher` whenever `key` changes (or `reload` is called) and aborts stale requests, so a
 * slow response can never overwrite a newer one. Loading is derived: the request in flight is
 * the one whose result has not arrived yet. Data is never fabricated: on failure it is null.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  const fetcherRef = useRef(fetcher);
  const requestKey = `${key}#${attempt}`;

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    const controller = new AbortController();
    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ requestKey, data, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || (err as Error).name === "AbortError") return;
        const error = err instanceof ApiError ? err : new ApiError(0, "Unexpected error.");
        setResult({ requestKey, data: null, error });
      });
    return () => controller.abort();
  }, [requestKey]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const loading = result?.requestKey !== requestKey;
  return {
    data: result?.data ?? null,
    error: loading ? null : (result?.error ?? null),
    loading,
    reload,
  };
}
