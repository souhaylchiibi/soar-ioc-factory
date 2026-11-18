import {
  Activity, Boxes, Database, FileText, Gauge, LayoutDashboard,
  Radar, Route, ScrollText, Users, Workflow, type LucideIcon,
} from "lucide-react";
import type { Role } from "../../lib/api";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  minRole?: Role;
}

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Opérations",
    items: [
      { to: "/", label: "SOC Overview", icon: LayoutDashboard },
      { to: "/detections", label: "Detection Center", icon: Radar },
      { to: "/threat-intel", label: "Threat Intelligence", icon: Database },
    ],
  },
  {
    label: "Pipeline IOC",
    items: [
      { to: "/lifecycle", label: "IOC Lifecycle", icon: Route },
      { to: "/scoring", label: "Scoring & Risk", icon: Gauge },
      { to: "/sources", label: "Sources", icon: Boxes },
      { to: "/automation", label: "Automation Center", icon: Workflow },
    ],
  },
  {
    label: "Gouvernance",
    items: [
      { to: "/audit", label: "Audit Center", icon: ScrollText },
      { to: "/reports", label: "Rapports", icon: FileText },
      { to: "/system-health", label: "System Health", icon: Activity },
      { to: "/users", label: "Utilisateurs", icon: Users, minRole: "admin" },
    ],
  },
];

/** Breadcrumb labels for every route segment. */
export const ROUTE_LABELS: Record<string, string> = {
  "": "SOC Overview",
  detections: "Detection Center",
  "threat-intel": "Threat Intelligence",
  iocs: "Threat Intelligence",
  lifecycle: "IOC Lifecycle",
  scoring: "Scoring & Risk",
  sources: "Sources",
  automation: "Automation Center",
  audit: "Audit Center",
  reports: "Rapports",
  "system-health": "System Health",
  users: "Utilisateurs",
};

