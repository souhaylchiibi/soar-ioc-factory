import type { ScoreBreakdown as SB } from "../../lib/api";
import { DECISION_META } from "../../lib/meta";
import { Badge } from "../ui/Badge";

/** Explainable score: every component with its points and justification. */
export function ScoreBreakdownView({ breakdown }: { breakdown: SB }) {
  const decision = DECISION_META[breakdown.decision] ?? { label: breakdown.decision, tone: "neutral" as const, rule: "" };
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="num text-[34px] font-semibold leading-none">
            {breakdown.final_score}<span className="text-[16px] font-normal text-fg-subtle"> / 100</span>
          </div>
          <div className="mt-1.5 text-[12px] text-fg-subtle">Politique {breakdown.policy_version}</div>
        </div>
        <div className="text-right">
          <Badge tone={decision.tone} dot>Décision : {decision.label}</Badge>
          {decision.rule && <div className="mt-1 text-[11.5px] text-fg-subtle">Règle appliquée : {decision.rule}</div>}
        </div>
      </div>
      <ul className="space-y-3">
        {breakdown.components.map((c) => {
          const pct = c.max_points ? Math.max(0, Math.min(100, (c.points / c.max_points) * 100)) : 0;
          return (
            <li key={c.key}>
              <div className="flex items-baseline justify-between gap-3 text-[13px]">
                <span className="font-medium">{c.label}</span>
                <span className="num font-mono text-[12px] text-fg-muted">+{Number(c.points.toFixed(1))} / {c.max_points}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3"
                role="meter" aria-valuemin={0} aria-valuemax={c.max_points} aria-valuenow={c.points} aria-label={c.label}>
                <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
              </div>
              <p className="mt-1 text-[12px] text-fg-muted">{c.explanation}</p>
            </li>
          );
        })}
        {breakdown.penalties.map((p) => (
          <li key={p.key} className="rounded-md border border-danger/30 bg-danger/8 px-3 py-2.5">
            <div className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="font-medium text-danger">{p.label}</span>
              <span className="num font-mono text-[12px] text-danger">{p.points}</span>
            </div>
            <p className="mt-0.5 text-[12px] text-fg-muted">{p.explanation}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
