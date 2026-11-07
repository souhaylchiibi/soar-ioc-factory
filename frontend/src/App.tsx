import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Inventory from "./pages/Inventory";
import Sources from "./pages/Sources";
import Scoring from "./pages/Scoring";
import IocDetailPage from "./pages/IocDetailPage";
import Lifecycle from "./pages/Lifecycle";
import Published from "./pages/Published";
import Monitoring from "./pages/Monitoring";
import Expired from "./pages/Expired";
import Workflows from "./pages/Workflows";
import AuditLogs from "./pages/AuditLogs";
import Reports from "./pages/Reports";
import SystemHealth from "./pages/SystemHealth";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/scoring" element={<Scoring />} />
        <Route path="/iocs/:id" element={<IocDetailPage />} />
        <Route path="/lifecycle" element={<Lifecycle />} />
        <Route path="/published" element={<Published />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/expired" element={<Expired />} />
        <Route path="/workflows" element={<Workflows />} />
        <Route path="/audit" element={<AuditLogs />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/system-health" element={<SystemHealth />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
