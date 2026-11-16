import { CheckCircle2, XCircle } from "lucide-react";
import type { AuditEntry } from "../../lib/api";
import { fmtRelative, fmtDate } from "../../lib/format";

const ACTION_LABELS: Record<string, string> = {
  COLLECT: "Collecte", NORMALIZE: "Normalisation", DEDUP: "Déduplication", ENRICH: "Enrichissement",
  SCORE: "Scoring", PUBLISH: "Publication", OBSERVE: "Observation capteur", EXPIRE: "Expiration",
  REMOVE: "Retrait", EXPORT: "Rapport", TRANSITION: "Transition manuelle", LOGIN: "Connexion",
  LOGOUT: "Déconnexion", USER_CREATE: "Création utilisateur", USER_UPDATE: "Modification utilisateur",
  CONFIG_CHANGE: "Modification IOC", DETECTION_REVIEW: "Triage détection",
};

export const actionLabel = (a: string) => ACTION_LABELS[a] ?? a;

function summary(e: AuditEntry): string {
  const d = e.detail ?? {};
  if (e.error) return e.error;
  const keys = ["collected", "created", "published", "expired", "removed", "matched", "scored", "enriched", "normalized", "verdict"];
  const parts = keys.filter((k) => d[k] !== undefined).map((k) => `${k} ${d[k]}`);
  return parts.slice(0, 3).join(" · ") || [e.entity_type, e.entity_id?.slice(0, 18)].filter(Boolean).join(" ");
}

/** Compact activity feed for the overview. */
export function AuditFeed({ entries }: { entries: AuditEntry[] }) {
  return (
    <ol className="divide-y divide-line/70">
      {entries.map((e) => (
        <li key={e.id} className="flex items-start gap-3 px-4 py-2.5 md:px-5">
          {e.success
            ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-ok" aria-label="succès" />
            : <XCircle size={15} className="mt-0.5 shrink-0 text-danger" aria-label="échec" />}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 text-[12.5px]">
              <span className="font-medium">{actionLabel(e.action)}</span>
              <span className="font-mono text-[11.5px] text-fg-subtle">{e.actor}</span>
            </div>
            <p className="truncate text-[12px] text-fg-muted">{summary(e)}</p>
          </div>
          <time dateTime={e.occurred_at} title={fmtDate(e.occurred_at)} className="shrink-0 text-[11.5px] text-fg-subtle">
            {fmtRelative(e.occurred_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
