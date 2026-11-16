import { useSearchParams, useNavigate } from "react-router-dom";
import { Download } from "lucide-react";
import { api, type Ioc } from "../lib/api";
import { fmtNum, fmtRelative, fmtShort } from "../lib/format";
import { RISK_META, RISK_ORDER, STATUS_META, TYPE_META } from "../lib/meta";
import { useApi, useDebounced } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { ClearButton, SearchInput, Select, Toggle } from "../components/ui/Controls";
import { Pagination, Row, Table, type Column } from "../components/ui/Table";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { RiskBadge, StatusBadge, SyntheticTag, TypeTag } from "../components/ui/Badge";

const LIMIT = 50;
const SORTS: Record<string, [string, string]> = {
  value: ["value_asc", "value_desc"],
  score: ["score_asc", "score_desc"],
  last_seen: ["last_seen_asc", "last_seen_desc"],
  expires: ["expires_asc", "expires_desc"],
};

const COLUMNS: Column[] = [
  { key: "value", label: "Indicateur", sortable: true },
  { key: "type", label: "Type" },
  { key: "status", label: "Statut" },
  { key: "score", label: "Score", sortable: true, align: "right" },
  { key: "risk", label: "Risque" },
  { key: "sources", label: "Sources", align: "center" },
  { key: "detections", label: "Détections", align: "center" },
  { key: "last_seen", label: "Vu", sortable: true },
  { key: "expires", label: "Expiration", sortable: true },
];

function csv(items: Ioc[]): string {
  const head = ["value", "type", "status", "score", "risk_level", "independent_sources", "detections", "first_seen_at", "last_seen_at", "expires_at", "is_synthetic"];
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [head.join(","), ...items.map((i) => [i.value, i.type, i.status, i.score, i.risk_level, i.independent_source_count, i.detection_count, i.first_seen_at, i.last_seen_at, i.expires_at, i.is_synthetic].map(esc).join(","))].join("\n");
}

export default function ThreatIntel() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const status = params.get("status") ?? "";
  const type = params.get("type") ?? "";
  const risk = params.get("risk") ?? "";
  const qRaw = params.get("q") ?? "";
  const hideLab = params.get("lab") === "0";
  const sort = params.get("sort") ?? "last_seen_desc";
  const offset = Number(params.get("offset") ?? 0);
  const q = useDebounced(qRaw, 300);

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v === null || v === "" ? next.delete(k) : next.set(k, v));
    if (!("offset" in patch)) next.delete("offset");
    setParams(next, { replace: true });
  };

  const qs = new URLSearchParams({ limit: String(LIMIT), offset: String(offset), sort });
  if (status) qs.set("status", status);
  if (type) qs.set("type", type);
  if (risk) qs.set("risk", risk);
  if (q) qs.set("q", q);
  if (hideLab) qs.set("synthetic", "false");
  const state = useApi(() => api.iocs(`?${qs}`), [qs.toString()]);

  const sortKey = Object.entries(SORTS).find(([, v]) => v.includes(sort));
  const onSort = (key: string) => {
    const [asc, desc] = SORTS[key];
    set({ sort: sort === desc ? asc : desc });
  };

  const exportCsv = () => {
    if (!state.data) return;
    const blob = new Blob([csv(state.data.items)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `iocs-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const filtered = !!(status || type || risk || qRaw || hideLab);

  return (
    <>
      <PageHeader
        title="Threat Intelligence"
        description="Inventaire des indicateurs : provenance, score, cycle de vie et détections. Cliquez une ligne pour ouvrir le dossier de preuve de l'IOC."
        updatedAt={state.updatedAt}
        onRefresh={state.refresh}
        actions={<button type="button" className="btn-secondary h-8" onClick={exportCsv} disabled={!state.data?.items.length}><Download size={14} aria-hidden /> Export CSV (page)</button>}
      />

      <Card bodyClass="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <SearchInput label="Recherche" value={qRaw} onChange={(v) => set({ q: v })} placeholder="IP, domaine, URL, hachage…" />
          <Select label="Statut" value={status} onChange={(v) => set({ status: v })}
            options={[{ value: "", label: "Tous les statuts" }, ...Object.entries(STATUS_META).map(([k, m]) => ({ value: k, label: m.label }))]} />
          <Select label="Type" value={type} onChange={(v) => set({ type: v })} className="w-36"
            options={[{ value: "", label: "Tous les types" }, ...Object.entries(TYPE_META).map(([k, m]) => ({ value: k, label: m.label }))]} />
          <Select label="Risque" value={risk} onChange={(v) => set({ risk: v })} className="w-36"
            options={[{ value: "", label: "Tous niveaux" }, ...RISK_ORDER.map((r) => ({ value: r, label: RISK_META[r].label }))]} />
          <Toggle label="Masquer les données de labo" checked={hideLab} onChange={(v) => set({ lab: v ? "0" : null })} />
          {filtered && <ClearButton onClick={() => setParams({}, { replace: true })} />}
        </div>
      </Card>

      <Card className="mt-4" bodyClass=""
        title={state.data ? `${fmtNum(state.data.total)} indicateur(s)` : "Indicateurs"}
        subtitle={filtered ? "Filtres actifs — l'URL de cette vue est partageable" : "Tri par défaut : dernière observation"}>
        <AsyncBlock state={state} rows={10}>
          {(d) => d.items.length === 0 ? (
            <EmptyState title="Aucun IOC ne correspond">{filtered ? "Modifiez ou effacez les filtres." : "L'inventaire est vide : lancez une collecte depuis l'Automation Center."}</EmptyState>
          ) : (
            <>
              <Table columns={COLUMNS} caption="Inventaire des IOC" minWidth={1040}
                sort={sortKey ? { key: sortKey[0], dir: sort.endsWith("asc") ? "asc" : "desc" } : undefined} onSort={onSort}>
                {d.items.map((i) => (
                  <Row key={i.id} onClick={() => navigate(`/iocs/${i.id}`)}>
                    <td className="td max-w-[380px]">
                      <a href={`/iocs/${i.id}`} onClick={(e) => { e.preventDefault(); navigate(`/iocs/${i.id}`); }}
                        className="flex items-center gap-2 font-mono text-[12.5px] text-fg hover:text-accent-strong">
                        <span className="truncate" title={i.value}>{i.value}</span>
                        {i.is_synthetic && <SyntheticTag />}
                      </a>
                    </td>
                    <td className="td"><TypeTag type={i.type} /></td>
                    <td className="td"><StatusBadge status={i.status} /></td>
                    <td className="td num text-right font-medium">{i.score ?? <span className="text-fg-subtle">—</span>}</td>
                    <td className="td"><RiskBadge risk={i.risk_level} /></td>
                    <td className="td num text-center">{i.independent_source_count}</td>
                    <td className="td num text-center">{i.detection_count ? <span className="font-semibold text-risk-high">{i.detection_count}</span> : <span className="text-fg-subtle">0</span>}</td>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtShort(i.last_seen_at)}>{fmtRelative(i.last_seen_at)}</td>
                    <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtShort(i.expires_at)}>{i.expires_at ? fmtRelative(i.expires_at) : "—"}</td>
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
