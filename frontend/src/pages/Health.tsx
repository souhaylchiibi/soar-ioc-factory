import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, fmtRelative } from "../lib/format";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, DefList } from "../components/ui/Card";
import { AsyncBlock } from "../components/ui/States";
import { Badge } from "../components/ui/Badge";
import { IntegrationCard } from "../components/domain/Integrations";

const CHECK_LABELS: Record<string, string> = {
  database: "Connexion PostgreSQL",
  migrations: "Schéma (Alembic)",
  audit_append_only: "Journal append-only (trigger)",
  intel_sources: "Sources de renseignement",
  activity_freshness: "Fraîcheur de l'activité (< 24 h)",
};

function CheckIcon({ status }: { status?: string }) {
  if (status === "ok") return <CheckCircle2 size={16} className="text-ok" aria-label="OK" />;
  if (status === "warning" || status === "stale") return <AlertTriangle size={16} className="text-warn" aria-label="avertissement" />;
  return <XCircle size={16} className="text-danger" aria-label="erreur" />;
}

export default function Health() {
  const health = useApi(api.health, [], { pollMs: 30000 });
  const ready = useApi(api.readiness, [], { pollMs: 30000 });
  const live = useApi(api.liveness, [], { pollMs: 30000 });
  const integ = useApi(() => api.integrations(), [], { pollMs: 60000 });
  const refresh = () => { health.refresh(); ready.refresh(); live.refresh(); integ.reload(); api.integrations(true).then(() => integ.refresh()); };

  const h = health.data;
  return (
    <>
      <PageHeader
        title="System Health"
        description="État de chaque composant tel qu'observé depuis l'API. Un service non configuré est affiché comme tel : aucune connexion n'est simulée."
        updatedAt={health.updatedAt}
        onRefresh={refresh}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="API" subtitle="Sondes de vie et de disponibilité">
          <DefList items={[
            ["Liveness /health", live.error ? <Badge tone="danger">injoignable</Badge> : live.data ? <Badge tone="ok" dot>{live.data.status}</Badge> : "…"],
            ["Readiness /ready", ready.error ? <Badge tone="danger">indisponible</Badge> : ready.data ? <Badge tone={ready.data.status === "ready" ? "ok" : "warn"} dot>{ready.data.status}</Badge> : "…"],
            ["État global", h ? <Badge tone={h.status === "healthy" ? "ok" : "warn"} dot>{h.status === "healthy" ? "sain" : `dégradé (${h.degraded_checks.join(", ")})`}</Badge> : "…"],
            ["Environnement", h?.app.env ?? "…"],
            ["Dernière vérification", h ? fmtDate(h.checked_at) : "…"],
          ]} />
        </Card>

        <Card title="Contrôles internes" className="lg:col-span-2">
          <AsyncBlock state={health} rows={6}>
            {(d) => (
              <ul className="divide-y divide-line/70">
                {Object.entries(CHECK_LABELS).map(([k, label]) => {
                  const c = d.checks[k] ?? {};
                  const detail = k === "migrations" ? (c.head ? `révision ${c.head}` : c.detail)
                    : k === "audit_append_only" ? `${c.triggers ?? 0} trigger actif`
                    : k === "intel_sources" ? `${c.enabled ?? 0}/${c.total ?? 0} activées · ${c.require_key ?? 0} nécessitent une clé`
                    : k === "activity_freshness" ? `dernière activité ${fmtRelative(d.checks.last_activity_at)}`
                    : c.detail;
                  return (
                    <li key={k} className="flex items-center gap-3 py-2.5 text-[13px]">
                      <CheckIcon status={c.status} />
                      <span className="flex-1 font-medium">{label}</span>
                      <span className="text-right text-[12px] text-fg-muted">{detail}</span>
                    </li>
                  );
                })}
                <li className="flex items-center gap-3 py-2.5 text-[13px]">
                  <span className="w-4" />
                  <span className="flex-1 font-medium">Clés API présentes</span>
                  <span className="flex flex-wrap justify-end gap-1.5">
                    {Object.entries(d.checks.api_keys ?? {}).map(([name, ok]) => <Badge key={name} tone={ok ? "ok" : "warn"} dot>{name}</Badge>)}
                  </span>
                </li>
              </ul>
            )}
          </AsyncBlock>
          <p className="mt-3 text-[11.5px] text-fg-subtle">Seule la présence des clés est exposée ; leurs valeurs ne quittent jamais le serveur.</p>
        </Card>
      </div>

      <h2 className="mb-3 mt-6 text-[14px] font-semibold">Services et intégrations
        {integ.data && <span className="ml-2 text-[12px] font-normal text-fg-subtle">sondés {fmtRelative(integ.data.checked_at)} (cache {integ.data.cache_ttl_seconds} s)</span>}
      </h2>
      <AsyncBlock state={integ} rows={6}>
        {(d) => (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {d.items.map((it) => <IntegrationCard key={it.name} item={it} />)}
          </div>
        )}
      </AsyncBlock>
    </>
  );
}
