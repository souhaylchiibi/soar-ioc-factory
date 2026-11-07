import { ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtDate } from "../lib/api";

const STATUS_TONE = (s: string) =>
  s === "ok" || s === "healthy" ? "badge badge-ok"
    : s === "warning" || s === "degraded" ? "badge badge-warn"
    : "badge badge-bad";

/** Stack health as observable from the API (DB, migrations, trigger, keys). */
export default function SystemHealth() {
  const { data, error, loading } = useApi(api.health);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const checks = data.checks;

  return (
    <>
      <PageTitle
        title="System Health"
        subtitle="État de la plateforme tel qu'observé depuis l'API (lecture seule)."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <Stat
          value={<span className={STATUS_TONE(data.status)}>{data.status}</span>}
          label="État global"
          tone={data.status === "healthy" ? "good" : "warn"}
        />
        <Stat value={data.app.env} label="Environnement" tone="signal" />
        <Stat value={checks.migrations.head ?? "—"} label="Head Alembic" tone="violet" />
        <Stat
          value={checks.activity_freshness.status === "ok" ? "récente" : "> 24h"}
          label="Fraîcheur de l'activité"
          tone={checks.activity_freshness.status === "ok" ? "good" : "warn"}
        />
      </div>

      <Panel title="Vérifications" className="mb-5">
        <Table head={["Composant", "État", "Détail"]}>
          <tr>
            <td className="table-td">Base de données (PostgreSQL)</td>
            <td className="table-td"><span className={STATUS_TONE(checks.database.status)}>{checks.database.status}</span></td>
            <td className="table-td mono text-xs">{checks.database.detail}</td>
          </tr>
          <tr>
            <td className="table-td">Migrations</td>
            <td className="table-td"><span className={STATUS_TONE(checks.migrations.status)}>{checks.migrations.status}</span></td>
            <td className="table-td mono text-xs">head = {checks.migrations.head ?? "—"}</td>
          </tr>
          <tr>
            <td className="table-td">Journal d'audit append-only</td>
            <td className="table-td"><span className={STATUS_TONE(checks.audit_append_only.status)}>{checks.audit_append_only.status}</span></td>
            <td className="table-td mono text-xs">trigger trg_audit_immutable × {checks.audit_append_only.triggers ?? checks.audit_append_only.detail}</td>
          </tr>
          <tr>
            <td className="table-td">Sources de renseignement</td>
            <td className="table-td"><span className={STATUS_TONE(checks.intel_sources.status)}>{checks.intel_sources.status}</span></td>
            <td className="table-td text-xs">
              {checks.intel_sources.enabled}/{checks.intel_sources.total} activées ·
              {" "}{checks.intel_sources.require_key} avec clé requise
            </td>
          </tr>
          <tr>
            <td className="table-td">Fraîcheur de l'activité</td>
            <td className="table-td"><span className={STATUS_TONE(checks.activity_freshness.status)}>{checks.activity_freshness.status}</span></td>
            <td className="table-td mono text-xs">dernière : {fmtDate(checks.last_activity_at)}</td>
          </tr>
        </Table>
      </Panel>

      <div className="grid lg:grid-cols-2 gap-5">
        <Panel title="Clés API configurées (présence uniquement — valeurs jamais renvoyées)">
          <Table head={["Service", "Configurée"]}>
            {Object.entries(checks.api_keys as Record<string, boolean>).map(([k, v]) => (
              <tr key={k}>
                <td className="table-td">{k}</td>
                <td className="table-td">
                  {v ? <span className="badge badge-ok">✓ configurée</span> : <span className="badge badge-warn">absente</span>}
                </td>
              </tr>
            ))}
          </Table>
        </Panel>

        <Panel title="Inventaire (instantané)">
          <Table head={["Statut", "Nombre"]}>
            {Object.entries(checks.inventory as Record<string, number>).map(([k, v]) => (
              <tr key={k}>
                <td className="table-td">{k}</td>
                <td className="table-td mono">{v}</td>
              </tr>
            ))}
          </Table>
          <p className="text-muted text-xs mt-3">Vérifié le {fmtDate(data.checked_at)}</p>
        </Panel>
      </div>
    </>
  );
}
