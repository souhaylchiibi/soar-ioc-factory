import { lazy, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import AppShell from "./components/layout/AppShell";
import { SkeletonBlock } from "./components/ui/States";

// One chunk per page: the console loads only what the analyst opens.
const Login = lazy(() => import("./pages/Login"));
const Overview = lazy(() => import("./pages/Overview"));
const ThreatIntel = lazy(() => import("./pages/ThreatIntel"));
const IocDetail = lazy(() => import("./pages/IocDetail"));
const Lifecycle = lazy(() => import("./pages/Lifecycle"));
const Sources = lazy(() => import("./pages/Sources"));
const Detections = lazy(() => import("./pages/Detections"));
const Automation = lazy(() => import("./pages/Automation"));
const Scoring = lazy(() => import("./pages/Scoring"));
const Audit = lazy(() => import("./pages/Audit"));
const Health = lazy(() => import("./pages/Health"));
const Reports = lazy(() => import("./pages/Reports"));
const Users = lazy(() => import("./pages/Users"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "checking") return <div className="p-6"><SkeletonBlock rows={6} /></div>;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route path="/" element={<Overview />} />
        <Route path="/threat-intel" element={<ThreatIntel />} />
        <Route path="/iocs/:id" element={<IocDetail />} />
        <Route path="/lifecycle" element={<Lifecycle />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/detections" element={<Detections />} />
        <Route path="/automation" element={<Automation />} />
        <Route path="/scoring" element={<Scoring />} />
        <Route path="/audit" element={<Audit />} />
        {/* Not "/health": that path is the API liveness probe (proxied by Vite and nginx). */}
        <Route path="/system-health" element={<Health />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/users" element={<Users />} />
        {/* Short aliases, kept for bookmarks */}
        <Route path="/inventory" element={<Navigate to="/threat-intel" replace />} />
        <Route path="/monitoring" element={<Navigate to="/detections" replace />} />
        <Route path="/workflows" element={<Navigate to="/automation" replace />} />
        <Route path="/published" element={<Navigate to="/lifecycle?tab=published" replace />} />
        <Route path="/expired" element={<Navigate to="/lifecycle?tab=expired" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
