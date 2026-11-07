import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ErrorBox, Loading, PageTitle, Panel, Stat, useApi } from "../components/ui";
import { api } from "../lib/api";

const RISK_COLORS: Record<string, string> = {
  "0-49": "#22c55e", "50-64": "#38bdf8", "65-79": "#f59e0b",
  "80-89": "#f97316", "90-100": "#ef4444",
};
const TYPE_COLORS = ["#38bdf8", "#c084fc", "#22c55e", "#f59e0b", "#ef4444", "#14b8a6"];

export default function Dashboard() {
  const { data: stats, error, loading } = useApi(api.stats);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!stats) return null;

  const scoreData = Object.entries(stats.score_distribution).map(([range, count]) => ({
    range, count,
  }));
  const typeData = Object.entries(stats.by_type).map(([type, count]) => ({ name: type, value: count }));
  const dailyData = stats.daily_new.map((d) => ({
    date: new Date(d.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }),
    count: d.count,
  }));

  return (
    <>
      <PageTitle
        title="Dashboard général"
        subtitle="Toutes les valeurs proviennent de PostgreSQL — aucune statistique simulée."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-5 gap-4 mb-5">
        <Stat value={stats.total_iocs} label="IOC au total" tone="signal" />
        <Stat value={stats.active_iocs} label="IOC actifs" tone="good" />
        <Stat value={stats.published_iocs} label="Publiés" tone="violet" />
        <Stat value={stats.monitored_iocs} label="Sous surveillance" tone="signal" />
        <Stat value={stats.expired_iocs} label="Expirés" tone="warn" />
        <Stat value={stats.rejected_iocs} label="Rejetés" tone="bad" />
        <Stat value={stats.removed_iocs} label="Retirés" tone="bad" />
        <Stat value={stats.review_required} label="À revoir" tone="warn" />
        <Stat value={stats.total_detections} label="Détections observées" tone="good" />
        <Stat value={stats.false_positives} label="Faux positifs" tone="bad" />
        <Stat value={stats.avg_score ?? "—"} label="Score moyen" tone="signal" />
        <Stat
          value={stats.dedup_rate !== null ? `${(stats.dedup_rate * 100).toFixed(1)} %` : "—"}
          label="Taux de déduplication"
          tone="good"
        />
        <Stat
          value={stats.avg_processing_seconds !== null ? `${stats.avg_processing_seconds}s` : "—"}
          label="Temps moyen de traitement"
        />
        <Stat value={stats.synthetic_iocs} label="IOC synthétiques (lab)" tone="warn" />
        <Stat value={stats.duplicates_seen} label="Doublons liés" tone="warn" />
      </div>

      <div className="grid lg:grid-cols-2 gap-5 mb-5">
        <Panel title="Répartition des scores">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" name="IOC">
                {scoreData.map((d) => (
                  <Cell key={d.range} fill={RISK_COLORS[d.range] ?? "#38bdf8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="IOC par type">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={typeData}
                dataKey="value"
                nameKey="name"
                outerRadius={90}
                label={(e) => `${e.name} ${e.percent !== undefined ? (e.percent * 100).toFixed(0) : ""}%`}
              >
                {typeData.map((_, i) => (
                  <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Panel title="Évolution quotidienne (14 derniers jours)">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="count" name="IOC créés" stroke="#38bdf8" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          {dailyData.length === 0 && (
            <p className="text-muted text-xs">Aucune création sur la fenêtre glissante.</p>
          )}
        </Panel>

        <Panel title="Statut de l'inventaire">
          <table className="w-full">
            <tbody>
              {Object.entries(stats.by_status).map(([status, count]) => (
                <tr key={status}>
                  <td className="table-td">{status}</td>
                  <td className="table-td text-right font-mono">{count}</td>
                  <td className="table-td w-1/2">
                    <div className="h-2 rounded bg-signal/70"
                      style={{ width: `${(count / stats.total_iocs) * 100}%` }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-muted text-[11.5px] mt-3">
            Risques : {Object.entries(stats.by_risk).map(([k, v]) => `${k}=${v}`).join(" · ") || "aucun"}
          </p>
        </Panel>
      </div>
    </>
  );
}
