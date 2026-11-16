import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, ExternalLink, KeyRound, XCircle } from "lucide-react";
import { api, type SourceRow } from "../lib/api";
import { fmtDate, fmtNum, fmtRelative } from "../lib/format";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, DefList } from "../components/ui/Card";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { Badge, ConnBadge } from "../components/ui/Badge";
import { Row, Table } from "../components/ui/Table";
import { OperationButton } from "../components/domain/OperationButton";

function Reliability({ value }: { value: number }) {
  const color = value >= 80 ? "var(--color-ok)" : value >= 60 ? "var(--color-accent)" : value >= 40 ? "var(--color-warn)" : "var(--color-danger)";
  return (
    <div className="flex items-center gap-2" title={`Fiabilité ${value}/100`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-3" aria-hidden><div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} /></div>
      <span className="num text-[12px]">{value}</span>
    </div>
  );
}

const COLLECTABLE = new Set(["feodotracker", "blocklist_de", "urlscan", "alienvault_otx", "urlhaus", "threatfox", "malwarebazaar"]);

export default function Sources() {
  const [params] = useSearchParams();
  const state = useApi(api.sources, [], { pollMs: 60000 });
  const [selected, setSelected] = useState<string | null>(params.get("focus"));
  const runs = useApi(() => api.sourceRuns(selected!), [selected], { enabled: !!selected });

  useEffect(() => {
    if (!selected && state.data?.sources.length) setSelected(state.data.sources[0].name);
  }, [state.data, selected]);

  const all = state.data?.sources ?? [];
  const sel: SourceRow | undefined = all.find((s) => s.name === selected);
  const groups = new Set(all.map((s) => s.provenance_group));

  return (
    <>
      <PageHeader
        title="Threat Intelligence Sources"
        description="Sources enregistrées, état de connexion réel, fiabilité, rendement et historique des collectes. Une clé absente est signalée « Configuration manquante », jamais masquée."
        updatedAt={state.updatedAt}
        onRefresh={() => { state.refresh(); runs.refresh(); }}
        actions={<OperationButton path="/iocs/collect/run?limit=50" label="Collecter toutes les sources" variant="primary" onDone={() => { state.refresh(); runs.refresh(); }}
          description="Interroge chaque collecteur actif (50 éléments max par source). Une source en échec n'empêche pas les autres ; chaque échec est conservé avec son message d'erreur." />}
      />

      {state.data && (
        <KpiGrid cols="grid-cols-2 md:grid-cols-4">
          <Kpi label="Sources enregistrées" value={all.length} hint={`${groups.size} groupe(s) de provenance indépendants`} />
          <Kpi label="Opérationnelles" value={all.filter((s) => s.connection === "connected").length} tone="var(--color-ok)" hint="dernière collecte réussie" />
          <Kpi label="Configuration manquante" value={all.filter((s) => s.connection === "not_configured").length} tone="var(--color-warn)" hint="clé API absente du .env" />
          <Kpi label="En erreur" value={all.filter((s) => s.connection === "unreachable").length} tone="var(--color-danger)" hint="dernière tentative échouée" />
        </KpiGrid>
      )}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Card bodyClass="" title="Catalogue des sources">
          <AsyncBlock state={state} rows={8} empty={(d) => d.sources.length === 0} emptyTitle="Aucune source enregistrée">
            {(d) => (
              <Table minWidth={860} columns={[{ key: "n", label: "Source" }, { key: "c", label: "Connexion" }, { key: "r", label: "Fiabilité" }, { key: "i", label: "IOC", align: "right" }, { key: "l", label: "Dernier succès" }, { key: "x", label: "Collectes 30 j", align: "right" }]}>
                {d.sources.map((s) => (
                  <Row key={s.id} onClick={() => setSelected(s.name)} selected={s.name === selected}>
                    <td className="td">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{s.name}</span>
                        {s.kind === "SYNTHETIC" && <Badge tone="warn">LAB</Badge>}
                        {!s.enabled && <Badge>désactivée</Badge>}
                      </div>
                      <div className="text-[11.5px] text-fg-subtle">{s.provenance_group}</div>
                    </td>
                    <td className="td"><ConnBadge state={s.connection} /></td>
                    <td className="td"><Reliability value={s.reliability} /></td>
                    <td className="td num text-right font-medium">{fmtNum(s.ioc_count)}</td>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtDate(s.last_success_at)}>{fmtRelative(s.last_success_at)}</td>
                    <td className="td num text-right text-[12.5px]">{s.runs_30d}{s.failures_30d ? <span className="ml-1.5 text-danger">({s.failures_30d} ✕)</span> : null}</td>
                  </Row>
                ))}
              </Table>
            )}
          </AsyncBlock>
        </Card>

        <div className="space-y-4">
          {sel ? (
            <>
              <Card title={sel.name} subtitle={sel.kind ?? undefined}
                actions={COLLECTABLE.has(sel.name) ? <OperationButton path={`/iocs/collect/run?source=${encodeURIComponent(sel.name)}&limit=50`} label="Collecter" onDone={() => { state.refresh(); runs.refresh(); }}
                  description={<>Lance la collecte de <b>{sel.name}</b> uniquement (50 éléments maximum).</>} /> : undefined}>
                <DefList items={[
                  ["Connexion", <ConnBadge state={sel.connection} />],
                  ["Clé API", sel.requires_api_key || sel.key_configured !== null
                    ? sel.key_configured ? <span className="inline-flex items-center gap-1 text-ok"><KeyRound size={13} aria-hidden /> configurée</span> : <span className="text-warn">absente</span>
                    : "non requise"],
                  ["Limite de débit", `${sel.rate_limit_rpm} req/min`],
                  ["Dernier succès", fmtDate(sel.last_success_at)],
                  ["Dernière erreur", fmtDate(sel.last_error_at)],
                  ["Point d'accès", sel.url ? <a href={sel.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-mono text-[11.5px] hover:text-accent-strong">{sel.url.replace(/^https?:\/\//, "").slice(0, 34)}<ExternalLink size={11} aria-hidden /></a> : "—"],
                ]} />
                {sel.last_error && (
                  <div className="mt-3 rounded-md border border-danger/30 bg-danger/8 p-2.5 font-mono text-[11.5px] text-fg-muted">{sel.last_error}</div>
                )}
              </Card>
              <Card title="Historique des collectes" subtitle="audit_logs · action COLLECT" bodyClass="">
                <AsyncBlock state={runs} rows={6} empty={(d) => d.runs.length === 0} emptyTitle="Aucune collecte enregistrée pour cette source">
                  {(d) => (
                    <ol className="max-h-[420px] divide-y divide-line/70 overflow-y-auto">
                      {d.runs.map((r) => (
                        <li key={r.id} className="flex items-start gap-3 px-4 py-2.5">
                          {r.success ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-ok" aria-label="succès" /> : <XCircle size={15} className="mt-0.5 shrink-0 text-danger" aria-label="échec" />}
                          <div className="min-w-0 flex-1 text-[12.5px]">
                            {r.success
                              ? <span><b className="num">{String(r.detail.collected ?? 0)}</b> collectés · <span className="num">{String(r.detail.created ?? 0)}</span> créés · <span className="num">{String(r.detail.duplicates ?? 0)}</span> doublons · <span className="num">{String(r.detail.rejected ?? 0)}</span> rejetés</span>
                              : <span className="break-words text-danger">{r.error}</span>}
                            <div className="font-mono text-[11px] text-fg-subtle">{r.actor}</div>
                          </div>
                          <time className="shrink-0 text-[11.5px] text-fg-subtle" title={fmtDate(r.occurred_at)}>{fmtRelative(r.occurred_at)}</time>
                        </li>
                      ))}
                    </ol>
                  )}
                </AsyncBlock>
              </Card>
            </>
          ) : <Card><EmptyState title="Sélectionnez une source" /></Card>}
        </div>
      </div>
    </>
  );
}
