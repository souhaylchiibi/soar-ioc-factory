import type { ReactNode } from "react";

/** Page header shared by every page. */
export function PageTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold">
        {title}
      </h1>
      {subtitle && <p className="text-muted text-[13px] mt-1">{subtitle}</p>}
    </header>
  );
}

/** KPI tile. */
export function Stat({
  value,
  label,
  tone = "default",
}: {
  value: ReactNode;
  label: string;
  tone?: "default" | "good" | "warn" | "bad" | "signal" | "violet";
}) {
  const tones = {
    default: "text-ink",
    good: "text-green-400",
    warn: "text-amber-400",
    bad: "text-red-400",
    signal: "text-signal",
    violet: "text-purple-400",
  } as const;
  return (
    <div className="card">
      <div className={`kpi-value ${tones[tone]}`}>{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

/** Card wrapper with title. */
export function Panel({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && <h2 className="card-title">{title}</h2>}
      {children}
    </section>
  );
}

/** Loading spinner. */
export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-muted text-sm py-8">
      <span className="w-4 h-4 border-2 border-signal border-t-transparent rounded-full animate-spin" />
      {label}
    </div>
  );
}

/** Error state — surfaces the API failure, never replaces it with fake data. */
export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="border border-red-800 bg-red-950/60 text-red-200 rounded-lg px-4 py-3 text-sm">
      <strong className="font-semibold">Erreur API :</strong> <span className="mono">{msg}</span>
    </div>
  );
}

/** Generic data table. */
export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="table-th">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** Empty state. */
export function Empty({ text }: { text: string }) {
  return <div className="text-muted text-sm italic py-6 text-center">{text}</div>;
}

/** Standard fetch hook with explicit loading/error states (no silent fallback). */
import { useCallback, useEffect, useState } from "react";

export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then((d) => setData(d))
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload };
}
