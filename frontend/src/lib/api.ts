/**
 * Typed client for the SOAR API.
 *
 * Every number rendered by the dashboard comes from these calls — there are
 * no local fallbacks or mock values: an API failure shows an error, period.
 */

const BASE = "/api/v1";

/** Fetch outside the versioned prefix (health probes live at the root). */
async function rawGet<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return (await res.json()) as T;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const get = <T,>(path: string) => request<T>(path);
export const post = <path extends string>(path: path) =>
  request<unknown>(path, { method: "POST" });

/* ------------------------------------------------------------------ types */

export type IocStatus =
  | "NEW" | "NORMALIZED" | "ENRICHED" | "SCORED" | "PUBLISHED"
  | "MONITORED" | "EXPIRED" | "REMOVED" | "REJECTED" | "DUPLICATE"
  | "REVIEW_REQUIRED";

export type IocType = "IP" | "DOMAIN" | "URL" | "HASH_MD5" | "HASH_SHA1" | "HASH_SHA256";

export interface Ioc {
  id: string;
  type: IocType;
  value: string;
  raw_value: string;
  status: IocStatus;
  score: number | null;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | null;
  first_seen_at: string;
  last_seen_at: string;
  expires_at: string | null;
  removed_at: string | null;
  detection_count: number;
  false_positive_count: number;
  is_synthetic: boolean;
  tags: string[];
  independent_source_count: number;
}

export interface ScoreComponent {
  key: string;
  label: string;
  points: number;
  max_points: number;
  explanation: string;
}

export interface IocDetail extends Ioc {
  score_breakdown: {
    policy_version: string;
    final_score: number;
    decision: string;
    components: ScoreComponent[];
    penalties: ScoreComponent[];
  } | null;
  context: Record<string, unknown>;
  sources: { name: string; provenance_group: string; reliability: number; external_id: string | null }[];
  lifecycle: {
    from_status: IocStatus | null;
    to_status: IocStatus;
    reason: string;
    actor: string;
    triggered_by: string | null;
    score_before: number | null;
    score_after: number | null;
    verified: boolean;
    created_at: string;
  }[];
  enrichment_verdicts: string[];
}

export interface DashboardStats {
  total_iocs: number;
  active_iocs: number;
  expired_iocs: number;
  rejected_iocs: number;
  removed_iocs: number;
  review_required: number;
  published_iocs: number;
  monitored_iocs: number;
  duplicates_seen: number;
  synthetic_iocs: number;
  false_positives: number;
  total_detections: number;
  avg_score: number | null;
  avg_processing_seconds: number | null;
  dedup_rate: number | null;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_risk: Record<string, number>;
  score_distribution: Record<string, number>;
  daily_new: { date: string; count: number }[];
}

export interface SourceStat {
  name: string;
  provenance_group: string;
  reliability: number;
  enabled: boolean;
  ioc_count: number;
  last_success_at: string | null;
  last_error: string | null;
}

export interface LifecycleEvent {
  from_status: IocStatus | null;
  to_status: IocStatus;
  reason: string;
  actor: string;
  triggered_by: string | null;
  score_before: number | null;
  score_after: number | null;
  verified: boolean;
  created_at: string;
}

export interface Detection {
  id: string;
  ioc_id: string;
  sensor: string;
  rule_id: string | null;
  matched_at: string;
  is_false_positive: boolean | null;
}

export interface AuditEntry {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  success: boolean;
  error: string | null;
  detail: Record<string, unknown>;
}

export interface WorkflowSummary {
  workflow: string;
  operations: number;
  success: number;
  failed: number;
  actions: { action: string; count: number }[];
  last_run_at: string | null;
}

export interface SystemHealth {
  status: string;
  checked_at: string;
  app: { name: string; env: string };
  checks: Record<string, any>;
  degraded_checks: string[];
}

export interface IocList {
  total: number;
  offset: number;
  limit: number;
  items: Ioc[];
}

/* ------------------------------------------------------------- endpoints */

export const api = {
  stats: () => get<DashboardStats>("/iocs/stats/dashboard"),
  sources: () => get<SourceStat[]>("/iocs/stats/sources"),
  iocs: (qs = "") => get<IocList>(`/iocs${qs}`),
  ioc: (id: string) => get<IocDetail>(`/iocs/${id}`),
  lifecycle: (limit = 100) => get<LifecycleEvent[]>(`/iocs/lifecycle/events?limit=${limit}`),
  detections: (limit = 50) =>
    get<{ count: number; false_positives_in_window: number; detections: Detection[] }>(
      `/iocs/detections/recent?limit=${limit}`),
  audit: (qs = "") => get<{ total: number; entries: AuditEntry[] }>(`/audit${qs}`),
  auditActions: () => get<{ actions: { action: string; count: number }[] }>("/audit/actions"),
  workflows: () => get<{ window_days: number; count: number; workflows: WorkflowSummary[] }>(
    "/workflows/summary"),
  health: () => get<SystemHealth>("/system/health"),
  report: (date?: string) =>
    get<{ report_id: string; date: string; generated_at: string; payload: any }>(
      `/reports/daily${date ? `?report_date=${date}` : ""}`),
  liveness: () => rawGet<{ status: string }>("/health"),
  readiness: () =>
    rawGet<{ status: string; database: { status: string } }>("/ready"),
};

/* helpers */
export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" }) : "—";

export const fmtShort = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";

export const statusBadge = (s: IocStatus | string): string => {
  const map: Record<string, string> = {
    PUBLISHED: "badge badge-ok",
    MONITORED: "badge badge-info",
    SCORED: "badge badge-violet",
    ENRICHED: "badge badge-violet",
    NORMALIZED: "badge badge-info",
    NEW: "badge badge-info",
    EXPIRED: "badge badge-warn",
    REMOVED: "badge badge-bad",
    REJECTED: "badge badge-bad",
    REVIEW_REQUIRED: "badge badge-warn",
    DUPLICATE: "badge badge-warn",
  };
  return map[s] ?? "badge badge-info";
};

export const riskBadge = (r: string | null): string => {
  const map: Record<string, string> = {
    CRITICAL: "badge badge-bad",
    HIGH: "badge badge-warn",
    MEDIUM: "badge badge-info",
    LOW: "badge badge-ok",
  };
  return r ? map[r] ?? "badge badge-info" : "badge badge-info";
};
