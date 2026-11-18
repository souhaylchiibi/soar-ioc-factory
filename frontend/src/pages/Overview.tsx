import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Database, FlaskConical, Radar, ShieldX, Timer, Upload } from "lucide-react";
import { api, type IocType, type RiskLevel } from "../lib/api";
import { fmtNum, fmtPct, fmtRelative, fmtSeconds } from "../lib/format";
import { RISK_META, RISK_ORDER, TYPE_META, WORKFLOWS } from "../lib/meta";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { Card, CardLink } from "../components/ui/Card";
import { AsyncBlock, EmptyState, ErrorState, SkeletonKpis } from "../components/ui/States";
import { Tabs } from "../components/ui/Controls";
import { BarList, Donut, TimelineChart } from "../components/charts/Charts";
import { IntegrationStrip } from "../components/domain/Integrations";
import { AuditFeed } from "../components/domain/AuditFeed";
import { Badge } from "../components/ui/Badge";

const PENDING = ["NEW", "NORMALIZED", "ENRICHED", "SCORED", "REVIEW_REQUIRED"];

export default function Overview() {
  const [days, setDays] = useState<"14" | "30" | "90">("30");
  const stats = useApi(api.stats, [], { pollMs: 60000 });
  const timeline = useApi(() => api.timeline(Number(days)), [days], { pollMs: 120000 });
  const integ = useApi(() => api.integrations(), [], { pollMs: 60000 });
  const sources = useApi(api.sources, []);
  const activity = useApi(() => api.audit("?limit=8"), [], { pollMs: 30000 });
  const runs = useApi(() => api.runs("?limit=40"), [], { pollMs: 60000 });

  const s = stats.data;
  const pending = s ? PENDING.reduce((n, k) => n + (s.by_status[k] ?? 0), 0) : 0;

  const refreshAll = () => [stats, timeline, integ, sources, activity, runs].forEach((x) => x.refresh());

  return (
    <>
      <PageHeader
        title="SOC Overview"
        description="État opérationnel de la plateforme. Chaque valeur est calculée par l'API à partir de PostgreSQL ; les données synthétiques de laboratoire sont signalées séparément."
        updatedAt={stats.updatedAt}
        onRefresh={refreshAll}
        refreshing={stats.loading}
      />

      {stats.error && !s ? <ErrorState error={stats.error} onRetry={stats.reload} /> : null}
      {!s && !stats.error && <SkeletonKpis n={6} />}
      {s && (
        <div className="space-y-3">
          <KpiGrid>
            <Kpi label="IOC en base" value={fmtNum(s.total_iocs)} icon={<Database size={16} />} to="/threat-intel"
              hint={s.synthetic_iocs ? <>dont <b className="text-warn">{fmtNum(s.synthetic_iocs)}</b> synthétiques (lab)</> : "aucun IOC synthétique"} />
            <Kpi label="Publiés" value={fmtNum(s.published_iocs)} tone="var(--color-ok)" icon={<Upload size={16} />}
              to="/threat-intel?status=PUBLISHED" hint="score ≥ 80, publication relue" />
            <Kpi label="En surveillance" value={fmtNum(s.monitored_iocs)} tone="var(--color-info)" icon={<Radar size={16} />}
              to="/threat-intel?status=MONITORED" hint="50 ≤ score < 80" />
            <Kpi label="Rejetés" value={fmtNum(s.rejected_iocs)} tone="var(--color-risk-low)" icon={<ShieldX size={16} />}
              to="/threat-intel?status=REJECTED" hint="score < 50 ou invalide" />
            <Kpi label="Expirés / retirés" value={<>{fmtNum(s.expired_iocs)}<span className="text-[15px] text-fg-subtle"> / {fmtNum(s.removed_iocs)}</span></>}
              tone="var(--color-warn)" icon={<Clock3 size={16} />} to="/lifecycle?tab=expired" hint="retrait vérifié avant REMOVED" />
            <Kpi label="En attente de traitement" value={fmtNum(pending)} tone={pending ? "var(--color-warn)" : undefined}
              icon={<AlertTriangle size={16} />} to="/lifecycle"
              hint={s.review_required ? `${fmtNum(s.review_required)} à revoir par un analyste` : "aucune revue en attente"} />
          </KpiGrid>
          <KpiGrid cols="grid-cols-2 md:grid-cols-4">
            <Kpi label="Détections rapprochées" value={fmtNum(s.total_detections)} tone="var(--color-risk-high)" to="/detections"
              hint={`${fmtNum(s.false_positives)} faux positif(s) qualifié(s)`} />
            <Kpi label="Score moyen" value={fmtNum(s.avg_score)} hint="sur les IOC notés" to="/scoring" />
            <Kpi label="Taux de déduplication" value={fmtPct(s.dedup_rate)} hint={`${fmtNum(s.duplicates_seen)} doublon(s) rattaché(s)`} />
            <Kpi label="Ingestion → score" value={fmtSeconds(s.avg_processing_seconds)} icon={<Timer size={16} />} hint="temps moyen mesuré" />
          </KpiGrid>
        </div>
      )}

      <Card className="mt-4" title="État des intégrations"
        subtitle={integ.data ? `Sondé ${fmtRelative(integ.data.checked_at)} · « Configuration manquante » signifie qu'aucune connexion n'a été tentée` : "Sondage en cours…"}
        actions={<CardLink to="/system-health">System Health</CardLink>} bodyClass="p-3">
        <AsyncBlock state={integ} rows={2}>{(d) => <IntegrationStrip items={d.items} />}</AsyncBlock>
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Activité du pipeline"
          subtitle="IOC créés par jour, décisions appliquées (événements de cycle de vie) et détections capteurs"
          actions={<Tabs label="Fenêtre" value={days} onChange={setDays} items={[{ value: "14", label: "14 j" }, { value: "30", label: "30 j" }, { value: "90", label: "90 j" }]} />}>
          <AsyncBlock state={timeline} rows={6}>
            {(d) => d.series.every((p) => !p.created && !p.published && !p.monitored && !p.rejected && !p.detections)
              ? <EmptyState title="Aucune activité sur cette fenêtre">Élargissez la période ou lancez une collecte depuis l'Automation Center.</EmptyState>
              : <TimelineChart data={d.series} />}
          </AsyncBlock>
        </Card>

        <Card title="Niveaux de risque" subtitle="IOC notés, par niveau dérivé du score">
          {s && (() => {
            const data = RISK_ORDER.map((r: RiskLevel) => ({ name: RISK_META[r].label, value: s.by_risk[r] ?? 0, color: RISK_META[r].color }));
            const total = data.reduce((n, d) => n + d.value, 0);
            return total ? <Donut data={data} total={total} label="IOC notés" height={170} /> : <EmptyState title="Aucun IOC noté" />;
          })()}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card title="Types d'indicateurs">
          {s && (() => {
            const items = (Object.keys(TYPE_META) as IocType[])
              .map((t) => ({ label: TYPE_META[t].label, value: s.by_type[t] ?? 0, color: TYPE_META[t].color }))
              .filter((i) => i.value > 0)
              .sort((a, b) => b.value - a.value);
            return items.length ? <BarList items={items} /> : <EmptyState title="Inventaire vide" />;
          })()}
        </Card>

        <Card title="Sources les plus productives" subtitle="IOC distincts rattachés à chaque source" actions={<CardLink to="/sources">Sources</CardLink>}>
          <AsyncBlock state={sources} rows={5}>
            {(d) => {
              const items = [...d.sources].sort((a, b) => b.ioc_count - a.ioc_count).slice(0, 6)
                .map((x) => ({ label: x.name, value: x.ioc_count, color: x.kind === "SYNTHETIC" ? "var(--color-warn)" : undefined,
                  hint: x.kind === "SYNTHETIC" ? "source synthétique (lab)" : x.provenance_group }));
              return items.some((i) => i.value) ? <BarList items={items} /> : <EmptyState title="Aucun IOC rattaché" />;
            }}
          </AsyncBlock>
        </Card>

        <Card title="Workflows" subtitle="Dernière exécution enregistrée par étape" actions={<CardLink to="/automation">Automation</CardLink>} className="lg:col-span-2 xl:col-span-1">
          <AsyncBlock state={runs} rows={6}>
            {(d) => {
              const last = new Map<string, (typeof d.runs)[number]>();
              for (const r of d.runs) if (!last.has(r.action)) last.set(r.action, r);
              const rows = Object.values(WORKFLOWS).map((w) => ({ w, run: last.get(w.action) }));
              return (
                <ul className="divide-y divide-line/70 text-[12.5px]">
                  {rows.map(({ w, run }) => (
                    <li key={w.action} className="flex items-center justify-between gap-3 py-2">
                      <span>{w.label}</span>
                      {run ? (
                        <span className="flex items-center gap-2 text-fg-subtle">
                          {fmtRelative(run.occurred_at)}
                          {run.success ? <CheckCircle2 size={14} className="text-ok" aria-label="succès" /> : <Badge tone="danger">échec</Badge>}
                        </span>
                      ) : <span className="text-fg-subtle">aucune exécution récente</span>}
                    </li>
                  ))}
                </ul>
              );
            }}
          </AsyncBlock>
        </Card>
      </div>

      <Card className="mt-4" title="Activité récente" subtitle="Journal d'audit append-only" actions={<CardLink to="/audit">Audit Center</CardLink>} bodyClass="">
        <AsyncBlock state={activity} rows={6} empty={(d) => d.entries.length === 0} emptyTitle="Aucune entrée d'audit">
          {(d) => <AuditFeed entries={d.entries} />}
        </AsyncBlock>
      </Card>

      {s && s.synthetic_iocs > 0 && (
        <p className="mt-4 flex items-center gap-2 text-[12px] text-fg-subtle">
          <FlaskConical size={14} aria-hidden />
          {fmtNum(s.synthetic_iocs)} IOC proviennent du collecteur synthétique de laboratoire : ils sont marqués « LAB » partout et filtrables dans Threat Intelligence.
        </p>
      )}
    </>
  );
}
