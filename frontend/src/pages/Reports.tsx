import { useState } from "react";
import { Download } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { fmtDate, fmtNum, fmtPct, fmtSeconds } from "../lib/format";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { EmptyState, ErrorState, SkeletonBlock } from "../components/ui/States";
import { BarList } from "../components/charts/Charts";
import { OperationButton } from "../components/domain/OperationButton";
import { TYPE_META } from "../lib/meta";

const today = () => new Date().toISOString().slice(0, 10);

export default function Reports() {
  const [date, setDate] = useState(today());
  const rep = useApi(() => api.report(date), [date]);
  const notFound = rep.error instanceof ApiError && rep.error.status === 404;
  const p = rep.data?.payload;

  const download = () => {
    if (!rep.data) return;
    const blob = new Blob([JSON.stringify(rep.data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `rapport-soar-${rep.data.date}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      <PageHeader
        title="Rapports"
        description="Rapport quotidien calculé depuis PostgreSQL par le workflow 8 (ou à la demande). Les chiffres sont figés au moment de la génération."
        actions={<>
          <label className="flex items-center gap-2 text-[12.5px] text-fg-muted">Date
            <input type="date" className="input h-8 w-40" value={date} max={today()} onChange={(e) => setDate(e.target.value || today())} />
          </label>
          {rep.data && <button type="button" className="btn-secondary h-8" onClick={download}><Download size={14} aria-hidden /> JSON</button>}
          {date === today() && <OperationButton path="/reports/daily" label="Générer maintenant" onDone={rep.reload}
            description="Calcule le rapport du jour à partir des données actuelles (remplace celui du jour s'il existe)." />}
        </>}
      />

      {rep.loading && !rep.data && <div className="card"><SkeletonBlock rows={8} /></div>}
      {notFound && <Card><EmptyState title={`Aucun rapport pour le ${new Date(date).toLocaleDateString("fr-FR")}`}>Le workflow 8 ne s'est pas exécuté ce jour-là. Pour aujourd'hui, un analyste peut le générer.</EmptyState></Card>}
      {rep.error && !notFound ? <ErrorState error={rep.error} onRetry={rep.reload} /> : null}

      {p && rep.data && (
        <>
          <p className="mb-3 text-[12px] text-fg-subtle">Généré le {fmtDate(p.generated_at ?? rep.data.generated_at)} · identifiant <span className="font-mono">{rep.data.report_id}</span></p>
          <KpiGrid>
            <Kpi label="Total" value={fmtNum(p.totals.total)} />
            <Kpi label="Actifs" value={fmtNum(p.totals.active)} />
            <Kpi label="Publiés" value={fmtNum(p.totals.published)} tone="var(--color-ok)" />
            <Kpi label="Surveillés" value={fmtNum(p.totals.monitored)} tone="var(--color-info)" />
            <Kpi label="Rejetés" value={fmtNum(p.totals.rejected)} tone="var(--color-risk-low)" />
            <Kpi label="Expirés / retirés" value={`${fmtNum(p.totals.expired)} / ${fmtNum(p.totals.removed)}`} tone="var(--color-warn)" />
          </KpiGrid>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Card title="Qualité du traitement">
              <ul className="space-y-2 text-[13px]">
                {[
                  ["Taux de déduplication", fmtPct(p.quality.dedup_rate)],
                  ["Score moyen", fmtNum(p.quality.avg_score)],
                  ["Ingestion → score", fmtSeconds(p.quality.avg_processing_seconds)],
                  ["Détections", fmtNum(p.quality.detections)],
                  ["Faux positifs", fmtNum(p.quality.false_positives)],
                  ["IOC synthétiques (lab)", fmtNum(p.synthetic_iocs)],
                ].map(([k, v]) => <li key={String(k)} className="flex justify-between gap-3"><span className="text-fg-muted">{k}</span><span className="num font-medium">{v}</span></li>)}
              </ul>
            </Card>
            <Card title="Par type">
              <BarList items={Object.entries(p.by_type as Record<string, number>).map(([k, v]) => ({ label: TYPE_META[k as keyof typeof TYPE_META]?.label ?? k, value: v, color: TYPE_META[k as keyof typeof TYPE_META]?.color }))} />
            </Card>
            <Card title="Sources">
              <BarList items={(p.sources as { name: string; ioc_count: number }[]).sort((a, b) => b.ioc_count - a.ioc_count).map((s) => ({ label: s.name, value: s.ioc_count }))} />
            </Card>
          </div>
        </>
      )}
    </>
  );
}
