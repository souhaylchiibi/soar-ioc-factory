import { useState } from "react";
import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, PageTitle, Panel, Table, useApi } from "../components/ui";
import { api, fmtShort, statusBadge } from "../lib/api";

const STATUSES = ["", "PUBLISHED", "MONITORED", "ENRICHED", "NORMALIZED", "REJECTED",
  "EXPIRED", "REMOVED", "REVIEW_REQUIRED"];
const TYPES = ["", "IP", "DOMAIN", "URL", "HASH_MD5", "HASH_SHA1", "HASH_SHA256"];

export default function Inventory() {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");

  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  if (type) qs.set("type", type);
  if (q) qs.set("q", q);
  qs.set("limit", "100");

  const { data, error, loading } = useApi(() => api.iocs(`?${qs.toString()}`),
    [status, type, q]);

  return (
    <>
      <PageTitle title="IOC Inventory" subtitle="Inventaire complet, filtrable — API `/iocs`." />

      <Panel className="mb-5">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="text-sm">
            <div className="text-muted text-[11px] mb-1 uppercase">Statut</div>
            <select value={status} onChange={(e) => setStatus(e.target.value)}
              className="bg-void border border-edge rounded px-2 py-1.5 text-sm">
              {STATUSES.map((s) => <option key={s} value={s}>{s || "tous"}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <div className="text-muted text-[11px] mb-1 uppercase">Type</div>
            <select value={type} onChange={(e) => setType(e.target.value)}
              className="bg-void border border-edge rounded px-2 py-1.5 text-sm">
              {TYPES.map((t) => <option key={t} value={t}>{t || "tous"}</option>)}
            </select>
          </label>
          <label className="text-sm flex-1 min-w-[240px]">
            <div className="text-muted text-[11px] mb-1 uppercase">Recherche</div>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="valeur de l'IOC…"
              className="w-full bg-void border border-edge rounded px-2 py-1.5 text-sm mono"
            />
          </label>
          {data && (
            <span className="text-muted text-sm pb-1.5">{data.total} résultat(s)</span>
          )}
        </div>
      </Panel>

      <Panel>
        {loading && <Loading />}
        {error ? <ErrorBox error={error} /> : null}
        {data && data.items.length === 0 && <Empty text="Aucun IOC ne correspond à ces filtres." />}
        {data && data.items.length > 0 && (
          <Table head={["Valeur", "Type", "Statut", "Score", "Risque", "Sources", "Détections", "Vu le", "Synth."]}>
            {data.items.map((i) => (
              <tr key={i.id} className="hover:bg-white/5">
                <td className="table-td">
                  <Link to={`/iocs/${i.id}`} className="mono text-signal hover:underline break-all">
                    {i.value}
                  </Link>
                </td>
                <td className="table-td">{i.type}</td>
                <td className="table-td"><span className={statusBadge(i.status)}>{i.status}</span></td>
                <td className="table-td font-mono">{i.score ?? "—"}</td>
                <td className="table-td">
                  {i.risk_level ? <span className={i.risk_level === "CRITICAL" ? "badge badge-bad" : "badge badge-warn"}>{i.risk_level}</span> : "—"}
                </td>
                <td className="table-td text-center font-mono">{i.independent_source_count}</td>
                <td className="table-td text-center font-mono">{i.detection_count}</td>
                <td className="table-td text-muted text-xs">{fmtShort(i.last_seen_at)}</td>
                <td className="table-td">{i.is_synthetic ? <span className="badge badge-warn">lab</span> : ""}</td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}
