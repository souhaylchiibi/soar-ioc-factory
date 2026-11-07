import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtShort } from "../lib/api";

/** Detection monitoring: matches observed by Suricata / Wazuh / manual. */
export default function Monitoring() {
  const { data, error, loading } = useApi(() => api.detections(100));

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const bySensor: Record<string, number> = {};
  for (const d of data?.detections ?? []) {
    bySensor[d.sensor] = (bySensor[d.sensor] ?? 0) + 1;
  }

  return (
    <>
      <PageTitle
        title="Detection Monitoring"
        subtitle="Correspondances remontées par les capteurs (Suricata eve.json, Wazuh alerts.json, manuel)."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <Stat value={data?.count ?? 0} label="Détections récentes (100)" tone="signal" />
        <Stat value={data?.false_positives_in_window ?? 0} label="Faux positifs dans la fenêtre" tone="bad" />
        <Stat value={bySensor["suricata"] ?? 0} label="Suricata" tone="good" />
        <Stat value={bySensor["wazuh"] ?? 0} label="Wazuh" tone="violet" />
      </div>

      <Panel>
        {(data?.count ?? 0) === 0 && (
          <Empty text="Aucune détection enregistrée — les capteurs ne sont peut-être pas actifs (profils Docker)." />
        )}
        {(data?.count ?? 0) > 0 && (
          <Table head={["Horodatage", "Capteur", "Règle", "IOC", "Faux positif"]}>
            {(data?.detections ?? []).map((d) => (
              <tr key={d.id} className="hover:bg-white/5">
                <td className="table-td text-muted text-xs whitespace-nowrap">{fmtShort(d.matched_at)}</td>
                <td className="table-td">
                  <span className={d.sensor === "suricata" ? "badge badge-ok"
                    : d.sensor === "wazuh" ? "badge badge-violet" : "badge badge-info"}>
                    {d.sensor}
                  </span>
                </td>
                <td className="table-td mono text-xs">{d.rule_id ?? "—"}</td>
                <td className="table-td">
                  <Link to={`/iocs/${d.ioc_id}`} className="mono text-signal hover:underline text-xs">
                    {d.ioc_id.slice(0, 13)}…
                  </Link>
                </td>
                <td className="table-td">
                  {d.is_false_positive === true && <span className="badge badge-bad">oui</span>}
                  {d.is_false_positive === false && <span className="badge badge-ok">non</span>}
                  {d.is_false_positive === null && <span className="text-muted text-xs">non évalué</span>}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}
