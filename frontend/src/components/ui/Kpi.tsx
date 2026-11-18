import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * KPI tile: one number, one label, optional context line.
 * The accent bar on the left carries the semantic tone (no coloured numbers
 * everywhere: the figure stays readable white).
 */
export function Kpi({ label, value, hint, tone, to, icon }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: string;
  to?: string;
  icon?: ReactNode;
}) {
  const body = (
    <div className="relative flex h-full flex-col justify-between gap-2 overflow-hidden px-4 py-3.5">
      <span aria-hidden className="absolute inset-y-3 left-0 w-[3px] rounded-r" style={{ background: tone ?? "var(--color-line-strong)" }} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-fg-muted">{label}</span>
        {icon && <span aria-hidden className="text-fg-subtle">{icon}</span>}
      </div>
      <div className="num text-[26px] font-semibold leading-none tracking-tight text-fg">{value}</div>
      {hint && <div className="text-[11.5px] text-fg-subtle">{hint}</div>}
    </div>
  );
  return to ? (
    <Link to={to} className="card block transition-colors hover:border-line-strong hover:bg-surface-2">{body}</Link>
  ) : (
    <div className="card">{body}</div>
  );
}

export function KpiGrid({ children, cols = "grid-cols-2 md:grid-cols-3 xl:grid-cols-6" }: { children: ReactNode; cols?: string }) {
  return <div className={`grid gap-3 ${cols}`}>{children}</div>;
}
