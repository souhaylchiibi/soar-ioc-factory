import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Boxes, CornerDownLeft, Search } from "lucide-react";
import { api } from "../../lib/api";
import { useApi, useDebounced } from "../../lib/useApi";
import { RiskBadge, StatusBadge, SyntheticTag, TypeTag } from "../ui/Badge";

/**
 * Topbar search (Ctrl/⌘+K). Queries /search — IOC values and sources —
 * and navigates with the keyboard (↑ ↓ Entrée, Échap).
 */
export function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const dq = useDebounced(q.trim(), 250);
  const res = useApi(() => api.search(dq), [dq], { enabled: dq.length >= 2 });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    const onDown = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, []);

  const results = [
    ...(res.data?.iocs ?? []).map((i) => ({ key: i.id, to: `/iocs/${i.id}`, kind: "ioc" as const, ioc: i })),
    ...(res.data?.sources ?? []).map((s) => ({ key: `src-${s.name}`, to: `/sources?focus=${encodeURIComponent(s.name)}`, kind: "source" as const, name: s.name })),
  ];
  const go = (to: string) => { setOpen(false); setQ(""); navigate(to); };
  const showPanel = open && dq.length >= 2;

  return (
    <div ref={boxRef} className="relative w-full max-w-[460px]">
      <Search size={15} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-expanded={showPanel}
        aria-controls="global-search-results"
        aria-label="Recherche globale (IOC, sources)"
        placeholder="Rechercher un IOC, une source…"
        value={q}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter") {
            if (results[active]) go(results[active].to);
            else if (dq.length >= 2) go(`/threat-intel?q=${encodeURIComponent(dq)}`);
          }
          if (e.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
        }}
        className="input h-9 bg-surface-2 pl-9 pr-14 font-sans"
        autoComplete="off"
        spellCheck={false}
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-line-strong px-1.5 py-0.5 font-mono text-[10.5px] text-fg-subtle sm:block">Ctrl K</kbd>

      {showPanel && (
        <div id="global-search-results" role="listbox"
          className="absolute left-0 right-0 top-11 z-50 max-h-[420px] overflow-y-auto rounded-lg border border-line-strong bg-surface-2 p-1.5 shadow-xl shadow-black/50">
          {res.loading && !res.data && <p className="px-3 py-3 text-[12.5px] text-fg-muted">Recherche…</p>}
          {res.error ? <p className="px-3 py-3 text-[12.5px] text-danger">Recherche indisponible : {(res.error as Error).message}</p> : null}
          {res.data && results.length === 0 && (
            <p className="px-3 py-3 text-[12.5px] text-fg-muted">Aucun IOC ni source ne correspond à « {dq} ».</p>
          )}
          {results.map((r, i) => (
            <button key={r.key} type="button" role="option" aria-selected={i === active}
              onMouseEnter={() => setActive(i)} onClick={() => go(r.to)}
              className={`flex w-full cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-left ${i === active ? "bg-surface-3" : ""}`}>
              {r.kind === "ioc" ? (
                <>
                  <TypeTag type={r.ioc.type} />
                  <span className="min-w-0 flex-1 truncate font-mono text-[12.5px]">{r.ioc.value}</span>
                  {r.ioc.is_synthetic && <SyntheticTag />}
                  <RiskBadge risk={r.ioc.risk_level} />
                  <StatusBadge status={r.ioc.status} />
                </>
              ) : (
                <>
                  <Boxes size={15} className="text-fg-subtle" aria-hidden />
                  <span className="flex-1 text-[13px]">Source · {r.name}</span>
                </>
              )}
            </button>
          ))}
          {dq.length >= 2 && (
            <button type="button" onClick={() => go(`/threat-intel?q=${encodeURIComponent(dq)}`)}
              className="mt-1 flex w-full cursor-pointer items-center gap-2 border-t border-line px-3 pt-2.5 pb-1.5 text-[12px] text-fg-muted hover:text-fg">
              <CornerDownLeft size={13} aria-hidden /> Voir tous les résultats dans Threat Intelligence
            </button>
          )}
        </div>
      )}
    </div>
  );
}
