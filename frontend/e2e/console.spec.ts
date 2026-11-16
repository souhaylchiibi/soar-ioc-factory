import { expect, test, type Page } from "@playwright/test";

const USER = process.env.E2E_USER ?? "";
const PASSWORD = process.env.E2E_PASSWORD ?? "";

test.skip(!USER || !PASSWORD, "E2E_USER / E2E_PASSWORD non définis");

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Identifiant").fill(USER);
  await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /se connecter/i }).click();
  await expect(page.getByRole("heading", { name: "SOC Overview" })).toBeVisible();
}

async function apiGet(page: Page, path: string) {
  return page.evaluate(async (p) => {
    const r = await fetch(`/api/v1${p}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem("soar.token")}` } });
    return r.json();
  }, path);
}

test("anonymous access is redirected to the login page", async ({ page }) => {
  await page.goto("/detections");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Connexion" })).toBeVisible();
});

test("unknown account gets a generic error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Identifiant").fill("e2e-unknown-user");
  await page.getByLabel("Mot de passe", { exact: true }).fill("not-the-password");
  await page.getByRole("button", { name: /se connecter/i }).click();
  await expect(page.getByRole("alert")).toContainText("Identifiant ou mot de passe incorrect");
});

test("overview KPIs equal the figures returned by the API", async ({ page }) => {
  await login(page);
  const stats = await apiGet(page, "/iocs/stats/dashboard");
  const tile = (label: string) => page.locator("a,div.card").filter({ hasText: label }).first();
  await expect(tile("IOC en base")).toContainText(new Intl.NumberFormat("fr-FR").format(stats.total_iocs));
  await expect(tile("Publiés")).toContainText(String(stats.published_iocs));
  await expect(tile("En surveillance")).toContainText(String(stats.monitored_iocs));
  await expect(page.getByText("État des intégrations")).toBeVisible();
});

test("every console page loads without an error state", async ({ page }) => {
  await login(page);
  const pages: [string, string][] = [
    ["Detection Center", "Detection Center"], ["Threat Intelligence", "Threat Intelligence"],
    ["IOC Lifecycle", "IOC Lifecycle"], ["Scoring & Risk", "Scoring & Risk Analysis"],
    ["Sources", "Threat Intelligence Sources"], ["Automation Center", "Automation Center"],
    ["Audit Center", "Audit Center"], ["Rapports", "Rapports"], ["System Health", "System Health"],
  ];
  for (const [link, heading] of pages) {
    await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: link, exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.locator("main [role=alert]")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test("every page also loads by direct URL (deep link / refresh)", async ({ page }) => {
  await login(page);
  const routes: [string, string][] = [
    ["/detections", "Detection Center"], ["/threat-intel", "Threat Intelligence"], ["/lifecycle", "IOC Lifecycle"],
    ["/scoring", "Scoring & Risk Analysis"], ["/sources", "Threat Intelligence Sources"], ["/automation", "Automation Center"],
    ["/audit", "Audit Center"], ["/reports", "Rapports"], ["/system-health", "System Health"], ["/users", "Utilisateurs"],
  ];
  for (const [path, heading] of routes) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});

test("global search opens the IOC evidence file", async ({ page }) => {
  await login(page);
  const top = await apiGet(page, "/iocs?limit=1&sort=score_desc");
  const value: string = top.items[0].value;
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: /recherche globale/i }).fill(value.slice(0, 8));
  await page.getByRole("option").filter({ hasText: value }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: value })).toBeVisible();
  await page.getByRole("tab", { name: /cycle de vie/i }).click();
  await expect(page.getByRole("tabpanel")).toBeVisible();
});

test("threat intel filters are reflected in the URL and the table", async ({ page }) => {
  await login(page);
  await page.goto("/threat-intel");
  await page.getByLabel("Statut").selectOption("MONITORED");
  await expect(page).toHaveURL(/status=MONITORED/);
  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible();
  const statuses = await rows.locator("td:nth-child(3)").allInnerTexts();
  expect(statuses.every((s) => s.includes("Surveillé"))).toBe(true);
});

test("mobile navigation drawer @mobile", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Audit Center" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Audit Center" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
