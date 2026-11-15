// Présentation SOAR IOC Factory — 30 slides, chiffres lus dans metrics.json.
// Usage : node scripts/build_presentation.js "<racine du projet>" "<chemin vers apply_theme.js>"
// Prérequis : pptxgenjs, react, react-dom, react-icons, sharp (npm, hors dépôt ; NODE_PATH vers leur node_modules).
// Sortie : reports/PRESENTATION_SOAR_IOC_FACTORY.pptx
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = process.argv[2];
const OUT = path.join(ROOT, "reports", "PRESENTATION_SOAR_IOC_FACTORY.pptx");
const M = JSON.parse(fs.readFileSync(path.join(ROOT, "reports/evaluation/metrics.json"), "utf8"));
const CAP = (f) => path.join(ROOT, "capture", "2026-11-14", f);
const FIG = (f) => path.join(ROOT, "reports", "figures", f);
const { applyTheme } = require(process.argv[3]);

// ------------------------------------------------------------------ theme --
const HEX = {
  night: "0B1320", slate: "1E2A3D", white: "FFFFFF", mist: "EEF2F6",
  amber: "F59E0B", teal: "14B8A6", red: "E5484D", green: "22A06B",
  grey: "64748B", sky: "38BDF8", ink: "334155", line: "D5DCE5",
};
const THEME = {
  name: "SOAR IOC Factory",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: HEX.night, lt1: HEX.white, dk2: HEX.slate, lt2: HEX.mist,
    accent1: HEX.amber, accent2: HEX.teal, accent3: HEX.red, accent4: HEX.green,
    accent5: HEX.grey, accent6: HEX.sky, hlink: HEX.teal, folHlink: HEX.grey,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "SOAR IOC Factory — Soutenance";
pres.author = "Souhayl Chouaibi";
pres.subject = "Projet 3 — usine à indicateurs de compromission";
const C = pres.SchemeColor;

// ------------------------------------------------------------- helpers ----
const fr = (n, d = 1) => Number(n).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }).replace(/ /g, " ");
const int = (n) => Number(n).toLocaleString("fr-FR").replace(/ /g, " ");
const W = 13.333;

const iconCache = {};
async function icon(name, color) {
  const key = name + color;
  if (iconCache[key]) return iconCache[key];
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  iconCache[key] = "image/png;base64," + buf.toString("base64");
  return iconCache[key];
}
const shadow = () => ({ type: "outer", color: "1E2A3D", opacity: 0.12, blur: 8, offset: 2, angle: 90 });

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08,
    fill: { color: opts.fill || C.background1 },
    line: { color: opts.line || HEX.line, width: opts.lineW ?? 0.75 },
    shadow: opts.noShadow ? undefined : shadow(),
    objectName: opts.name || "card",
  });
}
async function iconCircle(slide, name, x, y, d, bg = C.accent1, fg = HEX.night) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg, width: 0 }, objectName: "icon-bg" });
  const p = d * 0.26;
  slide.addImage({ data: await icon(name, fg), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, altText: name });
}
function text(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, margin: 0, valign: "top", color: C.text1, fontSize: 14 }, o));
}
function stat(slide, x, y, w, value, label, color = C.accent1, size = 44) {
  text(slide, value, { x, y, w, h: 0.8, fontSize: size, bold: true, color, valign: "bottom", fontFace: "Calibri" });
  text(slide, label, { x, y: y + 0.85, w, h: 0.6, fontSize: 13, color: C.accent5 });
}
function screenshot(slide, file, x, y, w, caption) {
  const h = w * 499 / 800;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.06, y: y - 0.06, w: w + 0.12, h: h + 0.12, rectRadius: 0.06, fill: { color: HEX.night }, line: { color: HEX.night, width: 0 }, shadow: shadow(), objectName: "screen-frame" });
  slide.addImage({ path: file, x, y, w, h, altText: caption });
  if (caption) text(slide, caption, { x, y: y + h + 0.15, w, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
}
function arrow(slide, x, y, w, h, color = HEX.grey, head = true, flipH = false) {
  slide.addShape(pres.shapes.LINE, { x, y, w, h, flipH, line: { color, width: 1.75, endArrowType: head ? "triangle" : undefined }, objectName: "arrow" });
}
const chartBase = () => ({
  catAxisLabelColor: HEX.ink, valAxisLabelColor: HEX.grey, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", titleFontFace: "+mn-lt",
  valGridLine: { color: "E2E8F0", size: 0.75 }, catGridLine: { style: "none" },
  dataLabelColor: HEX.ink, dataLabelFontSize: 12, catAxisLineShow: false, valAxisLineShow: false,
});

// ------------------------------------------------------------- layouts ----
const FOOTER = "SOAR IOC Factory  ·  Projet 3 — soutenance  ·  14 novembre 2026";
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.white },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOTER, options: { x: 0.6, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.grey, align: "right" },
});
pres.defineSlideMaster({
  title: "SECTION",
  background: { color: HEX.night },
  objects: [
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 2.35, w: 8, h: 0.6, fontSize: 18, bold: true, color: C.accent1, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.95, w: 7.6, h: 2.0, fontSize: 40, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: "94A3B8", align: "right" },
});
pres.defineSlideMaster({ title: "COVER", background: { color: HEX.night }, objects: [] });

async function decor(slide, iconName) {
  // motif des slides sombres : grands cercles translucides + icône
  slide.addShape(pres.shapes.OVAL, { x: 8.9, y: 1.2, w: 5.4, h: 5.4, fill: { color: C.accent1, transparency: 88 }, line: { color: C.accent1, width: 0 }, objectName: "decor" });
  slide.addShape(pres.shapes.OVAL, { x: 9.9, y: 2.2, w: 3.4, h: 3.4, fill: { color: C.accent1, transparency: 80 }, line: { color: C.accent1, width: 0 }, objectName: "decor" });
  slide.addImage({ data: await icon(iconName, HEX.amber), x: 10.85, y: 3.15, w: 1.5, h: 1.5, altText: iconName });
}
let sectionName = "Ouverture";
function content(title) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sectionName });
  s.addText(title, { placeholder: "title" });
  return s;
}
async function section(num, title, iconName, notes) {
  sectionName = title;
  pres.addSection({ title });
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: title });
  s.addText(num, { placeholder: "body" });
  s.addText(title, { placeholder: "title" });
  await decor(s, iconName);
  s.addNotes(notes);
  return s;
}

// ============================================================= SLIDES =====
(async () => {
  const inv = M.inventory, ded = M.dedup, enr = M.enrichment, sco = M.scoring;
  const det = M.detection, perf = M.performance, aut = M.automation, lif = M.lifecycle;
  const TESTS = 192;

  // 1 — Couverture --------------------------------------------------------
  pres.addSection({ title: "Ouverture" });
  let s = pres.addSlide({ masterName: "COVER", sectionTitle: "Ouverture" });
  await decor(s, "FaShieldAlt");
  text(s, "PROJET 3  ·  USINE À INDICATEURS DE COMPROMISSION", { x: 0.9, y: 1.3, w: 8, h: 0.4, fontSize: 14, bold: true, color: C.accent1, charSpacing: 2 });
  text(s, "SOAR IOC Factory", { x: 0.9, y: 1.9, w: 8.5, h: 1.2, fontSize: 54, bold: true, color: C.background1 });
  text(s, "Automatiser le cycle de vie des indicateurs de compromission, sans jamais mentir sur leur état", { x: 0.9, y: 3.15, w: 7.6, h: 1.0, fontSize: 20, color: "CBD5E1" });
  text(s, [
    { text: "Souhayl Chouaibi", options: { bold: true, color: C.background1, breakLine: true } },
    { text: "Soutenance de projet  ·  14 novembre 2026", options: { color: "94A3B8" } },
  ], { x: 0.9, y: 5.4, w: 7, h: 0.8, fontSize: 16 });
  s.addNotes("Présentation du projet SOAR IOC Factory : une plateforme qui automatise tout le cycle de vie des indicateurs de compromission, de la collecte jusqu'au retrait vérifié.");

  // 2 — Sommaire -------------------------------------------------------------
  s = content("Plan de la présentation");
  const agenda = [
    ["01", "Problème et objectifs", "Pourquoi une usine à indicateurs", "FaBullseye"],
    ["02", "Conception", "Cycle de vie, architecture, machine à états", "FaProjectDiagram"],
    ["03", "Moteur IOC", "Collecte, déduplication, enrichissement, notation", "FaCogs"],
    ["04", "Automatisation et SOC", "n8n, Suricata, Wazuh, MISP, dashboard", "FaRobot"],
    ["05", "Évaluation", "Mesures, performance, hypothèse vs mesure", "FaChartBar"],
    ["06", "Sécurité, tests, bilan", "Menaces, AWS, 192 tests, limites", "FaLock"],
  ];
  for (let i = 0; i < agenda.length; i++) {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.6 + col * 4.1, y = 1.6 + row * 2.6, w = 3.8, h = 2.3;
    card(s, x, y, w, h, { fill: C.background2, line: C.background2 });
    await iconCircle(s, agenda[i][3], x + 0.3, y + 0.3, 0.7);
    text(s, agenda[i][0], { x: x + 2.8, y: y + 0.3, w: 0.75, h: 0.6, fontSize: 28, bold: true, color: "CBD5E1", align: "right" });
    text(s, agenda[i][1], { x: x + 0.3, y: y + 1.15, w: w - 0.6, h: 0.45, fontSize: 18, bold: true });
    text(s, agenda[i][2], { x: x + 0.3, y: y + 1.6, w: w - 0.6, h: 0.55, fontSize: 13, color: C.accent5 });
  }
  s.addNotes("Six parties : le problème, la conception, le moteur, l'automatisation et les intégrations SOC, l'évaluation chiffrée, puis sécurité, tests et bilan.");

  // 3 — Problème -------------------------------------------------------------
  sectionName = "Problème et objectifs";
  pres.addSection({ title: sectionName });
  s = content("Les indicateurs bruts sont inutilisables tels quels");
  const pbs = [
    ["FaVolumeUp", "Bruyants", "Des flux publics hétérogènes, de fiabilité inégale, qui publient sans contexte ni niveau de confiance."],
    ["FaCopy", "Dupliqués", "Le même indicateur arrive de plusieurs flux, sous des formes différentes (casse, espaces, URL non canonique)."],
    ["FaHourglassEnd", "Obsolètes", "Une IP malveillante hier peut être réattribuée demain : sans expiration, la liste de blocage devient un risque."],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.6, 3.8, 3.6);
    await iconCircle(s, pbs[i][0], x + 0.35, 1.95, 0.85, C.accent3, HEX.white);
    text(s, pbs[i][1], { x: x + 0.35, y: 3.0, w: 3.1, h: 0.5, fontSize: 22, bold: true });
    text(s, pbs[i][2], { x: x + 0.35, y: 3.55, w: 3.1, h: 1.5, fontSize: 14, color: C.text2 });
  }
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.6, w: 12.1, h: 1.0, rectRadius: 0.08, fill: { color: C.text1 }, line: { color: C.text1, width: 0 }, objectName: "callout" });
  text(s, [
    { text: "Objectif : ", options: { bold: true, color: C.accent1 } },
    { text: "transformer ce flux brut en un inventaire unique, noté, explicable et traçable, publié seulement quand c'est justifié.", options: { color: C.background1 } },
  ], { x: 0.95, y: 5.6, w: 11.5, h: 1.0, fontSize: 17, valign: "middle" });
  s.addNotes("Trois défauts structurels des IOC : le bruit, la duplication, l'obsolescence. L'usine doit les traiter automatiquement et garder la preuve de chaque décision.");

  // 4 — Solution + chiffres clés --------------------------------------------
  s = content("SOAR IOC Factory en un coup d'œil");
  text(s, "Une plateforme qui automatise le cycle complet, de la collecte au retrait vérifié, et qui refuse de mentir : une publication n'est « vérifiée » qu'après relecture, un retrait non confirmé bloque le passage à REMOVED.", { x: 0.6, y: 1.45, w: 12.1, h: 0.9, fontSize: 17, color: C.text2 });
  const kpis = [
    [String(inv.total_iocs), "indicateurs réels en base", C.accent1],
    [String(TESTS), "tests automatisés au vert", C.accent2],
    ["8", "workflows n8n orchestrés", C.accent6],
    ["0", "port applicatif exposé", C.accent4],
  ];
  kpis.forEach((k, i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 2.75, 2.85, 2.1, { fill: C.background2, line: C.background2 });
    stat(s, x + 0.3, 2.95, 2.4, k[0], k[1], k[2], 54);
  });
  const facts = [
    ["FaBalanceScale", `${fr(sco.explainability_pct, 0)} % des scores expliqués composante par composante`],
    ["FaFingerprint", "Journal d'audit append-only, protégé par trigger PostgreSQL"],
    ["FaCloud", "Déployé sur EC2, accessible uniquement par tunnel SSH"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    await iconCircle(s, facts[i][0], x, 5.35, 0.6, C.text1, HEX.amber);
    text(s, facts[i][1], { x: x + 0.8, y: 5.3, w: 3.1, h: 0.75, fontSize: 14, valign: "middle" });
  }
  s.addNotes(`Chiffres lus dans metrics.json du 14/11/2026 : ${inv.total_iocs} IOC, ${TESTS} tests, 8 workflows. Aucun indicateur synthétique dans l'inventaire évalué.`);

  // 5 — Section Conception ---------------------------------------------------
  await section("02", "Conception", "FaProjectDiagram", "Comment la plateforme est construite : le cycle de vie imposé, l'architecture en couches et la machine à états.");

  // 6 — Cycle de vie 10 étapes ----------------------------------------------
  s = content("Le cycle de vie en dix étapes, toutes automatisées");
  const steps = [
    ["Collecte", "7 flux publics"], ["Normalisation", "forme canonique"], ["Déduplication", "empreinte SHA-256"],
    ["Enrichissement", "OTX, AbuseIPDB"], ["Notation", "5 composantes"], ["Décision", "seuils 80 / 50"],
    ["Publication", "vérifiée par relecture"], ["Surveillance", "Suricata, Wazuh"], ["Expiration", "date de la source"],
    ["Retrait vérifié", "révocation confirmée"],
  ];
  for (let i = 0; i < 10; i++) {
    const row = Math.floor(i / 5), col = i % 5;
    const x = 0.6 + col * 2.47, y = 1.65 + row * 2.55, w = 2.22, h = 2.1;
    card(s, x, y, w, h, { fill: row === 0 ? C.background2 : C.background1 });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "step-num" });
    text(s, String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fontSize: 18, bold: true, align: "center", valign: "middle" });
    text(s, steps[i][0], { x: x + 0.25, y: y + 1.0, w: w - 0.4, h: 0.45, fontSize: 17, bold: true });
    text(s, steps[i][1], { x: x + 0.25, y: y + 1.45, w: w - 0.4, h: 0.5, fontSize: 13, color: C.accent5 });
    if (col < 4) arrow(s, x + w + 0.02, y + h / 2, 0.21, 0, HEX.amber);
  }
  s.addNotes("Les dix étapes du sujet. Chacune a une route API, une transition journalisée et au moins un test.");

  // 7 — Architecture --------------------------------------------------------
  s = content("Architecture : l'orchestration appelle, l'API décide");
  card(s, 0.6, 1.45, 7.4, 4.85 + 0.05, { noShadow: false });
  s.addImage({ path: FIG("architecture.png"), x: 0.75, y: 1.6, w: 7.1, h: 7.1 * 1258 / 1918, altText: "Schéma d'architecture" });
  const layers = [
    ["FaRobot", "Orchestration", "n8n : 8 workflows planifiés, idempotents, sans logique métier"],
    ["FaServer", "Décision", "FastAPI : normalisation, notation, machine à états, publication"],
    ["FaDatabase", "Preuve", "PostgreSQL 16 : 13 tables, audit append-only, migrations Alembic"],
    ["FaDesktop", "Restitution", "React 19 + TypeScript : 13 pages lues sur l'API"],
  ];
  for (let i = 0; i < 4; i++) {
    const y = 1.5 + i * 1.22;
    await iconCircle(s, layers[i][0], 8.4, y + 0.05, 0.65);
    text(s, layers[i][1], { x: 9.25, y, w: 3.5, h: 0.4, fontSize: 17, bold: true });
    text(s, layers[i][2], { x: 9.25, y: y + 0.4, w: 3.5, h: 0.75, fontSize: 13, color: C.text2 });
  }
  text(s, "Source : reports/figures/architecture.png, construit depuis le code et les fichiers Docker Compose.", { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("Séparation stricte : n8n ne fait qu'appeler des routes ; toute décision métier vit dans l'API, ce qui la rend testable et traçable.");

  // 8 — Stack ------------------------------------------------------------------
  s = content("Une pile technique choisie pour la preuve");
  const stack = [
    ["FaPython", "Backend", "Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic 2"],
    ["FaDatabase", "Données", "PostgreSQL 16 · Alembic · tests sur vraie base, pas de SQLite"],
    ["FaProjectDiagram", "Orchestration", "n8n · 8 workflows exportés en JSON, IDs stables"],
    ["FaReact", "Frontend", "React 19 · TypeScript · Tailwind 4 · Recharts 3"],
    ["FaBroadcastTower", "Détection", "Suricata (rejeu PCAP) · Wazuh 4.12 · client MISP REST"],
    ["FaDocker", "Déploiement", "Docker Compose · profils mémoire · EC2 par tunnel SSH"],
  ];
  for (let i = 0; i < 6; i++) {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.6 + col * 4.1, y = 1.6 + row * 2.6;
    card(s, x, y, 3.8, 2.3);
    await iconCircle(s, stack[i][0], x + 0.3, y + 0.3, 0.7, C.text1, HEX.amber);
    text(s, stack[i][1], { x: x + 1.2, y: y + 0.4, w: 2.4, h: 0.5, fontSize: 18, bold: true, valign: "middle" });
    text(s, stack[i][2], { x: x + 0.3, y: y + 1.2, w: 3.2, h: 0.9, fontSize: 14, color: C.text2 });
  }
  s.addNotes("Choix guidés par la vérifiabilité : PostgreSQL réel en test, migrations versionnées, workflows exportés dans le dépôt.");

  // 9 — Machine à états --------------------------------------------------------
  s = content("Une machine à états qui interdit les raccourcis");
  const box = (label, x, y, fill, fg = HEX.white) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.0, h: 0.7, rectRadius: 0.1, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: "state-" + label });
    text(s, label, { x, y, w: 2.0, h: 0.7, fontSize: 15, bold: true, color: fg, align: "center", valign: "middle" });
  };
  const xs = [0.6, 3.1, 5.6, 8.1];
  ["NEW", "NORMALIZED", "ENRICHED", "SCORED"].forEach((l, i) => box(l, xs[i], 1.6, HEX.slate));
  for (let i = 0; i < 3; i++) arrow(s, xs[i] + 2.02, 1.95, 0.46, 0);
  arrow(s, 9.1, 2.3, 0, 0.6, HEX.grey, false);
  arrow(s, 6.6, 2.9, 5.0, 0, HEX.grey, false);
  [6.6, 9.1, 11.6].forEach((x) => arrow(s, x, 2.9, 0, 0.55));
  box("PUBLISHED", 5.6, 3.45, HEX.green);
  box("MONITORED", 8.1, 3.45, HEX.teal);
  box("REJECTED", 10.6, 3.45, HEX.grey);
  text(s, "score ≥ 80", { x: 5.6, y: 4.2, w: 2.0, h: 0.3, fontSize: 12, color: C.accent5, align: "center" });
  text(s, "50 ≤ score < 80", { x: 8.1, y: 4.2, w: 2.0, h: 0.3, fontSize: 12, color: C.accent5, align: "center" });
  text(s, "score < 50", { x: 10.6, y: 4.2, w: 2.0, h: 0.3, fontSize: 12, color: C.accent5, align: "center" });
  arrow(s, 9.1, 4.55, 0, 0.3, HEX.grey, false);
  arrow(s, 6.6, 4.85, 2.5, 0, HEX.grey, false);
  arrow(s, 6.6, 4.55, 0, 0.75);
  box("EXPIRED", 5.6, 5.3, HEX.amber, HEX.night);
  arrow(s, 5.6, 5.65, 0.48, 0, HEX.grey, true, true);
  box("REMOVED", 3.1, 5.3, HEX.red);
  card(s, 0.6, 2.75, 4.2, 2.25, { fill: C.background2, line: C.background2, noShadow: true });
  text(s, [
    { text: "Règles appliquées par le code", options: { bold: true, breakLine: true } },
    { text: "Table TRANSITIONS explicite : tout saut d'état est refusé", options: { bullet: true, breakLine: true } },
    { text: "REMOVED impossible sans révocation confirmée", options: { bullet: true, breakLine: true } },
    { text: "Chaque transition est journalisée", options: { bullet: true } },
  ], { x: 0.85, y: 2.9, w: 3.8, h: 2.0, fontSize: 14, paraSpaceAfter: 4 });
  text(s, `Source : backend/app/lifecycle/machine.py · ${int(lif.transitions_total)} transitions journalisées (metrics.json).`, { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("Simplifié : REVIEW_REQUIRED et DUPLICATE existent aussi. Les tests de sécurité tentent des sauts illégaux (NEW vers PUBLISHED) et vérifient le refus.");

  // 10 — Section Moteur ----------------------------------------------------------
  await section("03", "Le moteur IOC", "FaCogs", "Le cœur du projet : collecter, nettoyer, enrichir et noter chaque indicateur de façon explicable.");

  // 11 — Collecte : sources --------------------------------------------------------
  s = content("Collecte : sept flux réels, aucun indicateur simulé");
  const src = M.sources.filter((x) => x.ioc_count > 0);
  s.addChart(pres.charts.BAR, [{ name: "IOC", labels: src.map((x) => x.name), values: src.map((x) => x.ioc_count) }], Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 7.6, h: 5.1, barDir: "bar", chartColors: [HEX.amber], showValue: true, dataLabelPosition: "outEnd",
    showTitle: true, title: "Indicateurs apportés par source", titleFontSize: 14, titleColor: HEX.ink, valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin",
  }));
  card(s, 8.7, 1.5, 4.0, 5.1, { fill: C.background2, line: C.background2, noShadow: true });
  stat(s, 9.0, 1.7, 3.4, String(inv.synthetic_iocs), "indicateur synthétique dans l'inventaire évalué", C.accent4, 48);
  text(s, [
    { text: "Fiabilité par source (60 à 80/100), utilisée par la notation", options: { bullet: true, breakLine: true } },
    { text: "abuse.ch (URLhaus, ThreatFox, MalwareBazaar) actif avec clé valide depuis le 14/11", options: { bullet: true, breakLine: true } },
    { text: "Chaque exécution laisse un événement COLLECT dans l'audit", options: { bullet: true } },
  ], { x: 9.0, y: 3.35, w: 3.45, h: 3.1, fontSize: 14, paraSpaceAfter: 6, color: C.text2 });
  s.addNotes("Source : metrics.json, section sources. La source synthétique de laboratoire n'apporte aucun indicateur à l'inventaire évalué.");

  // 12 — Normalisation & dédup --------------------------------------------------------
  s = content("Normalisation et déduplication par empreinte");
  card(s, 0.6, 1.5, 5.6, 2.3, { fill: C.text1, line: C.text1 });
  text(s, "Empreinte unique", { x: 0.95, y: 1.7, w: 5, h: 0.4, fontSize: 15, bold: true, color: C.accent1 });
  text(s, "SHA-256(TYPE:valeur)", { x: 0.95, y: 2.15, w: 5, h: 0.6, fontSize: 24, bold: true, color: C.background1, fontFace: "Courier New" });
  text(s, "Contrainte d'unicité en base : un même indicateur ne peut exister deux fois, quelle que soit sa forme d'arrivée.", { x: 0.95, y: 2.85, w: 5, h: 0.85, fontSize: 13, color: "CBD5E1" });
  text(s, [
    { text: "IP, domaines, URL et empreintes MD5/SHA-1/SHA-256 validés strictement", options: { bullet: true, breakLine: true } },
    { text: "Valeurs invalides rejetées et journalisées, jamais stockées", options: { bullet: true, breakLine: true } },
    { text: "Un doublon met à jour la provenance et la date de dernière observation", options: { bullet: true } },
  ], { x: 0.6, y: 4.15, w: 5.6, h: 2.4, fontSize: 15, paraSpaceAfter: 8, color: C.text2 });
  const dd = [
    [int(ded.raw_items_collected), "éléments bruts collectés", C.text1],
    [int(ded.created), "indicateurs créés", C.accent2],
    [int(ded.dedup_events), "doublons écartés", C.accent1],
    [`${fr(ded.dedup_rate_pct)} %`, "taux de déduplication", C.accent1],
  ];
  dd.forEach((d, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 6.75 + col * 3.0, y = 1.5 + row * 2.55;
    card(s, x, y, 2.75, 2.3);
    stat(s, x + 0.3, y + 0.3, 2.2, d[0], d[1], d[2], 44);
  });
  text(s, `Source : metrics.json (dedup) · ${ded.invalid_rejected} valeur invalide rejetée.`, { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("Taux de déduplication = événements DEDUP / (NORMALIZE + DEDUP). Le test anti-injection fait passer une chaîne SQL malveillante : elle est rejetée, la table reste intacte.");

  // 13 — Enrichissement --------------------------------------------------------------
  s = content("Enrichissement : un fournisseur en panne n'est jamais « bénin »");
  const v = enr.by_verdict, cats = ["AlienVault OTX", "AbuseIPDB"];
  const ser = ["malicious", "suspicious", "benign", "unknown"].map((k) => ({ name: k, labels: cats, values: [v["otx/" + k] || 0, v["abuseipdb/" + k] || 0] }));
  s.addChart(pres.charts.BAR, ser, Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 7.4, h: 4.9, barDir: "bar", barGrouping: "percentStacked", valAxisLabelFormatCode: "0%", chartColors: [HEX.red, HEX.amber, HEX.green, "CBD5E1"],
    showValue: true, dataLabelPosition: "ctr", dataLabelColor: HEX.night, showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: HEX.ink,
    showTitle: true, title: "Répartition des verdicts par fournisseur (étiquettes : nombre de résultats)", titleFontSize: 14, titleColor: HEX.ink,
  }));
  const en = [
    [`${fr(enr.coverage_pct)} %`, `des IOC enrichis (${enr.iocs_enriched} / ${inv.total_iocs})`, C.accent2],
    [`${fr(enr.provider_success_pct)} %`, `d'appels réussis · ${enr.provider_errors} erreurs conservées`, C.accent1],
  ];
  en.forEach((e, i) => { card(s, 8.5, 1.5 + i * 2.1, 4.2, 1.85); stat(s, 8.8, 1.6 + i * 2.1, 3.7, e[0], e[1], e[2], 40); });
  text(s, "Cache de 24 h par fournisseur ; une erreur est stockée comme erreur, la notation la traite comme « inconnu ».", { x: 8.5, y: 5.75, w: 4.2, h: 0.75, fontSize: 13, color: C.text2 });
  s.addNotes("La majorité des verdicts OTX est « unknown » : la plateforme ne transforme pas l'absence d'information en verdict.");

  // 14 — Notation explicable ----------------------------------------------------------
  s = content("Notation explicable : cinq composantes, toutes persistées");
  const comp = sco.components_avg.slice().sort((a, b) => b.max_points - a.max_points);
  s.addChart(pres.charts.BAR, [
    { name: "Moyenne obtenue", labels: comp.map((c) => c.label), values: comp.map((c) => c.avg_points) },
    { name: "Maximum possible", labels: comp.map((c) => c.label), values: comp.map((c) => c.max_points) },
  ], Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 7.6, h: 5.0, barDir: "bar", barGrouping: "clustered", chartColors: [HEX.amber, "CBD5E1"], barGapWidthPct: 60,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: HEX.ink,
    showTitle: true, title: "Points moyens par composante (sur 100)", titleFontSize: 14, titleColor: HEX.ink, catAxisOrientation: "maxMin", valAxisMaxVal: 30,
  }));
  card(s, 8.7, 1.5, 4.0, 5.0, { fill: C.text1, line: C.text1 });
  text(s, "Le plafond sans détection", { x: 9.0, y: 1.75, w: 3.4, h: 0.4, fontSize: 16, bold: true, color: C.accent1 });
  text(s, "≈ 67 / 100", { x: 9.0, y: 2.25, w: 3.4, h: 0.9, fontSize: 44, bold: true, color: C.background1 });
  text(s, "Sans observation réelle par un capteur, un indicateur plafonne autour de 67. Publier (≥ 80) exige donc une détection, pas un empilement de sources.", { x: 9.0, y: 3.25, w: 3.4, h: 1.9, fontSize: 14, color: "CBD5E1" });
  text(s, "Anti-collusion : deux flux d'une même organisation comptent pour une seule source.", { x: 9.0, y: 5.25, w: 3.4, h: 1.0, fontSize: 13, italic: true, color: C.accent2 });
  s.addNotes(`Moyennes sur ${inv.total_iocs} IOC. Les détections observées apportent en moyenne ${fr(comp.find((c) => c.key === "observed_detections").avg_points, 2)} point : c'est voulu.`);

  // 15 — Décisions -------------------------------------------------------------------
  s = content("Décisions : la plateforme publie peu, et c'est voulu");
  const dc = sco.decisions;
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Décisions", labels: ["Publier", "Surveiller", "Rejeter"], values: [dc.publish, dc.monitor, dc.reject] }], {
    x: 0.6, y: 1.5, w: 5.4, h: 5.0, holeSize: 62, chartColors: [HEX.green, HEX.teal, HEX.grey], showPercent: false, showValue: true,
    dataLabelColor: HEX.white, dataLabelFontSize: 14, dataLabelFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 13, legendFontFace: "+mn-lt", legendColor: HEX.ink,
    showTitle: false,
  });
  text(s, String(inv.total_iocs), { x: 2.3, y: 3.1, w: 2.0, h: 0.7, fontSize: 36, bold: true, align: "center", valign: "middle" });
  text(s, "IOC notés", { x: 2.3, y: 3.75, w: 2.0, h: 0.35, fontSize: 13, align: "center", color: C.accent5 });
  const dec = [
    ["FaCheckCircle", HEX.green, `Publier : ${dc.publish}`, "Score ≥ 80 : seul l'indicateur observé par les capteurs (score 82) est publié et vérifié."],
    ["FaEye", HEX.teal, `Surveiller : ${dc.monitor}`, "Score entre 50 et 79 : conservé et observé, prêt à monter si un capteur le détecte."],
    ["FaBan", HEX.grey, `Rejeter : ${dc.reject}`, "Score < 50 : écarté mais conservé comme preuve, jamais supprimé."],
  ];
  for (let i = 0; i < 3; i++) {
    const y = 1.6 + i * 1.65;
    card(s, 6.5, y, 6.2, 1.45);
    await iconCircle(s, dec[i][0], 6.8, y + 0.37, 0.7, dec[i][1], HEX.white);
    text(s, dec[i][2], { x: 7.75, y: y + 0.2, w: 4.7, h: 0.4, fontSize: 18, bold: true });
    text(s, dec[i][3], { x: 7.75, y: y + 0.62, w: 4.75, h: 0.75, fontSize: 13, color: C.text2 });
  }
  text(s, `Score moyen ${fr(sco.avg)} · médiane ${fr(sco.median, 0)} · p95 ${fr(sco.p95, 0)} — source : metrics.json (scoring).`, { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("Un taux de publication bas n'est pas un échec : c'est le signe que les seuils ne cèdent pas à la simple accumulation de sources.");

  // 16 — Capture scoring -------------------------------------------------------------
  s = content("Chaque score se lit composante par composante");
  screenshot(s, CAP("14-scoring-detail.jpg"), 0.65, 1.5, 7.9, "Page Scoring, 14/11/2026 : classement et détail de l'indicateur publié 34.204.119.63.");
  const sc = [["Fiabilité de la source", "+18,75 / 25"], ["Fraîcheur", "+19,96 / 20"], ["Sources indépendantes", "+8,61 / 20"], ["Consensus d'enrichissement", "+20 / 20"], ["Détections observées", "+15 / 15"]];
  card(s, 9.0, 1.5, 3.7, 4.95, { fill: C.background2, line: C.background2, noShadow: true });
  text(s, "Exemple : score 82", { x: 9.25, y: 1.7, w: 3.3, h: 0.45, fontSize: 18, bold: true });
  sc.forEach((r, i) => {
    text(s, r[0], { x: 9.25, y: 2.35 + i * 0.75, w: 3.3, h: 0.3, fontSize: 13, color: C.text2 });
    text(s, r[1], { x: 9.25, y: 2.63 + i * 0.75, w: 3.3, h: 0.35, fontSize: 16, bold: true, color: C.accent1 });
  });
  s.addNotes("Le détail est persisté dans score_breakdown : le jury peut vérifier n'importe quel score sans relancer le moteur.");

  // 17 — Section Automatisation ---------------------------------------------------------
  await section("04", "Automatisation et intégrations SOC", "FaRobot", "Comment le cycle tourne seul, et comment il se branche sur de vrais outils de détection.");

  // 18 — Workflows n8n -------------------------------------------------------------------
  s = content("Huit workflows n8n, planifiés et idempotents");
  const wf = [
    ["1", "IOC Collection", "30 min", "/iocs/collect/run"], ["2", "IOC Normalization", "30 min", "/iocs/normalize/run"],
    ["3", "IOC Enrichment", "1 h", "/iocs/enrich/run"], ["4", "IOC Scoring", "30 min", "/iocs/scoring/run"],
    ["5", "IOC Publication", "1 h", "/iocs/publish/run"], ["6", "IOC Monitoring", "15 min", "/iocs/detections/ingest"],
    ["7", "IOC Expiration", "1 h", "/iocs/expire/run + /remove/run"], ["8", "IOC Reporting", "06:00", "/reports/daily"],
  ];
  const hdr = (t) => ({ text: t, options: { bold: true, color: HEX.white, fill: { color: HEX.night }, fontSize: 13 } });
  const rows = [[hdr("#"), hdr("Workflow"), hdr("Fréquence"), hdr("Route appelée (POST)")]].concat(
    wf.map((r, i) => r.map((c, j) => ({ text: c, options: { fontSize: 13, color: HEX.night, fill: { color: i % 2 ? HEX.white : HEX.mist }, fontFace: j === 3 ? "Courier New" : undefined, bold: j === 1 } }))));
  s.addTable(rows, { x: 0.6, y: 1.5, w: 7.9, colW: [0.5, 2.3, 1.3, 3.8], rowH: 0.5, border: { type: "solid", color: HEX.line, pt: 0.5 }, margin: [0.05, 0.1, 0.05, 0.1], valign: "middle" });
  const wfp = [["FaSyncAlt", "Idempotents", "rejouer un workflow ne crée ni doublon ni transition parasite"], ["FaRedo", "Reprise après panne", "un arrêt de la plateforme est rattrapé au cycle suivant"], ["FaFileCode", "Versionnés", "exportés en JSON dans workflows/n8n/, IDs stables"]];
  for (let i = 0; i < 3; i++) {
    const y = 1.5 + i * 1.55;
    await iconCircle(s, wfp[i][0], 8.95, y + 0.1, 0.65);
    text(s, wfp[i][1], { x: 9.8, y, w: 2.9, h: 0.4, fontSize: 17, bold: true });
    text(s, wfp[i][2], { x: 9.8, y: y + 0.42, w: 2.9, h: 0.95, fontSize: 13, color: C.text2 });
  }
  text(s, "Source : docs/WORKFLOWS.md.", { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("n8n ne contient aucune règle métier : il appelle les routes. On peut donc remplacer l'orchestrateur sans toucher aux décisions.");

  // 19 — Intégrations SOC -------------------------------------------------------------------
  s = content("Intégrations SOC : deux capteurs réels, un client MISP");
  const soc = [
    ["FaNetworkWired", "Suricata", "Réel", HEX.green, ["Mode IDS, rejeu PCAP par lots", "Règles générées avec des sid dédiés", `${det.by_sensor.suricata} détections rapprochées`]],
    ["FaShieldAlt", "Wazuh 4.12", "Réel", HEX.green, ["Alertes réelles lues sur un volume partagé", "Accès en lecture seule", `${det.by_sensor.wazuh} détections rapprochées`]],
    ["FaShareAlt", "MISP", "Non déployé", HEX.grey, ["Client REST complet, 18 tests simulés", "Vérification par relecture", "Sans serveur : réponse « skipped »"]],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.8, 4.0);
    await iconCircle(s, soc[i][0], x + 0.3, 1.8, 0.8, C.text1, HEX.amber);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 2.1, y: 1.95, w: 1.45, h: 0.45, rectRadius: 0.1, fill: { color: soc[i][3] }, line: { color: soc[i][3], width: 0 }, objectName: "badge" });
    text(s, soc[i][2], { x: x + 2.1, y: 1.95, w: 1.45, h: 0.45, fontSize: 12, bold: true, color: HEX.white, align: "center", valign: "middle" });
    text(s, soc[i][1], { x: x + 0.3, y: 2.85, w: 3.2, h: 0.5, fontSize: 20, bold: true });
    text(s, soc[i][4].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < 2 } })), { x: x + 0.3, y: 3.45, w: 3.25, h: 2.3, fontSize: 14, paraSpaceAfter: 6, color: C.text2 });
  }
  text(s, `${det.total} détections sur ${det.iocs_with_detections} indicateurs · ${det.false_positives} faux positif observé parmi les détections revues — source : metrics.json (detection).`, { x: 0.6, y: 5.85, w: 12.1, h: 0.4, fontSize: 14, color: C.text1, bold: true });
  s.addNotes(`Répartition : manuel ${det.by_sensor.manual}, Wazuh ${det.by_sensor.wazuh}, Suricata ${det.by_sensor.suricata}. MISP est honnêtement présenté comme non déployé.`);

  // 20 — Cycle complet mesuré ----------------------------------------------------------------
  s = content("Un cycle complet mesuré, de NEW à REMOVED");
  const fc = lif.full_cycles[0];
  const tl = ["NEW", "NORMALIZED", "ENRICHED", "SCORED", "PUBLISHED", "EXPIRED", "REMOVED"];
  s.addShape(pres.shapes.LINE, { x: 1.0, y: 3.0, w: 11.3, h: 0, line: { color: HEX.line, width: 3 }, objectName: "timeline" });
  tl.forEach((t, i) => {
    const x = 1.0 + i * (11.3 / 6);
    const col = t === "REMOVED" ? HEX.red : t === "PUBLISHED" ? HEX.green : t === "EXPIRED" ? HEX.amber : HEX.slate;
    s.addShape(pres.shapes.OVAL, { x: x - 0.22, y: 2.78, w: 0.44, h: 0.44, fill: { color: col }, line: { color: HEX.white, width: 2 }, objectName: "tl-dot" });
    text(s, t, { x: x - 0.9, y: i % 2 ? 3.4 : 2.1, w: 1.8, h: 0.4, fontSize: 13, bold: true, align: "center" });
  });
  const cy = [[`${fr(fc.seconds / 60)} min`, `durée réelle du cycle (${fr(fc.seconds)} s)`, C.accent1], [String(fc.transitions), "transitions journalisées", C.accent2], ["100 %", "des étapes vérifiées par relecture", C.accent4]];
  cy.forEach((c, i) => { const x = 0.6 + i * 4.1; card(s, x, 4.35, 3.8, 1.95); stat(s, x + 0.3, 4.5, 3.3, c[0], c[1], c[2], 40); });
  text(s, `Indicateur ${fc.value} — publication vérifiée, révocation confirmée, puis retrait. Source : metrics.json (lifecycle.full_cycles).`, { x: 0.6, y: 6.5, w: 12, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("C'est la preuve de bout en bout : un seul indicateur a parcouru tout le cycle, chaque étape étant relue avant d'être déclarée faite.");

  // 21 — Dashboard ---------------------------------------------------------------------------
  s = content("Un tableau de bord SOC de treize pages");
  screenshot(s, CAP("12-dashboard-general.jpg"), 0.65, 1.5, 7.9, "Dashboard général, 14/11/2026 : toutes les valeurs sont lues sur l'API.");
  const pages = ["Dashboard", "Inventory", "Sources", "Scoring", "Fiche IOC", "Lifecycle", "Published", "Monitoring", "Expired", "Workflows", "Audit", "Reports", "System Health"];
  card(s, 9.0, 1.5, 3.7, 4.95, { fill: C.background2, line: C.background2, noShadow: true });
  text(s, "13 routes React", { x: 9.25, y: 1.7, w: 3.3, h: 0.45, fontSize: 18, bold: true });
  [pages.slice(0, 7), pages.slice(7)].forEach((col, c) => text(s, col.map((p, i) => ({ text: p, options: { bullet: true, breakLine: i < col.length - 1 } })), { x: 9.25 + c * 1.7, y: 2.3, w: 1.65, h: 2.6, fontSize: 13, color: C.text2, paraSpaceAfter: 3 }));
  text(s, "Aucune statistique simulée : builds TypeScript et Vite sans erreur, 0 erreur console sur les 13 routes.", { x: 9.25, y: 5.15, w: 3.3, h: 1.1, fontSize: 13, italic: true, color: C.accent5 });
  s.addNotes("Le dashboard est en lecture seule sur l'API ; il ne calcule rien lui-même.");

  // 22 — Section Évaluation ---------------------------------------------------------------------
  await section("05", "Évaluation", "FaChartBar", "Toutes les mesures sont relues dans PostgreSQL par scripts/evaluate_platform.py. Les hypothèses sont étiquetées comme telles.");

  // 23 — Mesuré / hypothèse / non mesurable ------------------------------------------------------
  s = content("Trois natures de chiffres, jamais mélangées");
  const nat = [
    ["FaDatabase", HEX.green, "Mesuré", "Lu dans PostgreSQL ou l'API", ["Inventaire, scores, décisions", "Déduplication, enrichissement", "Latence, débit, cycle complet"]],
    ["FaCalculator", HEX.amber, "Hypothèse", "Modèle explicite et modifiable", ["Temps manuel de référence : 17 min par IOC", "Sert uniquement de point de comparaison", "Jamais présenté comme un historique"]],
    ["FaQuestionCircle", HEX.grey, "Non mesurable", "Faute de vérité terrain", ["Précision et rappel de la détection", "Remplacés par des proxys nommés", "Taux de publication, faux positifs revus"]],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.8, 4.9);
    await iconCircle(s, nat[i][0], x + 0.3, 1.8, 0.8, nat[i][1], HEX.white);
    text(s, nat[i][2], { x: x + 0.3, y: 2.8, w: 3.2, h: 0.5, fontSize: 22, bold: true });
    text(s, nat[i][3], { x: x + 0.3, y: 3.3, w: 3.2, h: 0.4, fontSize: 14, italic: true, color: C.accent5 });
    text(s, nat[i][4].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < 2 } })), { x: x + 0.3, y: 3.9, w: 3.25, h: 2.3, fontSize: 14, paraSpaceAfter: 6, color: C.text2 });
  }
  s.addNotes("C'est la règle centrale de l'évaluation : un chiffre sans source n'est pas présenté.");

  // 24 — Distribution des scores ---------------------------------------------------------------------
  s = content("Distribution des scores et seuils de décision");
  const dist = sco.distribution, dk = Object.keys(dist);
  s.addChart(pres.charts.BAR, [{ name: "IOC", labels: dk.map((k) => k.split(" ")[0]), values: dk.map((k) => dist[k]) }], Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 8.0, h: 5.0, barDir: "col", chartColors: [HEX.grey, HEX.teal, HEX.teal, HEX.green, HEX.green], showValue: true, dataLabelPosition: "outEnd",
    showTitle: true, title: "Nombre d'indicateurs par tranche de score", titleFontSize: 14, titleColor: HEX.ink, valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40,
    showCatAxisTitle: true, catAxisTitle: "Tranche de score", catAxisTitleFontSize: 12, catAxisTitleColor: HEX.grey,
  }));
  const ds = [[fr(sco.avg), "score moyen", C.accent1], [`${fr(sco.min, 0)} – ${fr(sco.max, 0)}`, "score minimum – maximum", C.text1], [`${fr(sco.explainability_pct, 0)} %`, "scores expliqués et persistés", C.accent4]];
  ds.forEach((d, i) => { card(s, 9.1, 1.5 + i * 1.7, 3.6, 1.5); stat(s, 9.4, 1.55 + i * 1.7, 3.1, d[0], d[1], d[2], 36); });
  s.addNotes("Rejet < 50, surveillance 50 à 79, publication ≥ 80. La masse se concentre juste au-dessus de 50 : beaucoup de signaux faibles, peu de signaux confirmés.");

  // 25 — Performance --------------------------------------------------------------------------------
  s = content("Performance : moins de 2 minutes par indicateur à chaud");
  const pf = [
    [`${fr(perf.hot_latency_avg_s)} s`, `latence moyenne ingestion → score (${perf.hot_latency_iocs} IOC à chaud)`, C.accent1],
    [`${fr(perf.hot_batch_throughput_ioc_per_s, 2)}`, "indicateurs par seconde sur le lot à chaud", C.accent2],
    [int(perf.scoring_engine.scores_per_second), `scores par seconde, moteur seul (${fr(perf.scoring_engine.us_per_score)} µs/score)`, C.accent6],
  ];
  pf.forEach((p, i) => { const x = 0.6 + i * 4.1; card(s, x, 1.5, 3.8, 2.4); stat(s, x + 0.3, 1.75, 3.3, p[0], p[1], p[2], 48); });
  card(s, 0.6, 4.3, 12.1, 2.0, { fill: C.background2, line: C.background2, noShadow: true });
  await iconCircle(s, "FaExclamationTriangle", 0.95, 4.75, 0.9, C.accent1, HEX.night);
  text(s, `Backlog exclu de la latence : ${perf.backlog_iocs} indicateurs`, { x: 2.15, y: 4.55, w: 10.3, h: 0.45, fontSize: 18, bold: true });
  text(s, `Ils ont été notés après un arrêt volontaire de la plateforme (07/11 → 14/11), avec ${fr(perf.backlog_latency_avg_h)} h d'attente en moyenne. Ce délai mesure l'indisponibilité, pas la performance : il est présenté à part plutôt que mélangé à la moyenne.`, { x: 2.15, y: 5.05, w: 10.3, h: 1.1, fontSize: 14, color: C.text2 });
  s.addNotes("Source : metrics.json, section performance. Séparer chaud et backlog évite de flatter ou de noircir le résultat.");

  // 26 — Automatisation hypothèse vs mesure ------------------------------------------------------------
  s = content("Gain d'automatisation : une comparaison honnête");
  s.addChart(pres.charts.BAR, [{ name: "min / IOC", labels: ["Analyste manuel (hypothèse)", "Plateforme (mesuré)"], values: [aut.manual_minutes_per_ioc, aut.automated_minutes_per_ioc] }], Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 6.6, h: 5.0, barDir: "col", chartColors: [HEX.grey, HEX.amber], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    showTitle: true, title: "Minutes par indicateur", titleFontSize: 14, titleColor: HEX.ink, valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 70,
  }));
  card(s, 7.7, 1.5, 5.0, 2.3, { fill: C.text1, line: C.text1 });
  text(s, `× ${fr(aut.time_reduction_factor)}`, { x: 8.0, y: 1.65, w: 4.4, h: 1.0, fontSize: 54, bold: true, color: C.accent1 });
  text(s, "facteur de réduction — calculé contre une HYPOTHÈSE, pas contre un historique", { x: 8.0, y: 2.75, w: 4.4, h: 0.9, fontSize: 14, color: C.background1 });
  text(s, [
    { text: `Modèle manuel : ${fr(aut.manual_minutes_per_ioc, 0)} min = collecte 1 + normalisation 2 + doublons 2 + enrichissement 4 + notation 3 + publication 4 + audit 1`, options: { bullet: true, breakLine: true } },
    { text: `Pour l'inventaire : ${fr(aut.manual_hours_for_inventory)} h (hypothèse) contre ${fr(aut.automated_hours_for_inventory, 2)} h (mesuré)`, options: { bullet: true, breakLine: true } },
    { text: "Modèle modifiable dans scripts/evaluate_platform.py (MANUAL_BASELINE)", options: { bullet: true } },
  ], { x: 7.7, y: 4.1, w: 5.0, h: 2.4, fontSize: 14, paraSpaceAfter: 6, color: C.text2 });
  s.addNotes("Insister : le temps manuel est un modèle explicite. Seul le temps plateforme est mesuré en base.");

  // 27 — Section Sécurité ------------------------------------------------------------------------------
  await section("06", "Sécurité, tests et bilan", "FaLock", "Ce qui protège la plateforme, comment c'est prouvé, et ce qui reste ouvert.");

  // 28 — Sécurité + AWS ---------------------------------------------------------------------------------
  s = content("Sécurité : chaque contrôle a sa preuve automatisée");
  const thr = [
    ["Injection SQL via un IOC", "validation stricte + requêtes paramétrées", "faible"],
    ["Empoisonnement de l'inventaire", "anti-collusion + seuil 80 + détection requise", "moyen"],
    ["Falsification de l'audit", "trigger append-only + tests UPDATE/DELETE", "faible"],
    ["Fuite de secrets", ".gitignore + tests sur git ls-files et motifs", "faible"],
    ["Exposition réseau", "ports 127.0.0.1 testés + tunnel SSH", "faible"],
    ["Retrait non confirmé", "REMOVED refusé sans révocation relue", "faible"],
  ];
  const risk = (r) => ({ text: r, options: { fontSize: 13, bold: true, align: "center", color: HEX.white, fill: { color: r === "faible" ? HEX.green : HEX.amber } } });
  const trows = [[hdr("Menace"), hdr("Contrôle"), hdr("Résiduel")]].concat(thr.map((r, i) => [
    { text: r[0], options: { fontSize: 13, bold: true, color: HEX.night, fill: { color: i % 2 ? HEX.white : HEX.mist } } },
    { text: r[1], options: { fontSize: 13, color: HEX.night, fill: { color: i % 2 ? HEX.white : HEX.mist } } },
    risk(r[2]),
  ]));
  s.addTable(trows, { x: 0.6, y: 1.5, w: 8.0, colW: [2.9, 3.9, 1.2], rowH: 0.62, border: { type: "solid", color: HEX.line, pt: 0.5 }, margin: [0.05, 0.1, 0.05, 0.1], valign: "middle" });
  card(s, 9.0, 1.5, 3.7, 4.9, { fill: C.text1, line: C.text1 });
  s.addImage({ data: await icon("FaAws", HEX.amber), x: 9.3, y: 1.75, w: 0.8, h: 0.8, altText: "AWS" });
  text(s, "Déploiement EC2", { x: 9.3, y: 2.65, w: 3.2, h: 0.45, fontSize: 18, bold: true, color: C.background1 });
  text(s, [
    { text: "Instance t2.large existante réutilisée, aucune ressource créée", options: { bullet: true, breakLine: true } },
    { text: "Aucun port applicatif public : accès par tunnel SSH", options: { bullet: true, breakLine: true } },
    { text: "SSH restreint à l'IP de l'administrateur (/32)", options: { bullet: true, breakLine: true } },
    { text: "≈ 0,093 $/h quand l'instance tourne", options: { bullet: true } },
  ], { x: 9.3, y: 3.15, w: 3.2, h: 3.1, fontSize: 13, color: "CBD5E1", paraSpaceAfter: 6 });
  text(s, "Source : docs/SECURITY.md (modèle de menace) et docs/AWS_DEPLOYMENT.md.", { x: 0.6, y: 6.5, w: 8, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  s.addNotes("Les deux inventaires sont distincts : 217 IOC en local, 94 sur EC2. Ils ne sont jamais additionnés.");

  // 29 — Tests + limites ---------------------------------------------------------------------------------
  s = content("192 tests sur un vrai PostgreSQL, et des limites assumées");
  const tm = [["normalization", 35], ["security", 27], ["lifecycle", 23], ["ingest", 22], ["scoring", 19], ["misp", 18], ["providers", 16], ["abusech", 14], ["pipeline", 11], ["health", 7]];
  s.addChart(pres.charts.BAR, [{ name: "Tests", labels: tm.map((t) => t[0]), values: tm.map((t) => t[1]) }], Object.assign(chartBase(), {
    x: 0.6, y: 1.5, w: 5.9, h: 5.0, barDir: "bar", chartColors: [HEX.teal], showValue: true, dataLabelPosition: "outEnd", catAxisOrientation: "maxMin",
    showTitle: true, title: "Tests par module (test_*.py)", titleFontSize: 14, titleColor: HEX.ink, valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 45,
  }));
  const lim = [
    ["Précision / rappel", "pas de vérité terrain annotée"],
    ["MISP", "client testé, serveur non déployé"],
    ["Authentification API", "absente : usage local uniquement"],
    ["Frontend", "pas de tests unitaires ni de CI"],
  ];
  text(s, "Limites assumées", { x: 7.0, y: 1.5, w: 5.7, h: 0.45, fontSize: 18, bold: true });
  for (let i = 0; i < 4; i++) {
    const y = 2.1 + i * 1.08;
    card(s, 7.0, y, 5.7, 0.92, { fill: C.background2, line: C.background2, noShadow: true });
    await iconCircle(s, "FaExclamationCircle", 7.2, y + 0.18, 0.56, C.accent1, HEX.night);
    text(s, lim[i][0], { x: 7.95, y: y + 0.1, w: 4.6, h: 0.35, fontSize: 15, bold: true });
    text(s, lim[i][1], { x: 7.95, y: y + 0.47, w: 4.6, h: 0.35, fontSize: 13, color: C.text2 });
  }
  s.addNotes("Les tests attaquent la plateforme : audit modifié, saut d'état, injection, port exposé, secret commité. Les limites sont écrites, pas cachées.");

  // 30 — Bilan -------------------------------------------------------------------------------------------------
  s = pres.addSlide({ masterName: "COVER", sectionTitle: "Sécurité, tests et bilan" });
  await decor(s, "FaCheckCircle");
  text(s, "BILAN", { x: 0.9, y: 0.9, w: 6, h: 0.4, fontSize: 16, bold: true, color: C.accent1, charSpacing: 2 });
  text(s, "Une usine à IOC qui prouve ce qu'elle affirme", { x: 0.9, y: 1.4, w: 7.7, h: 1.3, fontSize: 36, bold: true, color: C.background1 });
  const bl = [
    ["Démontré", ["Cycle complet sur données réelles, jusqu'au retrait vérifié", "Notation 100 % explicable et auditée", "192 tests, aucun port public exposé"]],
    ["Prochaines étapes", ["Déployer MISP et authentifier l'API", "Annoter une vérité terrain (précision / rappel)", "Ajouter une CI et des tests frontend"]],
  ];
  bl.forEach((b, i) => {
    const x = 0.9 + i * 4.1;
    text(s, b[0], { x, y: 3.05, w: 3.8, h: 0.45, fontSize: 18, bold: true, color: i ? C.accent2 : C.accent4 });
    text(s, b[1].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < 2 } })), { x, y: 3.6, w: 3.8, h: 2.3, fontSize: 15, color: "CBD5E1", paraSpaceAfter: 8 });
  });
  text(s, "Merci — questions ?", { x: 0.9, y: 6.3, w: 6, h: 0.5, fontSize: 20, bold: true, color: C.background1 });
  s.addNotes("Conclusion : la valeur du projet est la confiance dans l'état affiché. Ouvrir sur les questions du jury.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("OK", OUT, pres.slides.length, "slides");
})().catch((e) => { console.error(e); process.exit(1); });
