import { Link, useParams } from "react-router-dom";
import { ErrorBox, Loading, PageTitle, Panel, Table, useApi } from "../components/ui";
import { api, fmtDate, riskBadge, statusBadge } from "../lib/api";

/** IOC detail: the full evidence trail (sources, score, lifecycle, verdicts). */
export default function IocDetailPage() {
  const { id = "" } = useParams();
  const { data, error, loading } = useApi(() => api.ioc(id), [id]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const b = data.score_breakdown;

  return (
    <>
      <Link to="/inventory" className="text-signal text-sm hover:underline">← Retour à l'inventaire</Link>
      <PageTitle title={data.value} subtitle={`${data.type} · id ${data.id}`} />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <div className="card">
          <div className="kpi-value">{data.score ?? "—"}</div>
          <div className="kpi-label">Score {b ? `(${b.policy_version})` : ""}</div>
        </div>
        <div className="card">
          <div className="pt-1"><span className={statusBadge(data.status)}>{data.status}</span></div>
          <div className="kpi-label">Statut</div>
        </div>
        <div className="card">
          <div className="pt-1">
            <span className={riskBadge(data.risk_level)}>{data.risk_level ?? "—"}</span>
          </div>
          <div className="kpi-label">Risque</div>
        </div>
        <div className="card">
          <div className="kpi-value">{data.detection_count}</div>
          <div className="kpi-label">Détections</div>
        </div>
        <div className="card">
          <div className="kpi-value">{data.false_positive_count}</div>
          <div className="kpi-label">Faux positifs</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5 mb-5">
        <Panel title="Informations">
          <dl className="text-sm space-y-2">
            {[
              ["Première apparition", fmtDate(data.first_seen_at)],
              ["Dernière apparition", fmtDate(data.last_seen_at)],
              ["Expiration", fmtDate(data.expires_at)],
              ["Retrait", fmtDate(data.removed_at)],
              ["Sources indépendantes", String(data.independent_source_count)],
              ["Verdicts d'enrichissement", data.enrichment_verdicts.join(", ") || "—"],
              ["Synthétique (lab)", data.is_synthetic ? "oui" : "non"],
              ["Tags", data.tags.join(", ") || "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-edge/50 pb-1.5">
                <dt className="text-muted">{k}</dt>
                <dd className="mono text-right break-all">{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        <Panel title="Détail du score (explicable)">
          {!b && <p className="text-muted text-sm">Non scoré.</p>}
          {b && (
            <>
              <div className="text-4xl font-bold mb-1">{b.final_score}<span className="text-muted text-lg">/100</span></div>
              <div className="text-sm mb-3">Décision : <b className="text-signal">{b.decision}</b></div>
              <ul className="space-y-2">
                {b.components.map((c) => (
                  <li key={c.key} className="text-sm">
                    <div className="flex justify-between">
                      <span>{c.label}</span>
                      <span className="mono">+{c.points}/{c.max_points}</span>
                    </div>
                    <div className="h-1.5 rounded bg-void border border-edge mt-1 overflow-hidden">
                      <div className="h-full bg-signal" style={{ width: `${(c.points / c.max_points) * 100}%` }} />
                    </div>
                    <div className="text-xs text-muted">{c.explanation}</div>
                  </li>
                ))}
                {b.penalties.map((c) => (
                  <li key={c.key} className="text-sm text-red-300 border border-red-900 rounded p-2 bg-red-950/40">
                    <div className="flex justify-between font-semibold">
                      <span>{c.label}</span><span className="mono">{c.points}</span>
                    </div>
                    <div className="text-xs text-red-200/70">{c.explanation}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Panel title={`Sources (${data.sources.length})`}>
          {data.sources.length === 0 && <p className="text-muted text-sm">Aucune source liée.</p>}
          <Table head={["Source", "Groupe", "Fiabilité", "Référence externe"]}>
            {data.sources.map((s) => (
              <tr key={s.name}>
                <td className="table-td">{s.name}</td>
                <td className="table-td"><span className="badge badge-info">{s.provenance_group}</span></td>
                <td className="table-td font-mono">{s.reliability}</td>
                <td className="table-td mono text-xs text-muted break-all">{s.external_id ?? "—"}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        <Panel title={`Cycle de vie (${data.lifecycle.length} transitions)`}>
          <ol className="space-y-2">
            {data.lifecycle.map((e, idx) => (
              <li key={idx} className="border-l-2 border-signal/60 pl-3 py-1">
                <div className="text-sm flex flex-wrap items-center gap-2">
                  <span className="text-muted">{e.from_status ?? "START"}</span>
                  <span>→</span>
                  <b className={statusBadge(e.to_status)}>{e.to_status}</b>
                  {e.verified && <span className="badge badge-ok">✓ vérifié</span>}
                  {e.score_after !== null && (
                    <span className="mono text-xs text-muted">score {e.score_after}</span>
                  )}
                </div>
                <div className="text-xs text-muted mt-0.5">
                  {fmtDate(e.created_at)} · <b>{e.actor}</b>
                  {e.triggered_by && ` · déclencheur ${e.triggered_by}`}
                </div>
                <div className="text-xs">{e.reason}</div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </>
  );
}
