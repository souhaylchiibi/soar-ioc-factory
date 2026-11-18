import type { ReactNode } from "react";
import type { ConnState, IocStatus, IocType, RiskLevel } from "../../lib/api";
import { CONN_META, RISK_META, SEVERITY_META, STATUS_META, TYPE_META, toneClasses, toneDot, type Tone } from "../../lib/meta";

export function Badge({ tone = "neutral", children, dot = false, title }: { tone?: Tone; children: ReactNode; dot?: boolean; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex h-[22px] items-center gap-1.5 whitespace-nowrap rounded-[5px] px-2 text-[11.5px] font-medium ring-1 ring-inset ${toneClasses[tone]}`}
    >
      {dot && <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${toneDot[tone]}`} />}
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: IocStatus }) {
  const m = STATUS_META[status] ?? { label: status, tone: "neutral" as Tone, hint: "" };
  return <Badge tone={m.tone} dot title={m.hint}>{m.label}</Badge>;
}

/** Risk is shown with a coloured bar + text: never colour alone (WCAG 1.4.1). */
export function RiskBadge({ risk }: { risk: RiskLevel | null }) {
  if (!risk) return <span className="text-fg-subtle text-[12px]">non évalué</span>;
  const m = RISK_META[risk];
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium" style={{ color: m.color }}>
      <span aria-hidden className="h-3 w-[3px] rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return <span className="text-fg-subtle text-[12px]" title="Le capteur n'a fourni aucune sévérité">non fournie</span>;
  const m = SEVERITY_META[severity];
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium" style={{ color: m.color }}>
      <span aria-hidden className="h-3 w-[3px] rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

export function TypeTag({ type }: { type: IocType }) {
  const m = TYPE_META[type];
  return (
    <span className="inline-flex h-[20px] items-center rounded border border-line px-1.5 font-mono text-[10.5px] font-medium text-fg-muted">
      <span aria-hidden className="mr-1.5 h-1.5 w-1.5 rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

export function ConnBadge({ state }: { state: ConnState }) {
  const m = CONN_META[state] ?? CONN_META.no_data;
  return <Badge tone={m.tone} dot>{m.label}</Badge>;
}

export function SyntheticTag() {
  return (
    <Badge tone="warn" title="Donnée synthétique de laboratoire — jamais comptée comme renseignement réel">
      LAB
    </Badge>
  );
}
