import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { SkeletonBlock } from "../ui/States";

const COLLAPSE_KEY = "soar.sidebar.collapsed";

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0"), [collapsed]);
  useEffect(() => { setMobileOpen(false); document.getElementById("main")?.focus({ preventScroll: true }); }, [pathname]);

  return (
    <div className="min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
        Aller au contenu
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      <div className={`flex min-h-full flex-col transition-[padding] duration-200 ${collapsed ? "lg:pl-[64px]" : "lg:pl-[236px]"}`}>
        <Topbar onOpenMobile={() => setMobileOpen(true)} />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 outline-none md:px-6 md:py-6">
          <Suspense fallback={<div className="card"><SkeletonBlock rows={8} /></div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
