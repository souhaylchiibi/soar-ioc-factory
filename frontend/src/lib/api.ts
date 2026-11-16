/**
 * Typed client for the SOAR API.
 *
 * Every number rendered by the console comes from these calls — there are no
 * local fallbacks or mock values: an API failure shows an error state.
 * The bearer token lives in sessionStorage (cleared when the tab closes);
 * a 401 anywhere logs the user out through the `soar:unauthorized` event.
 */

const BASE = "/api/v1";
const TOKEN_KEY = "soar.token";

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, prefix = BASE): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${prefix}${path}`, { ...init, headers: { ...headers, ...(init.headers ?? {}) } });
  } catch {
    throw new ApiError(0, "API injoignable — vérifiez que le service soar-api est démarré");
  }
  if (res.status === 401 && token) {
    window.dispatchEvent(new Event("soar:unauthorized"));
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });

/* ------------------------------------------------------------------ types */

export type Role = "viewer" | "analyst" | "admin";

export type IocStatus =
  | "NEW" | "NORMALIZED" | "ENRICHED" | "SCORED" | "PUBLISHED"
  | "MONITORED" | "EXPIRED" | "REMOVED" | "REJECTED" | "DUPLICATE"
  | "REVIEW_REQUIRED";

export type IocType = "IP" | "DOMAIN" | "URL" | "HASH_MD5" | "HASH_SHA1" | "HASH_SHA256";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
  locked_until: string | null;
}

export interface Me {
  actor: string;
  role: Role;
  is_service: boolean;
  user: UserInfo | null;
}

export interface Ioc {
  id: string;
  type: IocType;
  value: string;
  raw_value: string;
  status: IocStatus;
  score: number | null;
  risk_level: RiskLevel | null;
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

export interface ScoreBreakdown {
  policy_version: string;
  final_score: number;
  decision: string;
  components: ScoreComponent[];
  penalties: ScoreComponent[];
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

export interface IocDetail extends Ioc {
  score_breakdown: ScoreBreakdown | null;
  context: Record<string, unknown>;
  sources: { name: string; provenance_group: string; reliability: number; external_id: string | null }[];
  lifecycle: LifecycleEvent[];
  enrichment_verdicts: string[];
}

export interface DetectionItem {
  id: string;
  ioc_id: string;
  ioc_value: string;
  ioc_type: IocType;
  ioc_risk: RiskLevel | null;
  ioc_status: IocStatus;
  ioc_synthetic: boolean;
  sensor: string;
  rule_id: string | null;
  signature: string | null;
  severity: "critical" | "high" | "medium" | "low" | null;
  matched_at: string;
  triage: "pending" | "confirmed" | "false_positive";
  reviewed_by: string | null;
  review_note: string | null;
  evidence: Record<string, unknown>;
}

export interface IocActivity {
  ioc_id: string;
  score_history: { score: number; risk_level: RiskLevel | null; policy: string; computed_at: string; decision: string | null }[];
  publications: { id: string; target: string; target_ref: string | null; status: string; published_at: string | null; revoked_at: string | null; detail: Record<string, unknown> | null }[];
  detections: DetectionItem[];
  enrichments: { provider: string; verdict: string | null; reputation: number | null; fetched_at: string | null; is_synthetic: boolean; error: string | null }[];
  provenance: { source: string; provenance_group: string; reliability: number; first_seen_at: string | null; last_seen_at: string | null; external_id: string | null; external_url: string | null }[];
  audit: AuditEntry[];
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

export type ConnState = "connected" | "not_configured" | "no_data" | "unreachable" | "degraded" | "disabled";

export interface IntegrationItem {
  name: string;
  kind: string;
  status: ConnState;
  detail?: string;
  url?: string;
  file?: string;
  file_size?: number;
  file_modified_at?: string;
  last_ingest_at?: string | null;
  last_workflow_activity_at?: string | null;
  sources?: { name: string; status: ConnState; key_required: boolean; key_configured: boolean | null; last_success_at: string | null; last_error: string | null }[];
  providers?: { name: string; status: ConnState; detail: string }[];
}

export interface SourceRow {
  id: string;
  name: string;
  url: string | null;
  kind: string | null;
  provenance_group: string;
  reliability: number;
  enabled: boolean;
  requires_api_key: boolean;
  rate_limit_rpm: number;
  ioc_count: number;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  connection: ConnState;
  key_configured: boolean | null;
  runs_30d: number;
  failures_30d: number;
}

export interface SourceRun {
  id: number;
  occurred_at: string;
  actor: string;
  success: boolean;
  error: string | null;
  detail: Record<string, unknown>;
}

export interface AuditEntry {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
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

export interface RunEntry {
  id: number;
  occurred_at: string;
  actor: string;
  trigger: "n8n" | "manuel";
  action: string;
  success: boolean;
  error: string | null;
  duration_ms: number | null;
  detail: Record<string, unknown>;
}

export interface FunnelStage {
  key: string;
  label: string;
  count: number;
  current: number | null;
  proof: string;
}

export interface Notification {
  id: string;
  severity: "high" | "medium" | "low";
  category: "failure" | "detection" | "review";
  title: string;
  message: string;
  occurred_at: string;
  link: string;
}

export interface SystemHealth {
  status: string;
  checked_at: string;
  app: { name: string; env: string };
  checks: Record<string, any>;
  degraded_checks: string[];
}

export interface Paged<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export interface DailyReport {
  report_id: string;
  date: string;
  generated_at: string;
  payload: any;
}

/* ------------------------------------------------------------- endpoints */

export const api = {
  // auth
  login: (username: string, password: string) =>
    post<{ access_token: string; expires_at: string; user: UserInfo }>("/auth/login", { username, password }),
  me: () => get<Me>("/auth/me"),
  logout: () => post<void>("/auth/logout"),
  users: () => get<UserInfo[]>("/users"),
  createUser: (body: { username: string; email: string; password: string; role: Role }) => post<UserInfo>("/users", body),
  updateUser: (id: string, body: { role?: Role; is_active?: boolean; password?: string }) => patch<UserInfo>(`/users/${id}`, body),

  // inventory
  stats: () => get<DashboardStats>("/iocs/stats/dashboard"),
  iocs: (qs = "") => get<Paged<Ioc>>(`/iocs${qs}`),
  ioc: (id: string) => get<IocDetail>(`/iocs/${id}`),
  iocActivity: (id: string) => get<IocActivity>(`/iocs/${id}/activity`),
  transition: (id: string, to_status: IocStatus, reason: string) =>
    post<LifecycleEvent>(`/iocs/${id}/transition`, { to_status, reason }),
  search: (q: string) =>
    get<{ q: string; iocs: Pick<Ioc, "id" | "value" | "type" | "status" | "score" | "risk_level" | "is_synthetic">[]; sources: { name: string; enabled: boolean }[] }>(
      `/search?q=${encodeURIComponent(q)}`),

  // lifecycle & stats
  lifecycle: (limit = 100) => get<LifecycleEvent[]>(`/iocs/lifecycle/events?limit=${limit}`),
  funnel: () => get<{ stages: FunnelStage[]; decisions: Record<string, number>; current: Record<string, number>; verified_removals: number; collected_items: number }>("/lifecycle/funnel"),
  timeline: (days = 30) => get<{ days: number; series: { date: string; created: number; published: number; monitored: number; rejected: number; expired: number; detections: number }[] }>(`/stats/timeline?days=${days}`),

  // sources
  sources: () => get<{ count: number; sources: SourceRow[] }>("/sources"),
  sourceRuns: (name: string) => get<{ source: string; runs: SourceRun[] }>(`/sources/${encodeURIComponent(name)}/runs`),

  // detections
  detections: (qs = "") =>
    get<Paged<DetectionItem> & { by_sensor: Record<string, number>; by_triage: Record<string, number> }>(`/detections${qs}`),
  reviewDetection: (id: string, verdict: "confirmed" | "false_positive", note?: string) =>
    post<DetectionItem>(`/detections/${id}/review`, { verdict, note: note || null }),

  // automation
  workflows: (days = 7) => get<{ window_days: number; count: number; workflows: WorkflowSummary[] }>(`/workflows/summary?days=${days}`),
  runs: (qs = "") => get<{ total: number; failed_total: number; avg_duration_ms_page: number | null; runs: RunEntry[] }>(`/workflows/runs${qs}`),
  runOperation: (path: string) => post<Record<string, unknown>>(path),

  // audit / health / notifications
  audit: (qs = "") => get<{ total: number; entries: AuditEntry[] }>(`/audit${qs}`),
  auditActions: () => get<{ actions: { action: string; count: number }[] }>("/audit/actions"),
  health: () => get<SystemHealth>("/system/health"),
  integrations: (refresh = false) =>
    get<{ checked_at: string; cache_ttl_seconds: number; items: IntegrationItem[] }>(`/integrations/status${refresh ? "?refresh=true" : ""}`),
  notifications: () => get<{ count: number; items: Notification[] }>("/notifications"),
  liveness: () => request<{ status: string }>("/health", {}, ""),
  readiness: () => request<{ status: string; database: { status: string; detail: string } }>("/ready", {}, ""),

  // reports
  report: (date?: string) => get<DailyReport>(`/reports/daily${date ? `?report_date=${date}` : ""}`),
  generateReport: () => post<DailyReport>("/reports/daily"),
};
