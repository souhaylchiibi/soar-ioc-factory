import { ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtShort, statusBadge } from "../lib/api";

export default function Lifecycle() {
  const { data, error, loading } = useApi(() => api.lifecycle(200));

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const verified = data?.filter((e) => e.verified).length ?? 0;
  const actors = new Set(data?.map((e) => e.actor) ?? []);

  return (
    <>
      <PageTitle
        title="IOC Lifecycle"
        subtitle="Historique complet des transitions (table lifecycle_events, append-only)."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <Stat value={data?.length ?? 0} label="Transitions (200 dernières)" tone="signal" />
        <Stat value={verified} label="Opérations vérifiées" tone="good" />
        <Stat value={actors.size} label="Acteurs distincts" tone="violet" />
        <Stat
          value={data?.filter((e) => e.to_status === "REMOVED" && e.verified).length ?? 0}
          label="Retraits vérifiés"
          tone="good"
        />
      </div>

      <Panel>
        <Table head={["Quand", "De", "Vers", "Score", "Acteur", "Déclencheur", "Vérifié", "Raison"]}>
          {(data ?? []).map((e, idx) => (
            <tr key={idx} className="hover:bg-white/5">
              <td className="table-td text-muted text-xs whitespace-nowrap">{fmtShort(e.created_at)}</td>
              <td className="table-td text-muted text-xs">{e.from_status ?? "START"}</td>
              <td className="table-td"><span className={statusBadge(e.to_status)}>{e.to_status}</span></td>
              <td className="table-td mono text-xs whitespace-nowrap">
                {e.score_before !== null || e.score_after !== null
                  ? `${e.score_before ?? "—"} → ${e.score_after ?? "—"}`
                  : "—"}
              </td>
              <td className="table-td text-xs mono">{e.actor}</td>
              <td className="table-td text-xs mono text-muted">{e.triggered_by ?? "—"}</td>
              <td className="table-td">{e.verified ? <span className="badge badge-ok">✓</span> : ""}</td>
              <td className="table-td text-xs max-w-[380px]">{e.reason}</td>
            </tr>
          ))}
        </Table>
      </Panel>
    </>
  );
}
