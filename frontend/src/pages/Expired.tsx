import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtDate } from "../lib/api";

/** Expired + removed indicators (automatic retirement trail). */
export default function Expired() {
  const expired = useApi(() => api.iocs("?status=EXPIRED&limit=100"));
  const removed = useApi(() => api.iocs("?status=REMOVED&limit=100"));

  if (expired.loading || removed.loading) return <Loading />;
  if (expired.error) return <ErrorBox error={expired.error} />;
  if (removed.error) return <ErrorBox error={removed.error} />;

  const exp = expired.data?.items ?? [];
  const rem = removed.data?.items ?? [];

  return (
    <>
      <PageTitle
        title="Expired Indicators"
        subtitle="Expiration automatique puis retrait vérifié (workflow 7 : expire → remove)."
      />

      <div className="grid grid-cols-3 gap-4 mb-5">
        <Stat value={exp.length} label="Expirés (en attente de retrait)" tone="warn" />
        <Stat value={rem.length} label="Retirés (retrait vérifié)" tone="good" />
        <Stat value={rem.reduce((s, i) => s + i.detection_count, 0)} label="Détections avant retrait" tone="signal" />
      </div>

      <Panel title="Expirés" className="mb-5">
        {exp.length === 0 && <Empty text="Aucun IOC expiré en attente de retrait." />}
        {exp.length > 0 && (
          <Table head={["Valeur", "Type", "Score", "Expiré le", "Synth."]}>
            {exp.map((i) => (
              <tr key={i.id} className="hover:bg-white/5">
                <td className="table-td">
                  <Link to={`/iocs/${i.id}`} className="mono text-signal hover:underline break-all">{i.value}</Link>
                </td>
                <td className="table-td">{i.type}</td>
                <td className="table-td font-mono">{i.score ?? "—"}</td>
                <td className="table-td text-muted text-xs">{fmtDate(i.expires_at)}</td>
                <td className="table-td">{i.is_synthetic ? <span className="badge badge-warn">lab</span> : ""}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Panel title="Retirés (REMOVED — cycle terminé)">
        {rem.length === 0 && <Empty text="Aucun IOC retiré pour l'instant." />}
        {rem.length > 0 && (
          <Table head={["Valeur", "Type", "Score", "Retiré le", "Détections"]}>
            {rem.map((i) => (
              <tr key={i.id} className="hover:bg-white/5">
                <td className="table-td">
                  <Link to={`/iocs/${i.id}`} className="mono text-signal hover:underline break-all">{i.value}</Link>
                </td>
                <td className="table-td">{i.type}</td>
                <td className="table-td font-mono">{i.score ?? "—"}</td>
                <td className="table-td text-muted text-xs">{fmtDate(i.removed_at)}</td>
                <td className="table-td text-center font-mono">{i.detection_count}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}
