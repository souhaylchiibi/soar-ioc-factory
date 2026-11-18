import { NavLink } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useAuth } from "../../lib/auth";
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { NAV_GROUPS } from "./nav";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden className="shrink-0">
        <rect x="1" y="1" width="26" height="26" rx="7" fill="#10151c" stroke="#2e3948" />
        <path d="M8 18.5 14 7l6 11.5" fill="none" stroke="#2cc2a6" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="14" cy="19.5" r="2" fill="#e7ecf2" />
      </svg>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[13.5px] font-semibold tracking-tight">SOAR IOC Factory</div>
          <div className="text-[11px] text-fg-subtle">Threat Intel Console</div>
        </div>
      )}
    </div>
  );
}

export function Sidebar({ collapsed, onToggle, mobileOpen, onCloseMobile }: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const { can } = useAuth();
  const live = useApi(api.liveness, [], { pollMs: 20000 });
  const apiUp = live.data?.status === "ok" && !live.error;

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onCloseMobile} aria-hidden />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-line bg-surface transition-[width,transform] duration-200
          ${collapsed ? "lg:w-[64px]" : "lg:w-[236px]"} w-[260px]
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}
      >
        <div className={`flex h-14 items-center border-b border-line ${collapsed ? "lg:justify-center" : "justify-between"} px-4`}>
          <div className={collapsed ? "lg:hidden" : ""}><BrandMark /></div>
          {collapsed && <div className="hidden lg:block"><BrandMark compact /></div>}
          <button type="button" onClick={onCloseMobile} className="icon-btn lg:hidden" aria-label="Fermer le menu"><X size={18} /></button>
        </div>

        <nav aria-label="Navigation principale" className="flex-1 overflow-y-auto px-2.5 py-3">
          {NAV_GROUPS.map((g) => {
            const items = g.items.filter((i) => !i.minRole || can(i.minRole));
            if (!items.length) return null;
            return (
              <div key={g.label} className="mb-4">
                <div className={`eyebrow mb-1.5 px-2.5 ${collapsed ? "lg:sr-only" : ""}`}>{g.label}</div>
                <ul className="space-y-0.5">
                  {items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.to === "/"}
                        onClick={onCloseMobile}
                        title={collapsed ? item.label : undefined}
                        className={({ isActive }) =>
                          `group relative flex h-9 items-center gap-3 rounded-md px-2.5 text-[13px] font-medium transition-colors
                          ${collapsed ? "lg:justify-center lg:px-0" : ""}
                          ${isActive ? "bg-surface-3 text-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg"}`
                        }
                      >
                        {({ isActive }) => (
                          <>
                            {isActive && <span aria-hidden className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-accent" />}
                            <item.icon size={17} aria-hidden className={isActive ? "text-accent-strong" : ""} />
                            <span className={collapsed ? "lg:sr-only" : ""}>{item.label}</span>
                          </>
                        )}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-line p-2.5">
          <div className={`flex items-center gap-2 px-2.5 py-1.5 text-[11.5px] text-fg-muted ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
            title={apiUp ? "API joignable" : "API injoignable"}>
            <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${live.loading && !live.data ? "bg-fg-subtle" : apiUp ? "bg-ok" : "bg-danger"}`} />
            <span className={collapsed ? "lg:sr-only" : ""}>{live.loading && !live.data ? "Vérification API…" : apiUp ? "API opérationnelle" : "API injoignable"}</span>
          </div>
          <button type="button" onClick={onToggle}
            className={`hidden h-9 w-full items-center gap-3 rounded-md px-2.5 text-[12.5px] text-fg-muted hover:bg-surface-2 hover:text-fg lg:flex ${collapsed ? "justify-center px-0" : ""}`}
            aria-label={collapsed ? "Déplier la barre latérale" : "Replier la barre latérale"}>
            {collapsed ? <PanelLeftOpen size={17} /> : <><PanelLeftClose size={17} /> Replier</>}
          </button>
        </div>
      </aside>
    </>
  );
}
