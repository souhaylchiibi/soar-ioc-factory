import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const NAV: { to: string; label: string; icon: string }[] = [
  { to: "/", label: "Dashboard général", icon: "▦" },
  { to: "/inventory", label: "IOC Inventory", icon: "☰" },
  { to: "/sources", label: "Threat Intel Sources", icon: "⌁" },
  { to: "/scoring", label: "IOC Scoring", icon: "◑" },
  { to: "/lifecycle", label: "IOC Lifecycle", icon: "↻" },
  { to: "/published", label: "Published Indicators", icon: "⇪" },
  { to: "/monitoring", label: "Detection Monitoring", icon: "◉" },
  { to: "/expired", label: "Expired Indicators", icon: "⏱" },
  { to: "/workflows", label: "Automation Workflows", icon: "⚡" },
  { to: "/audit", label: "Audit Logs", icon: "▤" },
  { to: "/reports", label: "Reports", icon: "▥" },
  { to: "/health", label: "System Health", icon: "♥" },
];

export default function Layout() {
  const [health, setHealth] = useState<string>("…");

  useEffect(() => {
    let alive = true;
    const ping = () =>
      api
        .liveness()
        .then((r) => alive && setHealth(r.status === "ok" ? "API OK" : "API ?"))
        .catch(() => alive && setHealth("API KO"));
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-edge bg-panel/60 flex flex-col">
        <div className="px-5 py-5 border-b border-edge">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 grid place-items-center text-lg">
              🛡️
            </div>
            <div>
              <div className="font-bold leading-tight">
                SOAR <span className="text-signal">IOC</span>
              </div>
              <div className="text-[11px] text-muted">Factory · v0.1.0</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-[13.5px] border-l-2 transition-colors ${
                  isActive
                    ? "border-signal bg-signal/10 text-signal font-semibold"
                    : "border-transparent text-muted hover:text-ink hover:bg-white/5"
                }`
              }
            >
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-5 py-4 border-t border-edge text-[11.5px] text-muted">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                health === "API OK" ? "bg-green-500" : "bg-red-500"
              }`}
            />
            {health} · données temps réel PostgreSQL
          </div>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-[1500px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
