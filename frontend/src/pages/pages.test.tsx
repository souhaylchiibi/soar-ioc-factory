import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt, me } from "../test/utils";
import { ApiError, tokenStore, type DashboardStats } from "../lib/api";

// Keep the real ApiError/tokenStore, replace every network call.
vi.mock("../lib/api", async (orig) => {
  const actual = await orig<typeof import("../lib/api")>();
  const api = Object.fromEntries(Object.keys(actual.api).map((k) => [k, vi.fn()]));
  return { ...actual, api };
});
const { api } = await import("../lib/api");
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const stats: DashboardStats = {
  total_iocs: 217, active_iocs: 133, expired_iocs: 0, rejected_iocs: 83, removed_iocs: 1,
  review_required: 0, published_iocs: 1, monitored_iocs: 132, duplicates_seen: 0, synthetic_iocs: 0,
  false_positives: 0, total_detections: 16, avg_score: 52.4, avg_processing_seconds: 81.8, dedup_rate: 0.234,
  by_type: { DOMAIN: 99, IP: 58 }, by_status: { MONITORED: 132, REJECTED: 83, PUBLISHED: 1, REMOVED: 1 },
  by_risk: { MEDIUM: 120, LOW: 83, CRITICAL: 1 }, score_distribution: { "0-49": 83 }, daily_new: [],
};

function signedIn(role: "viewer" | "analyst" | "admin" = "analyst") {
  tokenStore.set("test-token");
  mocked.me.mockResolvedValue(me(role));
}

beforeEach(() => {
  Object.values(mocked).forEach((fn) => fn.mockReset());
  mocked.liveness.mockResolvedValue({ status: "ok" });
  mocked.notifications.mockResolvedValue({ count: 0, items: [] });
});

describe("Login", async () => {
  const { default: Login } = await import("./Login");

  it("signs in and stores the token", async () => {
    mocked.login.mockResolvedValue({ access_token: "jwt", expires_at: "", user: me().user });
    mocked.me.mockResolvedValue(me());
    renderAt(<Login />, { path: "/login", route: "/login" });
    await userEvent.type(screen.getByLabelText("Identifiant"), "ana");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "Str0ng!Passw0rd");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));
    await waitFor(() => expect(mocked.login).toHaveBeenCalledWith("ana", "Str0ng!Passw0rd"));
    expect(tokenStore.get()).toBe("jwt");
  });

  it("explains a locked account without revealing which field was wrong", async () => {
    mocked.login.mockRejectedValue(new ApiError(423, "locked"));
    renderAt(<Login />, { path: "/login", route: "/login" });
    await userEvent.type(screen.getByLabelText("Identifiant"), "ana");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "bad");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("verrouillé");
    expect(screen.getByLabelText("Mot de passe")).toHaveValue("");
  });

  it("uses a generic message on bad credentials", async () => {
    mocked.login.mockRejectedValue(new ApiError(401, "Identifiants invalides"));
    renderAt(<Login />, { path: "/login", route: "/login" });
    await userEvent.type(screen.getByLabelText("Identifiant"), "x");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "y");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Identifiant ou mot de passe incorrect");
  });
});

describe("route protection", async () => {
  const { default: App } = await import("../App");
  it("redirects anonymous users to the login page", async () => {
    const { render } = await import("@testing-library/react");
    const { MemoryRouter } = await import("react-router-dom");
    const { AuthProvider } = await import("../lib/auth");
    render(<MemoryRouter initialEntries={["/detections"]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  });
});

describe("SOC Overview", async () => {
  const { default: Overview } = await import("./Overview");

  it("renders only figures returned by the API", async () => {
    signedIn();
    mocked.stats.mockResolvedValue(stats);
    mocked.timeline.mockResolvedValue({ days: 30, series: [] });
    mocked.integrations.mockResolvedValue({ checked_at: new Date().toISOString(), cache_ttl_seconds: 30, items: [
      { name: "postgresql", kind: "database", status: "connected" },
      { name: "misp", kind: "publication", status: "not_configured", detail: "MISP_URL / MISP_KEY absents" },
    ] });
    mocked.sources.mockResolvedValue({ count: 0, sources: [] });
    mocked.audit.mockResolvedValue({ total: 0, entries: [] });
    mocked.runs.mockResolvedValue({ total: 0, failed_total: 0, avg_duration_ms_page: null, runs: [] });
    renderAt(<Overview />);
    expect(await screen.findByText("217")).toBeInTheDocument();
    expect(screen.getByText("132")).toBeInTheDocument();
    expect(screen.getByText("23,4 %")).toBeInTheDocument();
    expect(await screen.findByText("Configuration manquante")).toBeInTheDocument();
    expect(screen.getByText("Aucune activité sur cette fenêtre")).toBeInTheDocument();
  });

  it("shows the API error instead of fake numbers", async () => {
    signedIn();
    mocked.stats.mockRejectedValue(new ApiError(500, "Internal server error"));
    for (const k of ["timeline", "integrations", "sources", "audit", "runs"]) mocked[k].mockReturnValue(new Promise(() => {}));
    renderAt(<Overview />);
    expect(await screen.findByText("Erreur lors du chargement")).toBeInTheDocument();
    expect(screen.queryByText("217")).not.toBeInTheDocument();
  });
});

describe("Threat Intelligence", async () => {
  const { default: ThreatIntel } = await import("./ThreatIntel");

  it("lists IOCs, flags lab data and forwards URL filters to the API", async () => {
    signedIn();
    mocked.iocs.mockResolvedValue({ total: 1, offset: 0, limit: 50, items: [{
      id: "1", type: "DOMAIN", value: "evil.example", raw_value: "evil.example", status: "MONITORED", score: 61,
      risk_level: "MEDIUM", first_seen_at: "2026-11-01T00:00:00Z", last_seen_at: "2026-11-02T00:00:00Z",
      expires_at: null, removed_at: null, detection_count: 2, false_positive_count: 0, is_synthetic: true,
      tags: [], independent_source_count: 2,
    }] });
    renderAt(<ThreatIntel />, { path: "/threat-intel?status=MONITORED&risk=MEDIUM" });
    expect(await screen.findByText("evil.example")).toBeInTheDocument();
    expect(screen.getByText("LAB")).toBeInTheDocument();
    const qs = mocked.iocs.mock.calls[0][0] as string;
    expect(qs).toContain("status=MONITORED");
    expect(qs).toContain("risk=MEDIUM");
  });

  it("has a designed empty state", async () => {
    signedIn();
    mocked.iocs.mockResolvedValue({ total: 0, offset: 0, limit: 50, items: [] });
    renderAt(<ThreatIntel />, { path: "/threat-intel?q=nothing" });
    expect(await screen.findByText("Aucun IOC ne correspond")).toBeInTheDocument();
  });
});

describe("Detection Center", async () => {
  const { default: Detections } = await import("./Detections");
  const det = {
    id: "d1", ioc_id: "1", ioc_value: "34.204.119.63", ioc_type: "IP", ioc_risk: "MEDIUM", ioc_status: "MONITORED",
    ioc_synthetic: false, sensor: "wazuh", rule_id: "5712", signature: null, severity: null,
    matched_at: "2026-11-06T10:00:00Z", triage: "pending", reviewed_by: null, review_note: null, evidence: { full_log: "sshd" },
  };

  it("shows sensor alerts and lets an analyst qualify one after confirmation", async () => {
    signedIn("analyst");
    mocked.detections.mockResolvedValue({ total: 1, offset: 0, limit: 50, by_sensor: { wazuh: 1 }, by_triage: { pending: 1, confirmed: 0, false_positive: 0 }, items: [det] });
    mocked.reviewDetection.mockResolvedValue({ ...det, triage: "false_positive", reviewed_by: "ana" });
    renderAt(<Detections />, { path: "/detections" });
    await userEvent.click(await screen.findByText("34.204.119.63"));
    expect(screen.getAllByText("non fournie").length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /faux positif/i }));
    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(mocked.reviewDetection).toHaveBeenCalledWith("d1", "false_positive", undefined));
    expect(await screen.findByText(/Détection qualifiée/)).toBeInTheDocument();
  });

  it("hides triage and pipeline actions from viewers", async () => {
    signedIn("viewer");
    mocked.detections.mockResolvedValue({ total: 1, offset: 0, limit: 50, by_sensor: { wazuh: 1 }, by_triage: { pending: 1, confirmed: 0, false_positive: 0 }, items: [det] });
    renderAt(<Detections />, { path: "/detections" });
    await userEvent.click(await screen.findByText("34.204.119.63"));
    expect(screen.queryByRole("button", { name: /faux positif/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ingérer suricata/i })).not.toBeInTheDocument();
  });
});

describe("Operation trigger", async () => {
  const { OperationButton } = await import("../components/domain/OperationButton");

  it("asks for confirmation and reports failures returned by the API", async () => {
    signedIn("analyst");
    mocked.runOperation.mockResolvedValue({ candidates: 3, removed: 2, failed: 1 });
    renderAt(<OperationButton path="/iocs/remove/run" label="Retirer" description="desc" />);
    await userEvent.click(await screen.findByRole("button", { name: /retirer/i }));
    expect(mocked.runOperation).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Lancer" }));
    await waitFor(() => expect(mocked.runOperation).toHaveBeenCalledWith("/iocs/remove/run"));
    expect(await screen.findByText("Retirer terminé avec 1 échec(s)")).toBeInTheDocument();
  });
});
