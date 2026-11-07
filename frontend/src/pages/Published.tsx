import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtDate, fmtShort } from "../lib/api";

/** Indicators distributed to detection systems (status=PUBLISHED). */
export default function Published() {
  const { data, error, loading } = useApi(() => api.iocs("?status=PUBLISHED&limit=100"));

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const items = data?.items ?? [];

  return (
    <>
      <PageTitle
        title="Published Indicators"
        subtitle="IOC distribués aux systèmes de détection (listes générées automatiquement)."
      />

      <div className="grid grid-cols-3 gap-4 mb-5">
        <Stat value={items.length} label="IOC publiés" tone="good" />
        <Stat
          value={items.reduce((s, i) => s + i.detection_count, 0)}
          label="Détections sur publiés"
          tone="signal"
        />
        <Stat value={items.filter((i) => i.is_synthetic).length} label="Synthétiques (lab)" tone="warn" />
      </div>

      <Panel>
        {items.length === 0 && (
          <Empty text="Aucun IOC publié actuellement — le seuil (score ≥ 80) exige corroboration multi-sources ou détections observées." />
        )}
        {items.length > 0 && (
          <Table head={["Valeur", "Type", "Score", "Risque", "Sources", "Détections", "Première vue", "Expiration"]}>
            {items.map((i) => (
              <tr key={i.id} className="hover:bg-white/5">
                <td className="table-td">
                  <Link to={`/iocs/${i.id}`} className="mono text-signal hover:underline break-all">
                    {i.value}
                  </Link>
                </td>
                <td className="table-td">{i.type}</td>
                <td className="table-td font-mono">{i.score}</td>
                <td className="table-td">
                  <span className={i.risk_level === "CRITICAL" ? "badge badge-bad" : "badge badge-warn"}>
                    {i.risk_level}
                  </span>
                </td>
                <td className="table-td text-center font-mono">{i.independent_source_count}</td>
                <td className="table-td text-center font-mono">{i.detection_count}</td>
                <td className="table-td text-muted text-xs">{fmtShort(i.first_seen_at)}</td>
                <td className="table-td text-muted text-xs">{fmtDate(i.expires_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}
