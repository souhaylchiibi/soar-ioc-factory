import { useState } from "react";
import { ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtDate } from "../lib/api";

/** Daily report generated from the database (workflow 8). */
export default function Reports() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);

  const { data, error, loading } = useApi(() => api.report(date), [date]);

  const payload = data?.payload;
  const q = payload?.quality ?? {};
  const totals = payload?.totals ?? {};

  return (
    <>
      <PageTitle
        title="Reports"
        subtitle="Rapport quotidien généré depuis PostgreSQL (workflow 8 · POST /reports/daily)."
      />

      <Panel className="mb-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <div className="text-muted text-[11px] mb-1 uppercase">Date du rapport</div>
            <input
              type="date"
              value={date}
              max={today}
              onChange={(e) => setDate(e.target.value)}
              className="bg-void border border-edge rounded px-2 py-1.5 text-sm mono"
            />
          </label>
          {data && (
            <div className="text-xs text-muted">
              Rapport <b className="mono text-signal">{data.report_id.slice(0, 8)}</b> · généré le{" "}
              {fmtDate(data.generated_at)}
            </div>
          )}
        </div>
      </Panel>

      {loading && <Loading />}
      {error ? <ErrorBox error={error} /> : null}

      {data && payload && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
            <Stat value={totals.total ?? 0} label="IOC total" tone="signal" />
            <Stat value={totals.published ?? 0} label="Publiés" tone="good" />
            <Stat value={totals.monitored ?? 0} label="Surveillance" tone="signal" />
            <Stat value={totals.rejected ?? 0} label="Rejetés" tone="bad" />
            <Stat value={totals.expired ?? 0} label="Expirés" tone="warn" />
          </div>

          <div className="grid lg:grid-cols-3 gap-5">
            <Panel title="Qualité du traitement">
              <Table head={["Métrique", "Valeur"]}>
                <tr><td className="table-td">Taux de déduplication</td>
                  <td className="table-td mono">{q.dedup_rate !== null && q.dedup_rate !== undefined ? `${(q.dedup_rate * 100).toFixed(1)} %` : "—"}</td></tr>
                <tr><td className="table-td">Score moyen</td><td className="table-td mono">{q.avg_score ?? "—"}</td></tr>
                <tr><td className="table-td">Temps moyen de traitement</td>
                  <td className="table-td mono">{q.avg_processing_seconds !== null && q.avg_processing_seconds !== undefined ? `${q.avg_processing_seconds}s` : "—"}</td></tr>
                <tr><td className="table-td">Détections</td><td className="table-td mono">{q.detections ?? 0}</td></tr>
                <tr><td className="table-td">Faux positifs</td><td className="table-td mono">{q.false_positives ?? 0}</td></tr>
                <tr><td className="table-td">Synthétiques (lab)</td>
                  <td className="table-td mono">{payload.synthetic_iocs ?? 0}</td></tr>
              </Table>
            </Panel>

            <Panel title="Par type">
              <Table head={["Type", "Nombre"]}>
                {Object.entries(payload.by_type ?? {}).map(([k, v]) => (
                  <tr key={k}><td className="table-td">{k}</td><td className="table-td mono">{String(v)}</td></tr>
                ))}
              </Table>
            </Panel>

            <Panel title="Sources les plus utiles">
              <Table head={["Source", "IOC", "Fiabilité"]}>
                {[...(payload.sources ?? [])]
                  .sort((a: any, b: any) => b.ioc_count - a.ioc_count)
                  .slice(0, 8)
                  .map((s: any) => (
                    <tr key={s.name}>
                      <td className="table-td">{s.name}</td>
                      <td className="table-td mono">{s.ioc_count}</td>
                      <td className="table-td mono">{s.reliability}</td>
                    </tr>
                  ))}
              </Table>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
