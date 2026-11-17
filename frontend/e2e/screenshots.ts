/**
 * Captures the console pages for the README / report (real data, real API).
 * Usage: E2E_USER=… E2E_PASSWORD=… npx tsx e2e/screenshots.ts  (or node --experimental-strip-types)
 * Output: ../capture/<date>/console-*.png (SHOT_PREFIX=aws for the server)
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173";
const OUT = join(process.cwd(), "..", "capture", new Date().toISOString().slice(0, 10));
mkdirSync(OUT, { recursive: true });
const PREFIX = process.env.SHOT_PREFIX ?? "console";
const shot = (f: string) => join(OUT, f.replace(/^v2/, PREFIX));

const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL ?? "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });

await page.goto(`${BASE}/login`);
await page.screenshot({ path: shot("v2-01-login.png") });
await page.getByLabel("Identifiant").fill(process.env.E2E_USER ?? "");
await page.getByLabel("Mot de passe", { exact: true }).fill(process.env.E2E_PASSWORD ?? "");
await page.getByRole("button", { name: /se connecter/i }).click();
await page.getByRole("heading", { name: "SOC Overview" }).waitFor();

const shots: [string, string, string][] = [
  ["/", "v2-02-overview.png", "SOC Overview"],
  ["/detections", "v2-03-detection-center.png", "Detection Center"],
  ["/threat-intel", "v2-04-threat-intel.png", "Threat Intelligence"],
  ["/lifecycle", "v2-06-lifecycle.png", "IOC Lifecycle"],
  ["/scoring", "v2-07-scoring.png", "Scoring & Risk Analysis"],
  ["/sources", "v2-08-sources.png", "Threat Intelligence Sources"],
  ["/automation", "v2-09-automation.png", "Automation Center"],
  ["/audit", "v2-10-audit.png", "Audit Center"],
  ["/system-health", "v2-11-system-health.png", "System Health"],
];
for (const [path, file, heading] of shots) {
  await page.goto(`${BASE}${path}`);
  await page.getByRole("heading", { level: 1, name: heading }).waitFor();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(600);
  await page.screenshot({ path: shot(file), fullPage: path === "/" });
}

// IOC evidence file of the highest-scored indicator
await page.goto(`${BASE}/scoring`);
await page.locator("tbody tr").first().click();
const value = (await page.locator("tbody tr").first().locator("td:nth-child(2)").innerText()).trim().split("\n")[0];
await page.goto(`${BASE}/threat-intel?q=${encodeURIComponent(value)}`);
await page.locator("tbody tr").first().click();
await page.getByRole("tab", { name: /score/i }).waitFor();
await page.waitForLoadState("networkidle");
await page.screenshot({ path: shot("v2-05-ioc-detail.png") });

// Mobile overview
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await mobile.goto(`${BASE}/login`);
await mobile.getByLabel("Identifiant").fill(process.env.E2E_USER ?? "");
await mobile.getByLabel("Mot de passe", { exact: true }).fill(process.env.E2E_PASSWORD ?? "");
await mobile.getByRole("button", { name: /se connecter/i }).click();
await mobile.getByRole("heading", { level: 1, name: "SOC Overview" }).waitFor();
await mobile.waitForLoadState("networkidle");
await mobile.screenshot({ path: shot("v2-12-mobile.png") });

await browser.close();
console.log(`screenshots written to ${OUT}`);
