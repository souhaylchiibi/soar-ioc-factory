import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnBadge, RiskBadge, SeverityBadge, StatusBadge, SyntheticTag } from "./Badge";
import { EmptyState, ErrorState } from "./States";
import { Pagination } from "./Table";
import { ApiError } from "../../lib/api";

describe("badges", () => {
  it("labels statuses in French with their meaning as a tooltip", () => {
    render(<StatusBadge status="REVIEW_REQUIRED" />);
    const badge = screen.getByText("À revoir");
    expect(badge).toHaveAttribute("title", "Décision analyste requise");
  });

  it("states explicitly when a value is unknown instead of hiding it", () => {
    render(<><RiskBadge risk={null} /><SeverityBadge severity={null} /></>);
    expect(screen.getByText("non évalué")).toBeInTheDocument();
    expect(screen.getByText("non fournie")).toHaveAttribute("title", "Le capteur n'a fourni aucune sévérité");
  });

  it("shows risk with text, not colour alone", () => {
    render(<RiskBadge risk="CRITICAL" />);
    expect(screen.getByText("Critique")).toBeInTheDocument();
  });

  it("marks lab data and missing configuration", () => {
    render(<><SyntheticTag /><ConnBadge state="not_configured" /></>);
    expect(screen.getByText("LAB")).toBeInTheDocument();
    expect(screen.getByText("Configuration manquante")).toBeInTheDocument();
  });
});

describe("states", () => {
  it("renders an API error with its HTTP status and a retry action", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(503, "base indisponible")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("HTTP 503");
    expect(screen.getByRole("alert")).toHaveTextContent("base indisponible");
    await userEvent.click(screen.getByRole("button", { name: /réessayer/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("explains an unreachable API", () => {
    render(<ErrorState error={new ApiError(0, "x")} />);
    expect(screen.getByText("API injoignable")).toBeInTheDocument();
  });

  it("renders a designed empty state", () => {
    render(<EmptyState title="Aucune détection">Vérifiez les capteurs.</EmptyState>);
    expect(screen.getByText("Aucune détection")).toBeInTheDocument();
  });
});

describe("pagination", () => {
  it("disables navigation at the bounds and reports the range", async () => {
    const onChange = vi.fn();
    render(<Pagination total={120} offset={50} limit={50} onChange={onChange} />);
    expect(screen.getByText("51–100 sur 120")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Page suivante" }));
    expect(onChange).toHaveBeenCalledWith(100);
    await userEvent.click(screen.getByRole("button", { name: "Page précédente" }));
    expect(onChange).toHaveBeenCalledWith(0);
  });
});
