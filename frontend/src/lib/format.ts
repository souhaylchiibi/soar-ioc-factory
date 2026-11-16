/** Formatting helpers — French locale, UTC-safe, never invent a value. */

const nf = new Intl.NumberFormat("fr-FR");

export const fmtNum = (n: number | null | undefined) => (n === null || n === undefined ? "—" : nf.format(n));

export const fmtPct = (ratio: number | null | undefined, digits = 1) =>
  ratio === null || ratio === undefined ? "—" : `${(ratio * 100).toFixed(digits).replace(".", ",")} %`;

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" }) : "—";

export const fmtShort = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";

export const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });

export function fmtDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "non mesurée";
  if (ms < 1000) return `${ms} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1).replace(".", ",")} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`;
  return `${Math.floor(s / 86400)} j ${Math.round((s % 86400) / 3600)} h`;
}

export function fmtSeconds(s: number | null | undefined): string {
  return s === null || s === undefined ? "—" : fmtDuration(Math.round(s * 1000));
}

const rtf = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });

export function fmtRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "jamais";
  const diff = (new Date(iso).getTime() - now) / 1000;
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export const fmtBytes = (n: number | null | undefined) => {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return `${n} o`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} Ko`;
  return `${(n / 1024 ** 2).toFixed(1)} Mo`;
};
