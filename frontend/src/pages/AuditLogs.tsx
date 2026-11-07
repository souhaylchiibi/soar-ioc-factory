import { useState } from "react";
import { ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtDate } from "../lib/api";

/** Append-only audit trail (table audit_logs, trigger-protected). */
export default function AuditLogs() {
  const [action, setAction] = useState("");
  const [onlyFailed, setOnlyFailed] = useState(false);

  const qs = new URLSearchParams({ limit: "150" });
  if (action) qs.set("action", action);
  if (onlyFailed) qs.set("success", "false");

  const { data, error, loading } = useApi(() => api.audit(`?${qs.toString()}`), [action, onlyFailed]);
  const actions = useApi(api.auditActions, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const failed = data?.entries.filter((e) => !e.success).length ?? 0;

  return (
    <>
      <PageTitle
        title="Audit Logs"
        subtitle="Journal append-only — UPDATE/DELETE refusés par trigger PostgreSQL."
      />

      <div className="grid grid-cols-3 gap-4 mb-5">
        <Stat value={data?.total ?? 0} label="Entrées correspondantes" tone="signal" />
        <Stat value={failed} label="Échecs dans la vue" tone={failed > 0 ? "bad" : "good"} />
        <Stat value={actions.data?.actions.length ?? 0} label="Types d'actions distincts" tone="violet" />
      </div>

      <Panel className="mb-5">
        <div className="flex flex-wrap gap-4 items-center">
          <label className="text-sm">
            <div className="text-muted text-[11px] mb-1 uppercase">Action</div>
            <select value={action} onChange={(e) => setAction(e.target.value)}
              className="bg-void border border-edge rounded px-2 py-1.5 text-sm">
              <option value="">toutes</option>
              {(actions.data?.actions ?? []).map((a) => (
                <option key={a.action} value={a.action}>
                  {a.action} ({a.count})
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm pt-4">
            <input type="checkbox" checked={onlyFailed} onChange={(e) => setOnlyFailed(e.target.checked)}
              className="accent-red-500" />
            uniquement les échecs
          </label>
        </div>
      </Panel>

      <Panel>
        <Table head={["#", "Horodatage", "Acteur", "Action", "Entité", "Succès", "Détail"]}>
          {(data?.entries ?? []).map((e) => (
            <tr key={e.id} className="hover:bg-white/5">
              <td className="table-td text-muted font-mono text-xs">{e.id}</td>
              <td className="table-td text-xs text-muted whitespace-nowrap">{fmtDate(e.occurred_at)}</td>
              <td className="table-td mono text-xs">{e.actor}</td>
              <td className="table-td"><span className="badge badge-info">{e.action}</span></td>
              <td className="table-td mono text-xs text-muted break-all max-w-[180px] truncate">
                {e.entity_type ?? "—"} {e.entity_id ? `#${e.entity_id.slice(0, 8)}` : ""}
              </td>
              <td className="table-td">
                {e.success ? <span className="badge badge-ok">✓</span> : <span className="badge badge-bad">✗</span>}
              </td>
              <td className="table-td text-[11px] mono text-muted max-w-[340px] truncate">
                {e.error ?? JSON.stringify(e.detail).slice(0, 140)}
              </td>
            </tr>
          ))}
        </Table>
      </Panel>
    </>
  );
}
