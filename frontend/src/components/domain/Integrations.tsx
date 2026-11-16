import { Bot, Database, FileSearch, Network, Radar, Share2, ShieldCheck, type LucideIcon } from "lucide-react";
import type { IntegrationItem } from "../../lib/api";
import { fmtBytes, fmtRelative } from "../../lib/format";
import { CONN_META, toneDot } from "../../lib/meta";
import { ConnBadge } from "../ui/Badge";

const META: Record<string, { label: string; icon: LucideIcon; role: string }> = {
  postgresql: { label: "PostgreSQL", icon: Database, role: "Base de données" },
  n8n: { label: "n8n", icon: Bot, role: "Orchestration" },
  collectors: { label: "Collecteurs", icon: Network, role: "Threat Intelligence" },
  enrichment: { label: "Enrichissement", icon: FileSearch, role: "OTX · AbuseIPDB" },
  misp: { label: "MISP", icon: Share2, role: "Publication" },
  suricata: { label: "Suricata", icon: Radar, role: "IDS réseau" },
  wazuh: { label: "Wazuh", icon: ShieldCheck, role: "SIEM / HIDS" },
};

export const integrationLabel = (n: string) => META[n]?.label ?? n;

/** Compact strip for the overview: one dot per integration. */
export function IntegrationStrip({ items }: { items: IntegrationItem[] }) {
  return (
    <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4 xl:grid-cols-7">
      {items.map((it) => {
        const m = META[it.name] ?? { label: it.name, icon: Database, role: it.kind };
        const tone = CONN_META[it.status]?.tone ?? "neutral";
        return (
          <li key={it.name} className="flex items-center gap-3 bg-surface px-3.5 py-3" title={it.detail}>
            <m.icon size={17} className="shrink-0 text-fg-subtle" aria-hidden />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-[12.5px] font-medium">
                <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${toneDot[tone]}`} />
                {m.label}
              </div>
              <div className="truncate text-[11.5px] text-fg-subtle">{CONN_META[it.status]?.label ?? it.status}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Detailed cards for System Health. */
export function IntegrationCard({ item }: { item: IntegrationItem }) {
  const m = META[item.name] ?? { label: item.name, icon: Database, role: item.kind };
  return (
    <article className="card flex flex-col gap-3 p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-surface-3 text-fg-muted"><m.icon size={18} aria-hidden /></div>
          <div>
            <h3 className="text-[13.5px] font-semibold">{m.label}</h3>
            <p className="text-[11.5px] text-fg-subtle">{m.role}</p>
          </div>
        </div>
        <ConnBadge state={item.status} />
      </header>
      {item.detail && <p className="text-[12.5px] text-fg-muted">{item.detail}</p>}
      <dl className="space-y-1 text-[12px]">
        {item.url && <Meta k="Point d'accès" v={<span className="font-mono">{item.url}</span>} />}
        {item.file && <Meta k="Fichier" v={<span className="font-mono">{item.file}</span>} />}
        {item.file_size !== undefined && <Meta k="Taille" v={fmtBytes(item.file_size)} />}
        {item.file_modified_at && <Meta k="Modifié" v={fmtRelative(item.file_modified_at)} />}
        {"last_ingest_at" in item && <Meta k="Dernière ingestion" v={fmtRelative(item.last_ingest_at)} />}
        {"last_workflow_activity_at" in item && <Meta k="Dernière exécution workflow" v={fmtRelative(item.last_workflow_activity_at)} />}
      </dl>
      {item.providers && (
        <ul className="space-y-1.5 border-t border-line pt-3">
          {item.providers.map((p) => (
            <li key={p.name} className="flex items-center justify-between gap-3 text-[12px]">
              <span>{p.name}</span><span className="text-fg-subtle">{p.detail}</span>
            </li>
          ))}
        </ul>
      )}
      {item.sources && (
        <ul className="space-y-1.5 border-t border-line pt-3">
          {item.sources.map((s) => (
            <li key={s.name} className="flex items-center justify-between gap-3 text-[12px]">
              <span className="font-mono">{s.name}</span>
              <ConnBadge state={s.status} />
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Meta({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-fg-subtle">{k}</dt>
      <dd className="min-w-0 truncate text-right text-fg-muted">{v}</dd>
    </div>
  );
}
