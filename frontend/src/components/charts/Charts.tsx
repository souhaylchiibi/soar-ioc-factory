import { Area, Bar, CartesianGrid, ComposedChart, Legend, Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { fmtDay, fmtNum } from "../../lib/format";

/** Shared tooltip: dark surface, tabular numbers, series colour + label. */
function ChartTooltip({ active, payload, label, labelFormatter }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line-strong bg-surface-2 px-3 py-2 text-[12px] shadow-lg shadow-black/40">
      {label !== undefined && <div className="mb-1 font-medium text-fg">{labelFormatter ? labelFormatter(label) : label}</div>}
      {payload.map((p: any) => (
        <div key={p.dataKey ?? p.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-fg-muted">
            <span aria-hidden className="h-2 w-2 rounded-sm" style={{ background: p.color ?? p.payload?.fill }} />
            {p.name}
          </span>
          <span className="num font-medium text-fg">{fmtNum(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

const legendStyle = { fontSize: 12, color: "var(--color-fg-muted)", paddingTop: 8 };

export interface TimelinePoint {
  date: string;
  created: number;
  published: number;
  monitored: number;
  rejected: number;
  expired: number;
  detections: number;
}

/** IOC activity over time: intake (area) vs. decisions (stacked bars). */
export function TimelineChart({ data, height = 260 }: { data: TimelinePoint[]; height?: number }) {
  return (
    <div role="img" aria-label="Évolution quotidienne des IOC : créés, publiés, surveillés, rejetés, détections">
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -6, bottom: 0 }}>
          <defs>
            <linearGradient id="g-created" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5aa2f5" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#5aa2f5" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="3 4" />
          <XAxis dataKey="date" tickFormatter={fmtDay} tickLine={false} axisLine={false} minTickGap={22} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTooltip labelFormatter={(d: string) => new Date(`${d}T00:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "short" })} />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Legend wrapperStyle={legendStyle} iconType="square" iconSize={9} />
          <Area type="monotone" dataKey="created" name="Créés" stroke="#5aa2f5" strokeWidth={1.8} fill="url(#g-created)" isAnimationActive={false} />
          <Bar dataKey="published" name="Publiés" stackId="d" fill="#4cc38a" maxBarSize={14} isAnimationActive={false} />
          <Bar dataKey="monitored" name="Surveillés" stackId="d" fill="#2cc2a6" fillOpacity={0.55} maxBarSize={14} isAnimationActive={false} />
          <Bar dataKey="rejected" name="Rejetés" stackId="d" fill="#7d8ba0" fillOpacity={0.7} maxBarSize={14} radius={[2, 2, 0, 0]} isAnimationActive={false} />
          <Line type="monotone" dataKey="detections" name="Détections" stroke="#ee8a3c" strokeWidth={1.6} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut with a centred total and an accessible legend list. */
export function Donut({ data, total, label, height = 200 }: {
  data: { name: string; value: number; color: string }[];
  total: number;
  label: string;
  height?: number;
}) {
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative shrink-0" style={{ width: height, height }} role="img" aria-label={`${label} : ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="68%" outerRadius="96%" paddingAngle={data.length > 1 ? 2 : 0} stroke="none" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="num text-[22px] font-semibold leading-none">{fmtNum(total)}</div>
            <div className="mt-1 text-[11px] text-fg-subtle">{label}</div>
          </div>
        </div>
      </div>
      <ul className="w-full space-y-1.5 text-[12.5px]">
        {data.map((d) => (
          <li key={d.name} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-fg-muted"><span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: d.color }} />{d.name}</span>
            <span className="num font-medium">{fmtNum(d.value)}<span className="ml-2 text-fg-subtle">{total ? Math.round((d.value / total) * 100) : 0} %</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Horizontal bars in plain HTML: crisp, accessible, no chart lib needed. */
export function BarList({ items, max, unit = "" }: { items: { label: string; value: number; color?: string; hint?: string }[]; max?: number; unit?: string }) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2.5">
      {items.map((i) => (
        <li key={i.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[12.5px]">
            <span className="truncate text-fg-muted" title={i.hint}>{i.label}</span>
            <span className="num shrink-0 font-medium">{fmtNum(i.value)}{unit}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
            <div className="h-full rounded-full" style={{ width: `${(i.value / top) * 100}%`, background: i.color ?? "var(--color-accent)" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Score histogram with decision thresholds marked. */
export function ScoreHistogram({ buckets }: { buckets: Record<string, number> }) {
  const colors: Record<string, string> = { "0-49": "#7d8ba0", "50-64": "#5aa2f5", "65-79": "#e0b33b", "80-89": "#ee8a3c", "90-100": "#f0605d" };
  const data = Object.entries(buckets).map(([range, count]) => ({ range, count, fill: colors[range] ?? "#5aa2f5" }));
  return (
    <div role="img" aria-label={`Distribution des scores : ${data.map((d) => `${d.range} ${d.count}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -6, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 4" />
          <XAxis dataKey="range" tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Bar dataKey="count" name="IOC" maxBarSize={56} radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.range} fill={d.fill} />)}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Score evolution of one IOC. */
export function ScoreLine({ data }: { data: { computed_at: string; score: number }[] }) {
  const points = data.map((d) => ({ t: new Date(d.computed_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }), score: d.score }));
  return (
    <div role="img" aria-label={`Historique du score : ${points.map((p) => p.score).join(", ")}`}>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={points} margin={{ top: 8, right: 8, left: -6, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 4" />
          <XAxis dataKey="t" tickLine={false} axisLine={false} minTickGap={30} />
          <YAxis domain={[0, 100]} ticks={[0, 50, 80, 100]} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="stepAfter" dataKey="score" name="Score" stroke="#2cc2a6" strokeWidth={2} dot={{ r: 3, fill: "#2cc2a6" }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
