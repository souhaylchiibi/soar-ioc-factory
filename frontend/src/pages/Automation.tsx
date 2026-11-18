import { useSearchParams } from "react-router-dom";
import { Bot, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, fmtDuration, fmtNum, fmtRelative } from "../lib/format";
import { WORKFLOWS } from "../lib/meta";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { Select } from "../components/ui/Controls";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { Badge, ConnBadge } from "../components/ui/Badge";
import { Pagination, Row, Table } from "../components/ui/Table";
import { OperationButton } from "../components/domain/OperationButton";
import { actionLabel } from "../components/domain/AuditFeed";

const LIMIT = 30;

export default function Automation() {
  const [params, setParams] = useSearchParams();
  const action = params.get("action") ?? "";
  const offset = Number(params.get("offset") ?? 0);
  const qs = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
  if (action) qs.set("action", action);

  const runs = useApi(() => api.runs(`?${qs}`), [qs.toString()], { pollMs: 30000 });
  const latest = useApi(() => api.runs("?limit=200"), [], { pollMs: 60000 });
  const summary = useApi(() => api.workflows(7), [], { pollMs: 60000 });
  const integ = useApi(() => api.integrations(), []);
  const n8n = integ.data?.items.find((i) => i.name === "n8n");
  const refreshAll = () => { runs.refresh(); latest.refresh(); summary.refresh(); integ.refresh(); };

  const lastBy = new Map<string, NonNullable<typeof latest.data>["runs"][number]>();
  for (const r of latest.data?.runs ?? []) if (!lastBy.has(r.action)) lastBy.set(r.action, r);
  const wfStats = new Map((summary.data?.workflows ?? []).map((w) => [w.workflow, w]));

  return (
    <>
      <PageHeader
        title="Automation Center"
        description="Les 8 workflows n8n et leurs exécutions. Chaque exécution est une entrée d'audit ; la durée n'est affichée que lorsqu'elle a été mesurée par l'API."
        updatedAt={runs.updatedAt}
        onRefresh={refreshAll}
      />

      <KpiGrid cols="grid-cols-2 md:grid-cols-4">
        <Kpi label="Orchestrateur n8n" value={n8n ? <ConnBadge state={n8n.status} /> : "…"} icon={<Bot size={16} />}
          hint={n8n?.last_workflow_activity_at ? `dernière exécution ${fmtRelative(n8n.last_workflow_activity_at)}` : n8n?.detail} />
        <Kpi label="Exécutions enregistrées" value={fmtNum(runs.data?.total)} hint="toutes étapes confondues" />
        <Kpi label="Exécutions en échec" value={fmtNum(runs.data?.failed_total)} tone={runs.data?.failed_total ? "var(--color-danger)" : "var(--color-ok)"} />
        <Kpi label="Opérations n8n (7 j)" value={fmtNum((summary.data?.workflows ?? []).reduce((n, w) => n + w.operations, 0))}
          hint={`${fmtNum((summary.data?.workflows ?? []).reduce((n, w) => n + w.failed, 0))} en échec`} />
      </KpiGrid>

      <Card className="mt-4" title="Workflows" subtitle="Déclenchement manuel possible quand l'API expose l'opération (rôle analyste requis, confirmation demandée)" bodyClass="">
        <ul className="grid gap-px bg-line sm:grid-cols-2 xl:grid-cols-4">
          {Object.entries(WORKFLOWS).map(([id, w]) => {
            const last = lastBy.get(w.action);
            const s = wfStats.get(id);
            return (
              <li key={id} className="flex flex-col gap-2.5 bg-surface p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-mono text-[11px] text-fg-subtle">{id}</div>
                    <h3 className="text-[13.5px] font-semibold">{w.label}</h3>
                  </div>
                  {last ? (last.success ? <Badge tone="ok" dot>OK</Badge> : <Badge tone="danger" dot>échec</Badge>) : <Badge>jamais</Badge>}
                </div>
                <p className="text-[12px] text-fg-muted">{w.describe}</p>
                <dl className="mt-auto space-y-1 text-[12px]">
                  <div className="flex justify-between"><dt className="text-fg-subtle">Dernière exécution</dt><dd>{last ? fmtRelative(last.occurred_at) : "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-fg-subtle">Durée</dt><dd>{last ? fmtDuration(last.duration_ms) : "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-fg-subtle">Opérations 7 j (n8n)</dt><dd className="num">{s ? `${s.operations} · ${s.failed} ✕` : "0"}</dd></div>
                </dl>
                {w.path && (
                  <div className="pt-1">
                    <OperationButton path={w.path} label="Exécuter maintenant" onDone={refreshAll}
                      description={<>{w.describe} <br />Endpoint : <code className="font-mono text-[12px]">POST /api/v1{w.path}</code></>} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      <Card className="mt-4" bodyClass="" title="Historique des exécutions"
        actions={<Select label="Étape" value={action} className="w-44" onChange={(v) => setParams(v ? { action: v } : {}, { replace: true })}
          options={[{ value: "", label: "Toutes" }, ...Object.values(WORKFLOWS).map((w) => ({ value: w.action, label: w.label }))]} />}>
        <AsyncBlock state={runs} rows={10}>
          {(d) => d.runs.length === 0 ? <EmptyState title="Aucune exécution enregistrée" /> : (
            <>
              <Table minWidth={900} columns={[{ key: "t", label: "Date" }, { key: "a", label: "Étape" }, { key: "d", label: "Déclencheur" }, { key: "r", label: "Résultat" }, { key: "du", label: "Durée", align: "right" }, { key: "x", label: "Détail" }]}>
                {d.runs.map((r) => (
                  <Row key={r.id}>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtDate(r.occurred_at)}>{fmtDate(r.occurred_at)}</td>
                    <td className="td font-medium">{actionLabel(r.action)}</td>
                    <td className="td"><span className="font-mono text-[12px]">{r.actor}</span> <Badge tone={r.trigger === "n8n" ? "violet" : "info"}>{r.trigger}</Badge></td>
                    <td className="td">{r.success ? <CheckCircle2 size={16} className="text-ok" aria-label="succès" /> : <span className="inline-flex items-center gap-1.5 text-[12px] text-danger"><XCircle size={15} aria-hidden /> {r.error ?? "échec"}</span>}</td>
                    <td className="td num text-right text-[12.5px]">{r.duration_ms !== null ? fmtDuration(r.duration_ms) : <span className="text-fg-subtle">non mesurée</span>}</td>
                    <td className="td max-w-[320px] truncate font-mono text-[11.5px] text-fg-muted" title={JSON.stringify(r.detail)}>
                      {Object.entries(r.detail ?? {}).filter(([k, v]) => typeof v === "number" && k !== "duration_ms").map(([k, v]) => `${k}=${v}`).join(" ")}
                    </td>
                  </Row>
                ))}
              </Table>
              <Pagination total={d.total} offset={offset} limit={LIMIT} onChange={(o) => setParams({ ...(action ? { action } : {}), offset: String(o) }, { replace: true })} />
            </>
          )}
        </AsyncBlock>
      </Card>

      <p className="mt-3 text-[12px] text-fg-subtle">
        Les définitions JSON des workflows sont dans <code className="font-mono">workflows/n8n/</code> ; elles s'authentifient avec la clé de service lue dans l'environnement n8n (jamais stockée dans les fichiers).
      </p>
    </>
  );
}
