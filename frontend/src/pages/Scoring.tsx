import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { fmtNum } from "../lib/format";
import { DECISION_META, RISK_META, RISK_ORDER } from "../lib/meta";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { Select, Toggle } from "../components/ui/Controls";
import { AsyncBlock, EmptyState, SkeletonBlock } from "../components/ui/States";
import { Badge, RiskBadge, StatusBadge, SyntheticTag, TypeTag } from "../components/ui/Badge";
import { Pagination, Row, Table } from "../components/ui/Table";
import { ScoreHistogram } from "../components/charts/Charts";
import { ScoreBreakdownView } from "../components/domain/ScoreBreakdown";

const LIMIT = 40;

function ScoreCell({ score }: { score: number }) {
  const color = score >= 80 ? "var(--color-ok)" : score >= 50 ? "var(--color-info)" : "var(--color-risk-low)";
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-3" aria-hidden>
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="num w-7 text-right font-semibold">{score}</span>
    </div>
  );
}

export default function Scoring() {
  const [params, setParams] = useSearchParams();
  const risk = params.get("risk") ?? "";
  const hideLab = params.get("lab") === "0";
  const offset = Number(params.get("offset") ?? 0);
  const [selected, setSelected] = useState<string | null>(null);

  const stats = useApi(api.stats, []);
  const qs = new URLSearchParams({ sort: "score_desc", limit: String(LIMIT), offset: String(offset) });
  if (risk) qs.set("risk", risk);
  if (hideLab) qs.set("synthetic", "false");
  const ranked = useApi(() => api.iocs(`?${qs}`), [qs.toString()]);
  const detail = useApi(() => api.ioc(selected!), [selected], { enabled: !!selected });
  const funnel = useApi(api.funnel, []);

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    if (!("offset" in patch)) next.delete("offset");
    setParams(next, { replace: true });
  };

  const s = stats.data;
  return (
    <>
      <PageHeader
        title="Scoring & Risk Analysis"
        description="Score de confiance explicable (5 composantes pondérées, pénalités de faux positifs). Les seuils publish / monitor / reject sont appliqués par l'API et chaque décision conserve sa justification."
        updatedAt={ranked.updatedAt}
        onRefresh={() => { stats.refresh(); ranked.refresh(); funnel.refresh(); detail.refresh(); }}
      />

      <KpiGrid cols="grid-cols-2 md:grid-cols-4">
        {(["publish", "monitor", "reject", "review"] as const).map((k) => (
          <Kpi key={k} label={`Décision : ${DECISION_META[k].label}`} value={fmtNum(funnel.data?.decisions[k])}
            hint={DECISION_META[k].rule} tone={`var(--color-${DECISION_META[k].tone === "ok" ? "ok" : DECISION_META[k].tone === "info" ? "info" : DECISION_META[k].tone === "danger" ? "danger" : "warn"})`} />
        ))}
      </KpiGrid>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Distribution des scores" subtitle={s?.avg_score !== undefined && s?.avg_score !== null ? `Score moyen ${fmtNum(s.avg_score)} · seuils : 50 (surveillance) et 80 (publication)` : undefined}>
          {s ? (Object.values(s.score_distribution).some(Boolean) ? <ScoreHistogram buckets={s.score_distribution} /> : <EmptyState title="Aucun IOC noté" />) : <SkeletonBlock rows={6} />}
        </Card>
        <Card title="Barème de décision">
          <ul className="space-y-3 text-[12.5px]">
            {(["publish", "monitor", "reject", "review"] as const).map((k) => (
              <li key={k} className="flex items-start gap-3">
                <Badge tone={DECISION_META[k].tone} dot>{DECISION_META[k].label}</Badge>
                <span className="text-fg-muted">{k === "publish" ? "Score ≥ 80 : publié vers la liste de détection, puis relu avant d'être marqué vérifié."
                  : k === "monitor" ? "50 ≤ score < 80 : suivi, rapproché des alertes, sans blocage."
                  : k === "reject" ? "Score < 50 : écarté, la justification reste consultable."
                  : "Cas ambigu : attend une décision analyste (transition manuelle tracée)."}</span>
              </li>
            ))}
          </ul>
          <h3 className="eyebrow mb-2 mt-5">Niveau de risque</h3>
          <ul className="space-y-1.5 text-[12.5px]">
            {RISK_ORDER.map((r) => (
              <li key={r} className="flex justify-between"><RiskBadge risk={r} /><span className="text-fg-muted">{r === "CRITICAL" ? "≥ 80" : r === "HIGH" ? "65 – 79" : r === "MEDIUM" ? "50 – 64" : "< 50"}</span></li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card bodyClass="" title="Classement par score"
          actions={<div className="flex items-end gap-3">
            <Toggle label="Sans lab" checked={hideLab} onChange={(v) => set({ lab: v ? "0" : null })} />
            <Select label="Risque" value={risk} className="w-36" onChange={(v) => set({ risk: v })}
              options={[{ value: "", label: "Tous" }, ...RISK_ORDER.map((r) => ({ value: r, label: RISK_META[r].label }))]} />
          </div>}>
          <AsyncBlock state={ranked} rows={10}>
            {(d) => d.items.filter((i) => i.score !== null).length === 0 ? <EmptyState title="Aucun IOC noté pour ces filtres" /> : (
              <>
                <Table minWidth={760} columns={[{ key: "r", label: "#", align: "right" }, { key: "v", label: "Indicateur" }, { key: "s", label: "Score" }, { key: "k", label: "Risque" }, { key: "st", label: "Statut" }, { key: "d", label: "Dét.", align: "center" }]}>
                  {d.items.filter((i) => i.score !== null).map((i, idx) => (
                    <Row key={i.id} onClick={() => setSelected(i.id)} selected={selected === i.id}>
                      <td className="td num text-right text-fg-subtle">{offset + idx + 1}</td>
                      <td className="td max-w-[300px]"><span className="flex items-center gap-2"><TypeTag type={i.type} /><span className="truncate font-mono text-[12.5px]">{i.value}</span>{i.is_synthetic && <SyntheticTag />}</span></td>
                      <td className="td"><ScoreCell score={i.score!} /></td>
                      <td className="td"><RiskBadge risk={i.risk_level} /></td>
                      <td className="td"><StatusBadge status={i.status} /></td>
                      <td className="td num text-center">{i.detection_count}</td>
                    </Row>
                  ))}
                </Table>
                <Pagination total={d.total} offset={offset} limit={LIMIT} onChange={(o) => set({ offset: String(o) })} />
              </>
            )}
          </AsyncBlock>
        </Card>

        <Card title="Justification" subtitle={detail.data ? <Link to={`/iocs/${detail.data.id}`} className="font-mono hover:text-accent-strong">{detail.data.value}</Link> : "Sélectionnez un IOC dans le classement"}>
          {!selected ? <EmptyState title="Aucun IOC sélectionné">Chaque composante du score est affichée avec ses points et son explication.</EmptyState>
            : <AsyncBlock state={detail} rows={8}>
                {(x) => x.score_breakdown ? <ScoreBreakdownView breakdown={x.score_breakdown} /> : <EmptyState title="Pas de détail de score stocké" />}
              </AsyncBlock>}
        </Card>
      </div>
    </>
  );
}
