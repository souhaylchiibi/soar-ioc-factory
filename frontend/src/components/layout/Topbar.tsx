import { Fragment, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Bell, ChevronRight, LogOut, Menu, Radar, ShieldAlert, UserRound, XCircle } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtRelative } from "../../lib/format";
import { useApi } from "../../lib/useApi";
import { usePopover } from "../ui/Controls";
import { GlobalSearch } from "./GlobalSearch";
import { ROUTE_LABELS } from "./nav";

const SEEN_KEY = "soar.notifications.seen";

function Breadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  const crumbs = parts.length === 0 ? [{ to: "/", label: ROUTE_LABELS[""] }] : [
    { to: "/", label: "Console" },
    ...parts.map((p, i) => ({
      to: p === "iocs" ? "/threat-intel" : "/" + parts.slice(0, i + 1).join("/"),
      label: ROUTE_LABELS[p] ?? (p.length > 20 ? `${p.slice(0, 8)}…` : p),
    })),
  ];
  return (
    <nav aria-label="Fil d'Ariane" className="hidden min-w-0 items-center gap-1 text-[12.5px] md:flex">
      {crumbs.map((c, i) => (
        <Fragment key={c.to + i}>
          {i > 0 && <ChevronRight size={13} className="shrink-0 text-fg-subtle" aria-hidden />}
          {i === crumbs.length - 1 ? (
            <span aria-current="page" className="truncate font-medium text-fg">{c.label}</span>
          ) : (
            <Link to={c.to} className="truncate text-fg-muted hover:text-fg">{c.label}</Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}

function Notifications() {
  const pop = usePopover();
  const navigate = useNavigate();
  const { data, error } = useApi(api.notifications, [], { pollMs: 60000 });
  const [seen, setSeen] = useState(() => localStorage.getItem(SEEN_KEY) ?? "");
  const unread = useMemo(() => (data?.items ?? []).filter((n) => n.occurred_at > seen).length, [data, seen]);
  const icons = { failure: XCircle, detection: Radar, review: ShieldAlert };
  const tones = { failure: "text-danger", detection: "text-risk-high", review: "text-warn" };

  const markRead = () => {
    const latest = data?.items[0]?.occurred_at ?? new Date().toISOString();
    localStorage.setItem(SEEN_KEY, latest);
    setSeen(latest);
  };

  return (
    <div ref={pop.ref} className="relative">
      <button type="button" className="icon-btn relative" aria-haspopup="true" aria-expanded={pop.open}
        aria-label={`Notifications${unread ? ` (${unread} non lues)` : ""}`} onClick={() => pop.setOpen(!pop.open)}>
        <Bell size={18} />
        {unread > 0 && (
          <span className="num absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {pop.open && (
        <div className="absolute right-0 top-11 z-50 w-[min(380px,calc(100vw-1.5rem))] rounded-lg border border-line-strong bg-surface-2 shadow-xl shadow-black/50">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="text-[13px] font-semibold">Notifications <span className="text-fg-subtle font-normal">· 48 h</span></span>
            <button type="button" onClick={markRead} className="text-[12px] text-fg-muted hover:text-fg">Tout marquer comme lu</button>
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            {error ? <p className="p-4 text-[12.5px] text-danger">Notifications indisponibles : {(error as Error).message}</p> : null}
            {data && data.items.length === 0 && (
              <p className="p-6 text-center text-[12.5px] text-fg-muted">Aucun échec, aucune détection ni revue en attente sur les 48 dernières heures.</p>
            )}
            {data?.items.map((n) => {
              const Icon = icons[n.category];
              return (
                <button key={n.id} type="button" onClick={() => { pop.setOpen(false); navigate(n.link); }}
                  className={`flex w-full cursor-pointer items-start gap-3 border-b border-line/60 px-4 py-3 text-left hover:bg-surface-3 ${n.occurred_at > seen ? "" : "opacity-70"}`}>
                  <Icon size={16} className={`mt-0.5 shrink-0 ${tones[n.category]}`} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[12.5px] font-medium">{n.title}</span>
                    <span className="block truncate text-[12px] text-fg-muted">{n.message}</span>
                  </span>
                  <span className="shrink-0 text-[11px] text-fg-subtle">{fmtRelative(n.occurred_at)}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { me, logout } = useAuth();
  const pop = usePopover();
  const roleLabel = { admin: "Administrateur", analyst: "Analyste", viewer: "Lecteur" };
  if (!me) return null;
  return (
    <div ref={pop.ref} className="relative">
      <button type="button" onClick={() => pop.setOpen(!pop.open)} aria-haspopup="true" aria-expanded={pop.open}
        className="flex h-9 cursor-pointer items-center gap-2.5 rounded-md pl-1 pr-2.5 hover:bg-surface-2">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-accent/15 text-[12px] font-semibold uppercase text-accent-strong">
          {me.actor.slice(0, 2)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[12.5px] font-medium">{me.actor}</span>
          <span className="block text-[11px] text-fg-subtle">{roleLabel[me.role]}</span>
        </span>
      </button>
      {pop.open && (
        <div className="absolute right-0 top-11 z-50 w-64 rounded-lg border border-line-strong bg-surface-2 p-1.5 shadow-xl shadow-black/50">
          <div className="flex items-center gap-3 border-b border-line px-3 pb-3 pt-2">
            <UserRound size={16} className="text-fg-subtle" aria-hidden />
            <div className="min-w-0 text-[12.5px]">
              <div className="truncate font-medium">{me.user?.email ?? me.actor}</div>
              <div className="text-fg-subtle">Rôle : {roleLabel[me.role]}</div>
              {me.user?.last_login_at && <div className="text-fg-subtle">Connexion {fmtRelative(me.user.last_login_at)}</div>}
            </div>
          </div>
          <button type="button" onClick={logout}
            className="mt-1 flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-fg-muted hover:bg-surface-3 hover:text-fg">
            <LogOut size={15} aria-hidden /> Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}

export function Topbar({ onOpenMobile }: { onOpenMobile: () => void }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-bg/95 px-4 backdrop-blur md:px-6">
      <button type="button" className="icon-btn lg:hidden" onClick={onOpenMobile} aria-label="Ouvrir le menu"><Menu size={19} /></button>
      <Breadcrumbs />
      <div className="flex flex-1 justify-end md:justify-center"><GlobalSearch /></div>
      <div className="flex items-center gap-1">
        <Notifications />
        <UserMenu />
      </div>
    </header>
  );
}
