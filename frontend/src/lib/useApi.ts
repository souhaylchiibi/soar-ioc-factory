import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Fetch hook with explicit loading / error / data states.
 * No silent fallback: an error stays an error until the next success.
 * `pollMs` refreshes in the background (paused while the tab is hidden).
 */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = [], opts: { pollMs?: number; enabled?: boolean } = {}) {
  const { pollMs, enabled = true } = opts;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(enabled);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const load = useCallback((background = false) => {
    if (!enabled) return Promise.resolve();
    const id = ++seq.current;
    if (!background) setLoading(true);
    return fnRef
      .current()
      .then((d) => {
        if (id !== seq.current) return;
        setData(d);
        setError(null);
        setUpdatedAt(Date.now());
      })
      .catch((e) => {
        if (id === seq.current) setError(e);
      })
      .finally(() => {
        if (id === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const t = setInterval(() => {
      if (document.visibilityState === "visible") load(true);
    }, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs, enabled]);

  return { data, error, loading, updatedAt, reload: () => load(false), refresh: () => load(true) };
}

/** Debounced value — used by search inputs to avoid one request per keystroke. */
export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
