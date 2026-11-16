import { CheckCircle2, ChevronRight } from "lucide-react";
import type { FunnelStage } from "../../lib/api";
import { fmtNum } from "../../lib/format";

/**
 * The ten stages of the IOC factory, left to right. Each stage shows its
 * measured throughput and, on hover, the SQL proof behind the figure.
 */
export function Pipeline({ stages, verifiedRemovals }: { stages: FunnelStage[]; verifiedRemovals?: number }) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5 2xl:grid-cols-10" aria-label="Étapes du cycle de vie des IOC">
      {stages.map((s, i) => (
        <li key={s.key} className="relative" title={`Preuve : ${s.proof}`}>
          <div className={`flex h-full flex-col justify-between rounded-lg border px-3 py-2.5 ${s.count > 0 ? "border-line-strong bg-surface-2" : "border-line bg-surface"}`}>
            <div className="flex items-center gap-1.5">
              <span className="num grid h-5 w-5 shrink-0 place-items-center rounded-full bg-surface-3 text-[10.5px] font-semibold text-fg-muted">{i + 1}</span>
              <span className="truncate text-[12px] font-medium text-fg-muted">{s.label}</span>
            </div>
            <div className="num mt-2 text-[20px] font-semibold leading-none">{fmtNum(s.count)}</div>
            <div className="mt-1 text-[11px] text-fg-subtle">
              {s.current !== null ? <>actuellement <span className="num text-fg-muted">{fmtNum(s.current)}</span></> : "opérations tracées"}
            </div>
            {s.key === "remove" && verifiedRemovals !== undefined && (
              <div className="mt-1 flex items-center gap-1 text-[11px] text-ok">
                <CheckCircle2 size={12} aria-hidden /> {fmtNum(verifiedRemovals)} vérifié(s)
              </div>
            )}
          </div>
          {i < stages.length - 1 && (
            <ChevronRight size={14} aria-hidden className="absolute -right-[11px] top-1/2 z-[1] hidden -translate-y-1/2 text-fg-subtle 2xl:block" />
          )}
        </li>
      ))}
    </ol>
  );
}
