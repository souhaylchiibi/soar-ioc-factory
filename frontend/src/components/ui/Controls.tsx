import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Search, X } from "lucide-react";

export function Field({ label, children, className = "" }: { label: string; children: (id: string) => ReactNode; className?: string }) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-[11.5px] font-medium text-fg-muted">{label}</label>
      {children(id)}
    </div>
  );
}

export function Select({ label, value, onChange, options, className = "w-44" }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <Field label={label} className={className}>
      {(id) => (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="input cursor-pointer pr-8">
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
    </Field>
  );
}

export function SearchInput({ label, value, onChange, placeholder, className = "min-w-[240px] flex-1" }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; className?: string;
}) {
  return (
    <Field label={label} className={className}>
      {(id) => (
        <div className="relative">
          <Search size={15} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
          <input id={id} type="search" value={value} onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder} className="input pl-9 font-mono" autoComplete="off" spellCheck={false} />
        </div>
      )}
    </Field>
  );
}

export function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="inline-flex h-9 cursor-pointer select-none items-center gap-2 text-[12.5px] text-fg-muted">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span aria-hidden className="relative h-5 w-9 rounded-full bg-surface-3 ring-1 ring-line-strong transition-colors peer-checked:bg-accent/70 peer-focus-visible:outline-2 peer-focus-visible:outline-accent
        after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-fg after:transition-transform peer-checked:after:translate-x-4" />
      {label}
    </label>
  );
}

/** Segmented tabs (keyboard: arrows move between tabs). */
export function Tabs<T extends string>({ value, onChange, items, label }: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: string; count?: number }[];
  label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const next = (i + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    refs.current[next]?.focus();
    onChange(items[next].value);
  };
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line">
      {items.map((it, i) => {
        const active = it.value === value;
        return (
          <button key={it.value} ref={(el) => { refs.current[i] = el; }} role="tab" type="button"
            aria-selected={active} tabIndex={active ? 0 : -1}
            onKeyDown={(e) => onKey(e, i)} onClick={() => onChange(it.value)}
            className={`-mb-px inline-flex cursor-pointer items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-medium transition-colors
              ${active ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg"}`}>
            {it.label}
            {it.count !== undefined && (
              <span className={`num rounded px-1.5 text-[11px] ${active ? "bg-accent/15 text-accent-strong" : "bg-surface-3 text-fg-subtle"}`}>{it.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Lightweight popover menu with outside-click + Escape handling. */
export function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return { open, setOpen, ref };
}

export function ClearButton({ onClick, label = "Effacer les filtres" }: { onClick: () => void; label?: string }) {
  return (
    <button type="button" onClick={onClick} className="btn-ghost h-9 self-end">
      <X size={14} aria-hidden /> {label}
    </button>
  );
}
