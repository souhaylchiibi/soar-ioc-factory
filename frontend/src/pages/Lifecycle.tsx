import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, fmtNum, fmtRelative } from "../lib/format";
import { DECISION_META, STATUS_META } from "../lib/meta";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Tabs } from "../components/ui/Controls";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { Badge, RiskBadge, StatusBadge, SyntheticTag, TypeTag } from "../components/ui/Badge";
import { Row, Table } from "../components/ui/Table";
import { Pipeline } from "../components/domain/Pipeline";
import { OperationButton } from "../components/domain/OperationButton";

type Tab = "events" | "published" | "expired" | "removed";

export default function Lifecycle() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) ?? "events";
  const navigate = useNavigate();
  const funnel = useApi(api.funnel, [], { pollMs: 60000 });
  const events = useApi(() => api.lifecycle(200), [], { enabled: tab === "events" });
  const list = useApi(
    () => api.iocs(`?status=${tab === "published" ? "PUBLISHED" : tab === "expired" ? "EXPIRED" : "REMOVED"}&limit=200&sort=${tab === "expired" ? "expires_asc" : "last_seen_desc"}`),
    [tab], { enabled: tab !== "events" });
  const c = funnel.data?.current ?? {};
  const refresh = () => { funnel.refresh(); events.refresh(); list.refresh(); };

  return (
    <>
      <PageHeader
        title="IOC Lifecycle"
        description="Les dix étapes de la chaîne, de la collecte au retrait vérifié. Chaque compteur indique la table qui le prouve (survol)."
        updatedAt={funnel.updatedAt}
        onRefresh={refresh}
        actions={<>
          <OperationButton path="/iocs/expire/run" label="Expirer les IOC échus" onDone={refresh}
            description="Passe en EXPIRED les indicateurs dont la date d'expiration est dépassée. Aucun retrait n'est effectué à cette étape." />
          <OperationButton path="/iocs/remove/run" label="Retirer (vérifié)" danger onDone={refresh}
            description="Révoque les publications des IOC expirés, relit chaque révocation, puis seulement passe en REMOVED. Un retrait non confirmé reste en échec." />
        </>}
      />

      <Card title="Chaîne de traitement" subtitle={funnel.data ? `${fmtNum(funnel.data.collected_items)} éléments collectés au total` : undefined}>
        <AsyncBlock state={funnel} rows={3}>
          {(d) => (
            <>
              <Pipeline stages={d.stages} verifiedRemovals={d.verified_removals} />
              <div className="mt-4 grid gap-2 sm:grid-cols-4">
                {Object.entries(d.decisions).map(([k, v]) => {
                  const m = DECISION_META[k];
                  return (
                    <div key={k} className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2">
                      <span className="min-w-0">
                        <Badge tone={m.tone} dot>{m.label}</Badge>
                        <span className="mt-1 block whitespace-nowrap text-[11.5px] text-fg-subtle">{m.rule}</span>
                      </span>
                      <span className="num text-[18px] font-semibold">{fmtNum(v)}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </AsyncBlock>
      </Card>

      <Card className="mt-4" bodyClass="">
        <div className="px-2 pt-1">
          <Tabs<Tab> label="Vues du cycle de vie" value={tab} onChange={(t) => setParams({ tab: t }, { replace: true })} items={[
            { value: "events", label: "Transitions récentes" },
            { value: "published", label: "Publiés", count: c.PUBLISHED },
            { value: "expired", label: "Expirés", count: c.EXPIRED },
            { value: "removed", label: "Retirés", count: c.REMOVED },
          ]} />
        </div>

        {tab === "events" && (
          <AsyncBlock state={events} rows={10} empty={(d) => d.length === 0} emptyTitle="Aucune transition enregistrée">
            {(d) => (
              <Table columns={[{ key: "t", label: "Date" }, { key: "f", label: "Transition" }, { key: "r", label: "Raison" }, { key: "a", label: "Acteur" }, { key: "s", label: "Score", align: "right" }, { key: "v", label: "Preuve" }]} minWidth={900}>
                {d.map((e, i) => (
                  <Row key={i}>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtDate(e.created_at)}>{fmtRelative(e.created_at)}</td>
                    <td className="td whitespace-nowrap"><span className="mr-1.5 text-[12px] text-fg-subtle">{e.from_status ? STATUS_META[e.from_status].label : "Création"} →</span><StatusBadge status={e.to_status} /></td>
                    <td className="td max-w-[420px] truncate text-[12.5px]" title={e.reason}>{e.reason}</td>
                    <td className="td font-mono text-[12px] text-fg-muted">{e.actor}</td>
                    <td className="td num text-right">{e.score_after ?? "—"}</td>
                    <td className="td">{e.verified ? <Badge tone="ok"><CheckCircle2 size={12} aria-hidden /> vérifiée</Badge> : <span className="text-[12px] text-fg-subtle">—</span>}</td>
                  </Row>
                ))}
              </Table>
            )}
          </AsyncBlock>
        )}

        {tab !== "events" && (
          <AsyncBlock state={list} rows={8}>
            {(d) => d.items.length === 0 ? (
              <EmptyState title={tab === "published" ? "Aucun IOC publié" : tab === "expired" ? "Aucun IOC en attente de retrait" : "Aucun retrait effectué"} />
            ) : (
              <Table columns={[{ key: "v", label: "Indicateur" }, { key: "t", label: "Type" }, { key: "s", label: "Statut" }, { key: "sc", label: "Score", align: "right" }, { key: "r", label: "Risque" }, { key: "d", label: "Détections", align: "center" }, { key: "e", label: tab === "removed" ? "Retiré" : "Expiration" }]} minWidth={860}>
                {d.items.map((i) => (
                  <Row key={i.id} onClick={() => navigate(`/iocs/${i.id}`)}>
                    <td className="td max-w-[360px]"><Link to={`/iocs/${i.id}`} className="flex items-center gap-2 font-mono text-[12.5px] hover:text-accent-strong"><span className="truncate">{i.value}</span>{i.is_synthetic && <SyntheticTag />}</Link></td>
                    <td className="td"><TypeTag type={i.type} /></td>
                    <td className="td"><StatusBadge status={i.status} /></td>
                    <td className="td num text-right">{i.score ?? "—"}</td>
                    <td className="td"><RiskBadge risk={i.risk_level} /></td>
                    <td className="td num text-center">{i.detection_count}</td>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted">{tab === "removed" ? fmtDate(i.removed_at) : i.expires_at ? `${fmtRelative(i.expires_at)}` : "—"}</td>
                  </Row>
                ))}
              </Table>
            )}
          </AsyncBlock>
        )}
      </Card>
    </>
  );
}
