import { Empty, ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtShort } from "../lib/api";

const NAMES: Record<string, string> = {
  "workflow-1": "1 · IOC Collection",
  "workflow-2": "2 · IOC Normalization",
  "workflow-3": "3 · IOC Enrichment",
  "workflow-4": "4 · IOC Scoring",
  "workflow-5": "5 · IOC Publication",
  "workflow-6": "6 · IOC Monitoring",
  "workflow-7": "7 · IOC Expiration",
  "workflow-8": "8 · IOC Reporting",
};

/** Automation: activity of the 8 n8n workflows, mirrored from the audit trail. */
export default function Workflows() {
  const { data, error, loading } = useApi(api.workflows);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const totalOps = data?.workflows.reduce((s, w) => s + w.operations, 0) ?? 0;
  const totalFailed = data?.workflows.reduce((s, w) => s + w.failed, 0) ?? 0;

  return (
    <>
      <PageTitle
        title="Automation Workflows"
        subtitle={`8 workflows n8n · activité agrégée depuis l'audit trail (${data?.window_days ?? 7} derniers jours).`}
      />

      <div className="grid grid-cols-3 gap-4 mb-5">
        <Stat value={data?.count ?? 0} label="Workflows avec activité" tone="signal" />
        <Stat value={totalOps} label="Opérations exécutées" tone="good" />
        <Stat value={totalFailed} label="Échecs signalés" tone={totalFailed > 0 ? "bad" : "good"} />
      </div>

      <Panel>
        {(data?.count ?? 0) === 0 && <Empty text="Aucune activité de workflow sur la fenêtre." />}
        {(data?.count ?? 0) > 0 && (
          <Table head={["Workflow", "Opérations", "Succès", "Échecs", "Actions principales", "Dernière exécution"]}>
            {(data?.workflows ?? []).map((w) => (
              <tr key={w.workflow} className="hover:bg-white/5">
                <td className="table-td font-semibold">{NAMES[w.workflow] ?? w.workflow}</td>
                <td className="table-td font-mono">{w.operations}</td>
                <td className="table-td">
                  <span className="badge badge-ok">{w.success}</span>
                </td>
                <td className="table-td">
                  {w.failed > 0 ? (
                    <span className="badge badge-bad">{w.failed}</span>
                  ) : (
                    <span className="text-muted">0</span>
                  )}
                </td>
                <td className="table-td text-xs">
                  {w.actions.slice(0, 4).map((a) => (
                    <span key={a.action} className="badge badge-info mr-1">
                      {a.action} ×{a.count}
                    </span>
                  ))}
                </td>
                <td className="table-td text-muted text-xs">{fmtShort(w.last_run_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Panel title="JSON exportables" className="mt-5">
        <p className="text-sm text-muted">
          Les 8 workflows sont exportés en JSON dans{" "}
          <code className="mono text-signal">workflows/n8n/</code> (générés par{" "}
          <code className="mono text-signal">scripts/generate_n8n_workflows.py</code>,
          importables via <code className="mono">n8n import:workflow</code> — ids stables,
          réimport idempotent).
        </p>
      </Panel>
    </>
  );
}
