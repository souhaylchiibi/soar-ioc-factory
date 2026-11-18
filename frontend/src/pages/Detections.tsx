import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Check, ShieldOff } from "lucide-react";
import { api, type DetectionItem } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtNum, fmtRelative } from "../lib/format";
import { useApi, useDebounced } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, DefList } from "../components/ui/Card";
import { Kpi, KpiGrid } from "../components/ui/Kpi";
import { ClearButton, SearchInput, Select } from "../components/ui/Controls";
import { AsyncBlock, EmptyState } from "../components/ui/States";
import { Badge, RiskBadge, SeverityBadge, StatusBadge, SyntheticTag, TypeTag } from "../components/ui/Badge";
import { Pagination, Row, Table } from "../components/ui/Table";
import { ConfirmDialog, useToast } from "../components/ui/Feedback";
import { OperationButton } from "../components/domain/OperationButton";

const LIMIT = 50;
const TRIAGE = {
  pending: { label: "À qualifier", tone: "warn" as const },
  confirmed: { label: "Confirmée", tone: "danger" as const },
  false_positive: { label: "Faux positif", tone: "neutral" as const },
};

export default function Detections() {
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const toast = useToast();
  const sensor = params.get("sensor") ?? "";
  const triage = params.get("triage") ?? "";
  const qRaw = params.get("q") ?? "";
  const offset = Number(params.get("offset") ?? 0);
  const q = useDebounced(qRaw, 300);
  const [selected, setSelected] = useState<DetectionItem | null>(null);
  const [verdict, setVerdict] = useState<"confirmed" | "false_positive" | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    if (!("offset" in patch)) next.delete("offset");
    setParams(next, { replace: true });
  };
  const qs = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
  if (sensor) qs.set("sensor", sensor);
  if (triage) qs.set("triage", triage);
  if (q) qs.set("q", q);
  const state = useApi(() => api.detections(`?${qs}`), [qs.toString()], { pollMs: 30000 });

  const review = async () => {
    if (!selected || !verdict) return;
    setBusy(true);
    try {
      const updated = await api.reviewDetection(selected.id, verdict, note.trim() || undefined);
      toast({ kind: "success", title: `Détection qualifiée : ${TRIAGE[updated.triage].label}`, message: verdict === "false_positive" ? "Le compteur de faux positifs de l'IOC est mis à jour (pénalité au prochain scoring)." : undefined });
      setSelected(updated);
      setVerdict(null);
      setNote("");
      state.refresh();
    } catch (e) {
      toast({ kind: "error", title: "Qualification refusée", message: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const d = state.data;
  return (
    <>
      <PageHeader
        title="Detection Center"
        description="Alertes des capteurs rapprochées de l'inventaire. La sévérité est celle déclarée par le capteur ; l'alerte d'origine est conservée comme preuve."
        updatedAt={state.updatedAt}
        onRefresh={state.refresh}
        actions={<>
          <OperationButton path="/iocs/detections/ingest?sensor=suricata" label="Ingérer Suricata" onDone={state.refresh}
            description="Lit eve.json (montage capteur en lecture seule) et rapproche chaque alerte des IOC suivis. Si le fichier est absent, l'API répond « no_file » sans rien inventer." />
          <OperationButton path="/iocs/detections/ingest?sensor=wazuh" label="Ingérer Wazuh" onDone={state.refresh}
            description="Lit alerts.json de Wazuh et rapproche les adresses source des IOC suivis." />
        </>}
      />

      {d && (
        <KpiGrid cols="grid-cols-2 md:grid-cols-5">
          <Kpi label="Détections" value={fmtNum(Object.values(d.by_sensor).reduce((a, b) => a + b, 0))} tone="var(--color-risk-high)" />
          <Kpi label="À qualifier" value={fmtNum(d.by_triage.pending)} tone="var(--color-warn)" to="/detections?triage=pending" />
          <Kpi label="Confirmées" value={fmtNum(d.by_triage.confirmed)} tone="var(--color-danger)" to="/detections?triage=confirmed" />
          <Kpi label="Faux positifs" value={fmtNum(d.by_triage.false_positive)} to="/detections?triage=false_positive" />
          <Kpi label="Par capteur" value={
            <ul className="space-y-0.5 text-[12.5px] font-medium">
              {Object.entries(d.by_sensor).length ? Object.entries(d.by_sensor).map(([k, v]) => (
                <li key={k} className="flex justify-between gap-3"><span className="text-fg-muted">{k}</span><span className="num">{v}</span></li>
              )) : <li className="text-fg-subtle">aucun</li>}
            </ul>} />
        </KpiGrid>
      )}

      <Card className="mt-4" bodyClass="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <SearchInput label="Recherche" value={qRaw} onChange={(v) => set({ q: v })} placeholder="IOC ou identifiant de règle…" />
          <Select label="Capteur" value={sensor} onChange={(v) => set({ sensor: v })} className="w-40"
            options={[{ value: "", label: "Tous" }, { value: "suricata", label: "Suricata" }, { value: "wazuh", label: "Wazuh" }, { value: "manual", label: "Manuel" }, { value: "misp", label: "MISP" }]} />
          <Select label="Qualification" value={triage} onChange={(v) => set({ triage: v })} className="w-44"
            options={[{ value: "", label: "Toutes" }, ...Object.entries(TRIAGE).map(([k, m]) => ({ value: k, label: m.label }))]} />
          {(sensor || triage || qRaw) && <ClearButton onClick={() => setParams({}, { replace: true })} />}
        </div>
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card bodyClass="">
          <AsyncBlock state={state} rows={10}>
            {(x) => x.items.length === 0 ? (
              <EmptyState title="Aucune détection">
                {sensor || triage || qRaw ? "Aucune alerte ne correspond aux filtres." : "Aucun capteur n'a encore remonté d'alerte correspondant à un IOC suivi. Vérifiez l'état de Suricata et Wazuh dans System Health."}
              </EmptyState>
            ) : (
              <>
                <Table minWidth={900} columns={[{ key: "t", label: "Horodatage" }, { key: "s", label: "Capteur" }, { key: "sev", label: "Sévérité" }, { key: "i", label: "IOC associé" }, { key: "r", label: "Règle / signature" }, { key: "q", label: "Statut" }]}>
                  {x.items.map((det) => (
                    <Row key={det.id} onClick={() => setSelected(det)} selected={selected?.id === det.id}>
                      <td className="td whitespace-nowrap text-[12px] text-fg-muted" title={fmtDate(det.matched_at)}>{fmtRelative(det.matched_at)}</td>
                      <td className="td"><Badge>{det.sensor}</Badge></td>
                      <td className="td"><SeverityBadge severity={det.severity} /></td>
                      <td className="td max-w-[260px]"><span className="flex items-center gap-2"><TypeTag type={det.ioc_type} /><span className="truncate font-mono text-[12.5px]">{det.ioc_value}</span>{det.ioc_synthetic && <SyntheticTag />}</span></td>
                      <td className="td max-w-[260px]"><span className="font-mono text-[12px]">{det.rule_id ?? "—"}</span>{det.signature && <span className="block truncate text-[11.5px] text-fg-subtle">{det.signature}</span>}</td>
                      <td className="td"><Badge tone={TRIAGE[det.triage].tone} dot>{TRIAGE[det.triage].label}</Badge></td>
                    </Row>
                  ))}
                </Table>
                <Pagination total={x.total} offset={offset} limit={LIMIT} onChange={(o) => set({ offset: String(o) })} />
              </>
            )}
          </AsyncBlock>
        </Card>

        <Card title="Détail de l'alerte" subtitle={selected ? fmtDate(selected.matched_at) : "Sélectionnez une détection"}>
          {!selected ? <EmptyState title="Aucune alerte sélectionnée" /> : (
            <div className="space-y-4">
              <DefList items={[
                ["IOC", <Link to={`/iocs/${selected.ioc_id}`} className="font-mono text-[12px] hover:text-accent-strong">{selected.ioc_value}</Link>],
                ["Statut IOC", <StatusBadge status={selected.ioc_status} />],
                ["Risque IOC", <RiskBadge risk={selected.ioc_risk} />],
                ["Capteur", selected.sensor],
                ["Règle", <span className="font-mono">{selected.rule_id ?? "—"}</span>],
                ["Qualification", <Badge tone={TRIAGE[selected.triage].tone}>{TRIAGE[selected.triage].label}</Badge>],
                ...(selected.reviewed_by ? [["Qualifiée par", <span className="font-mono">{selected.reviewed_by}</span>] as [string, React.ReactNode]] : []),
                ...(selected.review_note ? [["Note", selected.review_note] as [string, React.ReactNode]] : []),
              ]} />
              <div>
                <h3 className="eyebrow mb-1.5">Preuve (événement brut conservé)</h3>
                <pre className="max-h-64 overflow-auto rounded-md border border-line bg-bg p-3 font-mono text-[11px] leading-relaxed text-fg-muted">{JSON.stringify(selected.evidence, null, 2)}</pre>
              </div>
              {can("analyst") && (
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary flex-1" onClick={() => setVerdict("confirmed")} disabled={selected.triage === "confirmed"}><Check size={14} aria-hidden /> Confirmer</button>
                  <button type="button" className="btn-secondary flex-1" onClick={() => setVerdict("false_positive")} disabled={selected.triage === "false_positive"}><ShieldOff size={14} aria-hidden /> Faux positif</button>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      <ConfirmDialog open={!!verdict} busy={busy} danger={verdict === "false_positive"}
        title={verdict === "false_positive" ? "Qualifier en faux positif" : "Confirmer la détection"}
        confirmLabel="Enregistrer" onCancel={() => { setVerdict(null); setNote(""); }} onConfirm={review}>
        <p>{verdict === "false_positive"
          ? "L'IOC recevra une pénalité de faux positif lors du prochain calcul de score."
          : "La détection est marquée comme une vraie correspondance."}</p>
        <label htmlFor="note" className="mb-1 mt-3 block text-[12px] font-medium text-fg">Note (facultative)</label>
        <textarea id="note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} className="input h-auto py-2 font-sans" />
      </ConfirmDialog>
    </>
  );
}
