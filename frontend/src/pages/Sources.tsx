import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Stat, Table, useApi } from "../components/ui";
import { api, fmtShort } from "../lib/api";

export default function Sources() {
  const { data, error, loading } = useApi(api.sources);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const total = data?.reduce((s, x) => s + x.ioc_count, 0) ?? 0;
  const groups = new Set(data?.map((s) => s.provenance_group) ?? []);

  return (
    <>
      <PageTitle
        title="Threat Intelligence Sources"
        subtitle="Fiabilité, groupe de provenance (anti-collusion) et rendement réel de chaque source."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <Stat value={data?.length ?? 0} label="Sources enregistrées" tone="signal" />
        <Stat value={groups.size} label="Groupes de provenance indépendants" tone="violet" />
        <Stat value={data?.filter((s) => s.enabled).length ?? 0} label="Activées" tone="good" />
        <Stat value={total} label="Liens IOC ↔ source" tone="good" />
      </div>

      <Panel title="Rendement par source (nombre d'IOC liés)" className="mb-5">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data ?? []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="ioc_count" name="IOC" fill="#38bdf8" />
          </BarChart>
        </ResponsiveContainer>
        {data && data.length === 0 && <Empty text="Aucune source enregistrée." />}
      </Panel>

      <Panel>
        <Table head={["Source", "Groupe de provenance", "Fiabilité", "Activée", "IOC liés", "Dernier succès", "Dernière erreur"]}>
          {(data ?? []).map((s) => (
            <tr key={s.name} className="hover:bg-white/5">
              <td className="table-td font-semibold">{s.name}</td>
              <td className="table-td">
                <span className="badge badge-info">{s.provenance_group}</span>
              </td>
              <td className="table-td">
                <div className="flex items-center gap-2">
                  <div className="w-20 h-2 rounded bg-void border border-edge overflow-hidden">
                    <div className="h-full bg-signal" style={{ width: `${s.reliability}%` }} />
                  </div>
                  <span className="font-mono text-xs">{s.reliability}</span>
                </div>
              </td>
              <td className="table-td">
                {s.enabled ? <span className="badge badge-ok">oui</span> : <span className="badge badge-bad">non</span>}
              </td>
              <td className="table-td font-mono">{s.ioc_count}</td>
              <td className="table-td text-muted text-xs">{fmtShort(s.last_success_at)}</td>
              <td className="table-td text-red-300 text-xs mono max-w-[260px] truncate">
                {s.last_error ?? "—"}
              </td>
            </tr>
          ))}
        </Table>
      </Panel>
    </>
  );
}
