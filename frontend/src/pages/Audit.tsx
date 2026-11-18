import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Lock, XCircle } from "lucide-react";
import { api, type AuditEntry } from "../lib/api";
import { fmtDate, fmtNum } from "../lib/format";
import { useApi, useDebounced } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { ClearButton, SearchInput, Select } from "../components/ui/Controls";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { Pagination, Row, Table } from "../components/ui/Table";
import { actionLabel } from "../components/domain/AuditFeed";

const LIMIT = 50;

function objectLink(e: AuditEntry) {
  if (!e.entity_id) return <span className="text-fg-subtle">—</span>;
  if (e.entity_type === "ioc") return <Link to={`/iocs/${e.entity_id}`} className="font-mono text-[11.5px] hover:text-accent-strong">ioc/{e.entity_id.slice(0, 8)}…</Link>;
  return <span className="font-mono text-[11.5px] text-fg-muted">{e.entity_type}/{e.entity_id.length > 24 ? `${e.entity_id.slice(0, 8)}…` : e.entity_id}</span>;
}

export default function Audit() {
  const [params, setParams] = useSearchParams();
  const action = params.get("action") ?? "";
  const result = params.get("result") ?? "";
  const actorRaw = params.get("actor") ?? "";
  const offset = Number(params.get("offset") ?? 0);
  const actor = useDebounced(actorRaw, 300);
  const [open, setOpen] = useState<number | null>(null);

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    if (!("offset" in patch)) next.delete("offset");
    setParams(next, { replace: true });
  };
  const qs = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
  if (action) qs.set("action", action);
  if (actor) qs.set("actor", actor);
  if (result) qs.set("success", result === "ok" ? "true" : "false");
  const state = useApi(() => api.audit(`?${qs}`), [qs.toString()]);
  const actions = useApi(api.auditActions, []);

  return (
    <>
      <PageHeader
        title="Audit Center"
        description={<span className="inline-flex items-center gap-1.5"><Lock size={13} aria-hidden /> Journal append-only : toute modification ou suppression est refusée par un trigger PostgreSQL.</span>}
        updatedAt={state.updatedAt}
        onRefresh={state.refresh}
      />

      <Card bodyClass="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <SearchInput label="Acteur (préfixe)" value={actorRaw} onChange={(v) => set({ actor: v })} placeholder="admin, workflow-1, …" className="w-64" />
          <Select label="Action" value={action} onChange={(v) => set({ action: v })} className="w-56"
            options={[{ value: "", label: "Toutes les actions" }, ...(actions.data?.actions ?? []).map((a) => ({ value: a.action, label: `${actionLabel(a.action)} (${a.count})` }))]} />
          <Select label="Résultat" value={result} onChange={(v) => set({ result: v })} className="w-36"
            options={[{ value: "", label: "Tous" }, { value: "ok", label: "Succès" }, { value: "ko", label: "Échecs" }]} />
          {(action || result || actorRaw) && <ClearButton onClick={() => setParams({}, { replace: true })} />}
        </div>
      </Card>

      <Card className="mt-4" bodyClass="" title={state.data ? `${fmtNum(state.data.total)} entrée(s)` : "Journal"}>
        <AsyncBlock state={state} rows={12}>
          {(d) => d.entries.length === 0 ? <EmptyState title="Aucune entrée pour ces filtres" /> : (
            <>
              <Table minWidth={980} columns={[{ key: "id", label: "#", align: "right" }, { key: "t", label: "Date" }, { key: "a", label: "Acteur" }, { key: "x", label: "Action" }, { key: "o", label: "Objet" }, { key: "r", label: "Résultat" }, { key: "d", label: "Détail" }]}>
                {d.entries.map((e) => (
                  <Row key={e.id} onClick={() => setOpen(open === e.id ? null : e.id)} selected={open === e.id}>
                    <td className="td num text-right text-[11.5px] text-fg-subtle">{e.id}</td>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted">{fmtDate(e.occurred_at)}</td>
                    <td className="td font-mono text-[12px]">{e.actor}</td>
                    <td className="td text-[12.5px] font-medium">{actionLabel(e.action)}</td>
                    <td className="td">{objectLink(e)}</td>
                    <td className="td">{e.success ? <CheckCircle2 size={15} className="text-ok" aria-label="succès" /> : <span className="inline-flex items-center gap-1 text-[12px] text-danger"><XCircle size={14} aria-hidden />{e.error?.slice(0, 40) ?? "échec"}</span>}</td>
                    <td className="td max-w-[360px] font-mono text-[11px] text-fg-muted">
                      {open === e.id
                        ? <pre className="whitespace-pre-wrap break-all">{JSON.stringify(e.detail, null, 2)}</pre>
                        : <span className="block truncate">{JSON.stringify(e.detail)}</span>}
                    </td>
                  </Row>
                ))}
              </Table>
              <Pagination total={d.total} offset={offset} limit={LIMIT} onChange={(o) => set({ offset: String(o) })} />
            </>
          )}
        </AsyncBlock>
      </Card>
    </>
  );
}
