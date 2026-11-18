import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCw, ShieldAlert, WifiOff } from "lucide-react";
import { ApiError } from "../../lib/api";

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}

/** Placeholder keeping the final layout (no layout shift when data lands). */
export function SkeletonBlock({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2.5 p-4" role="status" aria-label="Chargement">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonKpis({ n = 6 }: { n?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" role="status" aria-label="Chargement">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="card space-y-3 p-4">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-16" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-surface-2 text-fg-subtle" aria-hidden>
        {icon ?? <Inbox size={18} />}
      </div>
      <p className="text-[13.5px] font-medium text-fg">{title}</p>
      {children && <div className="mt-1 max-w-md text-[12.5px] text-fg-muted">{children}</div>}
    </div>
  );
}

/** Explicit error: says what failed and why — never replaced by fake data. */
export function ErrorState({ error, onRetry, compact = false }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const status = error instanceof ApiError ? error.status : undefined;
  const msg = error instanceof Error ? error.message : String(error);
  const Icon = status === 0 ? WifiOff : status === 403 ? ShieldAlert : AlertTriangle;
  const title =
    status === 0 ? "API injoignable" : status === 403 ? "Accès refusé" : status === 404 ? "Introuvable" : "Erreur lors du chargement";
  return (
    <div role="alert" className={`flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/8 ${compact ? "p-3" : "p-4"}`}>
      <Icon size={18} className="mt-0.5 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-fg">{title}{status ? <span className="ml-2 font-mono text-[11px] text-fg-subtle">HTTP {status}</span> : null}</p>
        <p className="mt-0.5 break-words text-[12.5px] text-fg-muted">{msg}</p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary h-8 shrink-0">
          <RotateCw size={14} aria-hidden /> Réessayer
        </button>
      )}
    </div>
  );
}

/** Loading → error → empty → content, in one place. */
export function AsyncBlock<T>({ state, empty, emptyTitle = "Aucune donnée", rows, children }: {
  state: { data: T | null; error: unknown; loading: boolean; reload: () => void };
  empty?: (d: T) => boolean;
  emptyTitle?: string;
  rows?: number;
  children: (data: T) => ReactNode;
}) {
  if (state.error && !state.data) return <div className="p-4"><ErrorState error={state.error} onRetry={state.reload} /></div>;
  if (state.loading && !state.data) return <SkeletonBlock rows={rows} />;
  if (!state.data) return null;
  if (empty?.(state.data)) return <EmptyState title={emptyTitle} />;
  return <>{children(state.data)}</>;
}
