import type { ReactNode } from "react";
import { RotateCw } from "lucide-react";
import { fmtRelative } from "../../lib/format";

export function PageHeader({ title, description, actions, updatedAt, onRefresh, refreshing }: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  updatedAt?: number | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  return (
    <header className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="text-[20px] font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-[13px] text-fg-muted">{description}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {updatedAt ? (
          <span className="text-[11.5px] text-fg-subtle" aria-live="polite">
            Données PostgreSQL · {fmtRelative(new Date(updatedAt).toISOString())}
          </span>
        ) : null}
        {onRefresh && (
          <button type="button" onClick={onRefresh} className="btn-secondary h-8" aria-label="Actualiser les données">
            <RotateCw size={14} className={refreshing ? "animate-spin" : ""} aria-hidden /> Actualiser
          </button>
        )}
        {actions}
      </div>
    </header>
  );
}
