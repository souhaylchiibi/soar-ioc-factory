import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Copy, ExternalLink, XCircle } from "lucide-react";
import { api, type IocStatus } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtRelative } from "../lib/format";
import { STATUS_META } from "../lib/meta";
import { useApi } from "../lib/useApi";
import { Card, DefList } from "../components/ui/Card";
import { Tabs } from "../components/ui/Controls";
import { AsyncBlock, EmptyState, ErrorState, SkeletonBlock } from "../components/ui/States";
import { Badge, RiskBadge, SeverityBadge, StatusBadge, SyntheticTag, TypeTag } from "../components/ui/Badge";
import { Row, Table } from "../components/ui/Table";
import { ScoreBreakdownView } from "../components/domain/ScoreBreakdown";
import { ScoreLine } from "../components/charts/Charts";
import { ConfirmDialog, useToast } from "../components/ui/Feedback";
import { actionLabel } from "../components/domain/AuditFeed";

// Mirrors backend lifecycle/machine.py TRANSITIONS (the API re-validates).
const MANUAL_TRANSITIONS: Partial<Record<IocStatus, IocStatus[]>> = {
  NORMALIZED: ["REVIEW_REQUIRED", "REJECTED"],
  SCORED: ["PUBLISHED", "MONITORED", "REJECTED", "REVIEW_REQUIRED"],
  PUBLISHED: ["MONITORED", "EXPIRED"],
  MONITORED: ["EXPIRED", "REVIEW_REQUIRED", "PUBLISHED"],
  REVIEW_REQUIRED: ["PUBLISHED", "REJECTED", "MONITORED"],
};

type Tab = "score" | "lifecycle" | "provenance" | "detections" | "publications" | "audit";

export default function IocDetail() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const toast = useToast();
  const ioc = useApi(() => api.ioc(id), [id]);
  const act = useApi(() => api.iocActivity(id), [id]);
  const [tab, setTab] = useState<Tab>("score");
  const [target, setTarget] = useState<IocStatus | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  if (ioc.error) return <ErrorState error={ioc.error} onRetry={ioc.reload} />;
  if (!ioc.data) return <div className="card"><SkeletonBlock rows={10} /></div>;
  const d = ioc.data;
  const options = MANUAL_TRANSITIONS[d.status] ?? [];

  const doTransition = async () => {
    if (!target) return;
    setBusy(true);
    try {
      await api.transition(d.id, target, reason.trim());
      toast({ kind: "success", title: `Statut changé : ${STATUS_META[target].label}`, message: "Transition validée par la machine à états et inscrite à l'audit." });
      setTarget(null);
      setReason("");
      ioc.refresh();
      act.refresh();
    } catch (e) {
      toast({ kind: "error", title: "Transition refusée", message: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const a = act.data;
  return (
    <>
      <Link to="/threat-intel" className="mb-3 inline-flex items-center gap-1.5 text-[12.5px] text-fg-muted hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> Threat Intelligence
      </Link>

      <header className="card mb-4 p-4 md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <TypeTag type={d.type} /><StatusBadge status={d.status} />{d.is_synthetic && <SyntheticTag />}
            </div>
            <div className="flex items-center gap-2">
              <h1 className="break-all font-mono text-[18px] font-medium md:text-[20px]">{d.value}</h1>
              <button type="button" className="icon-btn h-8 w-8 shrink-0" aria-label="Copier la valeur"
                onClick={() => navigator.clipboard?.writeText(d.value).then(() => toast({ kind: "info", title: "Valeur copiée" }))}>
                <Copy size={15} />
              </button>
            </div>
            {d.raw_value !== d.value && <p className="mt-1 text-[12px] text-fg-subtle">Valeur brute reçue : <span className="font-mono">{d.raw_value}</span></p>}
          </div>
          <div className="grid shrink-0 grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
            <Stat label="Score" value={d.score ?? "—"} />
            <Stat label="Risque" value={<RiskBadge risk={d.risk_level} />} />
            <Stat label="Sources indép." value={d.independent_source_count} />
            <Stat label="Détections" value={<>{d.detection_count}{d.false_positive_count ? <span className="text-[12px] text-fg-subtle"> · {d.false_positive_count} FP</span> : null}</>} />
          </div>
        </div>

        {can("analyst") && options.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <span className="mr-1 text-[12px] text-fg-muted">Décision analyste :</span>
            {options.map((s) => (
              <button key={s} type="button" className="btn-secondary h-8" onClick={() => setTarget(s)}>→ {STATUS_META[s].label}</button>
            ))}
          </div>
        )}
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card bodyClass="">
          <div className="px-2 pt-1">
            <Tabs<Tab> label="Dossier de l'IOC" value={tab} onChange={setTab} items={[
              { value: "score", label: "Score" },
              { value: "lifecycle", label: "Cycle de vie", count: d.lifecycle.length },
              { value: "provenance", label: "Provenance", count: a?.provenance.length },
              { value: "detections", label: "Détections", count: a?.detections.length },
              { value: "publications", label: "Publications", count: a?.publications.length },
              { value: "audit", label: "Historique", count: a?.audit.length },
            ]} />
          </div>
          <div className="p-4 md:p-5" role="tabpanel">
            {tab === "score" && (
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="eyebrow mb-3">Justification du score</h3>
                  {d.score_breakdown ? <ScoreBreakdownView breakdown={d.score_breakdown} /> : <EmptyState title="Pas encore noté">Le score est calculé après l'enrichissement.</EmptyState>}
                </div>
                <div>
                  <h3 className="eyebrow mb-3">Historique des scores</h3>
                  <AsyncBlock state={act} rows={4}>
                    {(x) => x.score_history.length > 1 ? <ScoreLine data={x.score_history} />
                      : x.score_history.length === 1 ? <p className="text-[13px] text-fg-muted">Un seul calcul : <b className="num text-fg">{x.score_history[0].score}</b> le {fmtDate(x.score_history[0].computed_at)} (politique {x.score_history[0].policy}).</p>
                      : <EmptyState title="Aucun calcul enregistré" />}
                  </AsyncBlock>
                  <h3 className="eyebrow mb-2 mt-6">Enrichissements</h3>
                  <AsyncBlock state={act} rows={3}>
                    {(x) => x.enrichments.length ? (
                      <ul className="space-y-2 text-[12.5px]">
                        {x.enrichments.map((e, i) => (
                          <li key={i} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2">
                            <span><b className="font-medium">{e.provider}</b>{e.is_synthetic && <span className="ml-2"><SyntheticTag /></span>}
                              <span className="block text-fg-muted">{e.error ? <span className="text-danger">erreur : {e.error}</span> : e.verdict ?? "sans verdict"}</span></span>
                            <span className="shrink-0 text-fg-subtle">{fmtRelative(e.fetched_at)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-[12.5px] text-fg-muted">Aucun enrichissement stocké.</p>}
                  </AsyncBlock>
                </div>
              </div>
            )}

            {tab === "lifecycle" && (
              <ol className="relative space-y-4 border-l border-line pl-5">
                {d.lifecycle.map((e, i) => (
                  <li key={i} className="relative">
                    <span aria-hidden className="absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full border-2 border-bg bg-accent" />
                    <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
                      <span className="text-fg-subtle">{e.from_status ? STATUS_META[e.from_status].label : "Création"}</span>
                      <span aria-hidden>→</span><StatusBadge status={e.to_status} />
                      {e.verified && <Badge tone="ok"><CheckCircle2 size={12} aria-hidden /> vérifié</Badge>}
                      {e.score_after !== null && <span className="num font-mono text-[11.5px] text-fg-subtle">score {e.score_before ?? "—"} → {e.score_after}</span>}
                    </div>
                    <p className="mt-1 text-[13px]">{e.reason}</p>
                    <p className="mt-0.5 text-[11.5px] text-fg-subtle">{fmtDate(e.created_at)} · <span className="font-mono">{e.actor}</span>{e.triggered_by && e.triggered_by !== e.actor ? ` · via ${e.triggered_by}` : ""}</p>
                  </li>
                ))}
                {d.lifecycle.length === 0 && <EmptyState title="Aucune transition enregistrée" />}
              </ol>
            )}

            {tab === "provenance" && (
              <AsyncBlock state={act} empty={(x) => x.provenance.length === 0} emptyTitle="Aucune source rattachée">
                {(x) => (
                  <Table columns={[{ key: "s", label: "Source" }, { key: "g", label: "Groupe de provenance" }, { key: "r", label: "Fiabilité", align: "right" }, { key: "f", label: "Première vue" }, { key: "l", label: "Dernière vue" }, { key: "e", label: "Référence" }]} minWidth={760}>
                    {x.provenance.map((p) => (
                      <Row key={p.source}>
                        <td className="td font-medium">{p.source}</td>
                        <td className="td"><Badge>{p.provenance_group}</Badge></td>
                        <td className="td num text-right">{p.reliability}</td>
                        <td className="td text-[12px] text-fg-muted">{fmtDate(p.first_seen_at)}</td>
                        <td className="td text-[12px] text-fg-muted">{fmtDate(p.last_seen_at)}</td>
                        <td className="td max-w-[220px] truncate font-mono text-[11.5px] text-fg-muted">
                          {p.external_url ? <a href={p.external_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-accent-strong">{p.external_id ?? "lien"}<ExternalLink size={11} aria-hidden /></a> : p.external_id ?? "—"}
                        </td>
                      </Row>
                    ))}
                  </Table>
                )}
              </AsyncBlock>
            )}

            {tab === "detections" && (
              <AsyncBlock state={act} empty={(x) => x.detections.length === 0} emptyTitle="Aucune détection capteur pour cet IOC">
                {(x) => (
                  <Table columns={[{ key: "t", label: "Horodatage" }, { key: "s", label: "Capteur" }, { key: "r", label: "Règle" }, { key: "v", label: "Sévérité" }, { key: "q", label: "Qualification" }]} minWidth={640}>
                    {x.detections.map((det) => (
                      <Row key={det.id}>
                        <td className="td text-[12px] text-fg-muted">{fmtDate(det.matched_at)}</td>
                        <td className="td"><Badge>{det.sensor}</Badge></td>
                        <td className="td font-mono text-[12px]">{det.rule_id ?? "—"}{det.signature && <span className="block font-sans text-fg-subtle">{det.signature}</span>}</td>
                        <td className="td"><SeverityBadge severity={det.severity} /></td>
                        <td className="td">{det.triage === "pending" ? <Badge tone="warn">à qualifier</Badge> : det.triage === "false_positive" ? <Badge tone="neutral">faux positif</Badge> : <Badge tone="danger">confirmée</Badge>}</td>
                      </Row>
                    ))}
                  </Table>
                )}
              </AsyncBlock>
            )}

            {tab === "publications" && (
              <AsyncBlock state={act} empty={(x) => x.publications.length === 0} emptyTitle="Jamais publié">
                {(x) => (
                  <Table columns={[{ key: "c", label: "Cible" }, { key: "r", label: "Référence" }, { key: "s", label: "Statut" }, { key: "p", label: "Publié" }, { key: "v", label: "Révoqué" }]} minWidth={640}>
                    {x.publications.map((p) => (
                      <Row key={p.id}>
                        <td className="td font-medium">{p.target}</td>
                        <td className="td max-w-[260px] truncate font-mono text-[11.5px] text-fg-muted" title={p.target_ref ?? ""}>{p.target_ref ?? "—"}</td>
                        <td className="td">{p.status === "verified" ? <Badge tone="ok" dot>vérifiée</Badge> : p.status === "revoked" ? <Badge>révoquée</Badge> : <Badge tone={p.status === "failed" ? "danger" : "warn"}>{p.status}</Badge>}</td>
                        <td className="td text-[12px] text-fg-muted">{fmtDate(p.published_at)}</td>
                        <td className="td text-[12px] text-fg-muted">{fmtDate(p.revoked_at)}</td>
                      </Row>
                    ))}
                  </Table>
                )}
              </AsyncBlock>
            )}

            {tab === "audit" && (
              <AsyncBlock state={act} empty={(x) => x.audit.length === 0} emptyTitle="Aucune entrée d'audit liée">
                {(x) => (
                  <ol className="divide-y divide-line/70">
                    {x.audit.map((e) => (
                      <li key={e.id} className="flex items-start gap-3 py-2.5">
                        {e.success ? <CheckCircle2 size={15} className="mt-0.5 text-ok" aria-label="succès" /> : <XCircle size={15} className="mt-0.5 text-danger" aria-label="échec" />}
                        <div className="min-w-0 flex-1 text-[12.5px]">
                          <span className="font-medium">{actionLabel(e.action)}</span> <span className="font-mono text-fg-subtle">{e.actor}</span>
                          <pre className="mt-1 max-h-28 overflow-auto rounded bg-bg px-2 py-1.5 font-mono text-[11px] text-fg-muted">{JSON.stringify(e.detail, null, 0)}</pre>
                        </div>
                        <span className="shrink-0 text-[11.5px] text-fg-subtle">{fmtDate(e.occurred_at)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </AsyncBlock>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Chronologie">
            <DefList items={[
              ["Première apparition", fmtDate(d.first_seen_at)],
              ["Dernière apparition", fmtDate(d.last_seen_at)],
              ["Expiration", d.expires_at ? <span title={fmtDate(d.expires_at)}>{fmtRelative(d.expires_at)}</span> : "non définie"],
              ["Retrait", fmtDate(d.removed_at)],
            ]} />
          </Card>
          <Card title="Contexte">
            <DefList items={[
              ["Verdicts", d.enrichment_verdicts.join(", ") || "—"],
              ["Tags", d.tags.length ? <span className="flex flex-wrap justify-end gap-1">{d.tags.map((t) => <Badge key={t}>{t}</Badge>)}</span> : "—"],
              ["Origine", d.is_synthetic ? <span className="text-warn">synthétique (laboratoire)</span> : "renseignement réel"],
              ["Identifiant", <span className="font-mono text-[11px]">{d.id}</span>],
            ]} />
          </Card>
        </div>
      </div>

      <ConfirmDialog open={!!target} title={target ? `Passer en « ${STATUS_META[target].label} »` : ""} busy={busy}
        danger={target === "REJECTED" || target === "EXPIRED"} confirmLabel="Appliquer"
        onCancel={() => { setTarget(null); setReason(""); }}
        onConfirm={() => { if (reason.trim().length >= 3) doTransition(); }}>
        <p>Cette décision manuelle est vérifiée par la machine à états puis tracée avec votre identité.</p>
        <label htmlFor="reason" className="mb-1 mt-3 block text-[12px] font-medium text-fg">Justification (obligatoire)</label>
        <textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={500}
          className="input h-auto py-2 font-sans" placeholder="Ex. : confirmé par l'investigation INC-2026-114" />
        {reason.trim().length > 0 && reason.trim().length < 3 && <p className="mt-1 text-[11.5px] text-danger">3 caractères minimum.</p>}
      </ConfirmDialog>
    </>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11.5px] text-fg-subtle">{label}</div>
      <div className="num mt-0.5 text-[18px] font-semibold">{value}</div>
    </div>
  );
}
