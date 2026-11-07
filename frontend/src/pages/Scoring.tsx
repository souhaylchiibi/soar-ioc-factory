import { useState } from "react";
import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Table, useApi } from "../components/ui";
import { api, statusBadge } from "../lib/api";

/**
 * Scoring page: shows the score distribution AND, for the selected IOC,
 * the full explainable breakdown (why the score is what it is).
 */
export default function Scoring() {
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error, loading } = useApi(
    () => api.iocs("?sort=score_desc&limit=60"),
    [],
  );
  const detail = useApi(() => (selected ? api.ioc(selected) : Promise.resolve(null)), [selected]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const ranked = (data?.items ?? []).filter((i) => i.score !== null);
  const max = ranked[0]?.score ?? 100;

  return (
    <>
      <PageTitle
        title="IOC Scoring"
        subtitle="Score explicable : chaque composante est pondérée et justifiée (politique v1)."
      />

      <div className="grid grid-cols-4 gap-4 mb-5">
        {[
          { l: "≥ 80 → publication auto", c: "text-green-400", f: (s: number) => s >= 80 },
          { l: "65-79 → haut risque", c: "text-amber-400", f: (s: number) => s >= 65 && s < 80 },
          { l: "50-64 → surveillance", c: "text-sky-400", f: (s: number) => s >= 50 && s < 65 },
          { l: "< 50 → rejet", c: "text-red-400", f: (s: number) => s < 50 },
        ].map((b) => (
          <div className="card" key={b.l}>
            <div className={`kpi-value ${b.c}`}>{ranked.filter((i) => b.f(i.score!)).length}</div>
            <div className="kpi-label">{b.l}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-5">
        <Panel title="Classement par score (60 premiers)" className="lg:col-span-3">
          {ranked.length === 0 && <Empty text="Aucun IOC scoré." />}
          <Table head={["#", "Valeur", "Score", "Statut", "Détections"]}>
            {ranked.map((i, idx) => (
              <tr
                key={i.id}
                className={`hover:bg-white/5 cursor-pointer ${selected === i.id ? "bg-signal/10" : ""}`}
                onClick={() => setSelected(i.id)}
              >
                <td className="table-td text-muted">{idx + 1}</td>
                <td className="table-td mono break-all">{i.value}</td>
                <td className="table-td w-40">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded bg-void border border-edge overflow-hidden">
                      <div
                        className={`h-full ${i.score! >= 80 ? "bg-green-500" : i.score! >= 50 ? "bg-sky-500" : "bg-red-500"}`}
                        style={{ width: `${(i.score! / max) * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs w-7 text-right">{i.score}</span>
                  </div>
                </td>
                <td className="table-td"><span className={statusBadge(i.status)}>{i.status}</span></td>
                <td className="table-td text-center font-mono">{i.detection_count}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        <Panel title="Détail explicatif" className="lg:col-span-2">
          {!selected && (
            <p className="text-muted text-sm italic">
              Sélectionnez un IOC pour voir le détail de son score (composantes, pénalités,
              décision).
            </p>
          )}
          {selected && detail.loading && <Loading />}
          {selected && detail.error ? <ErrorBox error={detail.error} /> : null}
          {selected && detail.data && (
            <div>
              <div className="mb-3">
                <Link to={`/iocs/${detail.data.id}`} className="mono text-signal hover:underline break-all">
                  {detail.data.value}
                </Link>
                <div className="mt-1 flex gap-2 items-center">
                  <span className="text-3xl font-bold">{detail.data.score ?? "—"}</span>
                  <span className={detail.data.risk_level ? "badge badge-bad" : "badge badge-info"}>
                    {detail.data.risk_level ?? "non évalué"}
                  </span>
                  <span className={statusBadge(detail.data.status)}>{detail.data.status}</span>
                </div>
              </div>

              {detail.data.score_breakdown ? (
                <>
                  <div className="text-[11px] uppercase text-muted mb-2">
                    Politique {detail.data.score_breakdown.policy_version} · décision{" "}
                    <b className="text-signal">{detail.data.score_breakdown.decision}</b>
                  </div>
                  <ul className="space-y-2">
                    {detail.data.score_breakdown.components.map((c) => (
                      <li key={c.key} className="border border-edge rounded-lg p-2.5 bg-void/60">
                        <div className="flex justify-between text-sm">
                          <span className="font-semibold">{c.label}</span>
                          <span className="mono">
                            +{c.points}/{c.max_points}
                          </span>
                        </div>
                        <div className="h-1.5 rounded bg-panel mt-1.5 overflow-hidden">
                          <div
                            className="h-full bg-signal"
                            style={{ width: `${(c.points / c.max_points) * 100}%` }}
                          />
                        </div>
                        <div className="text-xs text-muted mt-1">{c.explanation}</div>
                      </li>
                    ))}
                    {detail.data.score_breakdown.penalties.map((c) => (
                      <li key={c.key} className="border border-red-900 rounded-lg p-2.5 bg-red-950/40">
                        <div className="flex justify-between text-sm text-red-300">
                          <span className="font-semibold">{c.label}</span>
                          <span className="mono">{c.points}</span>
                        </div>
                        <div className="text-xs text-red-200/70 mt-1">{c.explanation}</div>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-muted text-sm">IOC non encore scoré.</p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
