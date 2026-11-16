// Présentation de soutenance — SOAR IOC Factory v0.2 (14 diapositives).
// Données : reports/v2/facts.json (aucun chiffre saisi à la main hors faits mesurés).
// Usage : NODE_PATH=<node_modules avec pptxgenjs, react, react-dom, react-icons, sharp>
//         node scripts/build_presentation_v2.js "<racine>" "<chemin apply_theme.js>"
// Sortie : reports/PRESENTATION_V2_SOAR_IOC_FACTORY.pptx
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = process.argv[2];
const { applyTheme } = require(process.argv[3]);
const OUT = path.join(ROOT, "reports", "PRESENTATION_V2_SOAR_IOC_FACTORY.pptx");
const F = JSON.parse(fs.readFileSync(path.join(ROOT, "reports/v2/facts.json"), "utf8"));
const S = F.local.stats;
const AWS = F.aws || {};
const SHOT = (f) => path.join(ROOT, "capture", "2026-11-16", f);
const nf = (n) => new Intl.NumberFormat("fr-FR").format(n).replace(/ /g, " ");

// ------------------------------------------------------------------ theme --
const HEX = {
  bg: "0B0F14", card: "151B24", card2: "1B2330", line: "2E3948",
  text: "E7ECF2", muted: "9AA6B6", teal: "2CC2A6", amber: "E0A43B",
  red: "F0605D", blue: "5AA2F5", violet: "A48AF5", slate: "7D8BA0",
};
const THEME = {
  name: "SOAR IOC Factory v0.2",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: HEX.bg, lt1: HEX.text, dk2: HEX.card, lt2: HEX.muted,
    accent1: HEX.teal, accent2: HEX.blue, accent3: HEX.amber, accent4: HEX.red,
    accent5: HEX.violet, accent6: HEX.slate, hlink: HEX.teal, folHlink: HEX.violet,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "SOAR IOC Factory v0.2 — Soutenance";
pres.author = "Souhayl Chouaibi";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ------------------------------------------------------------------ icons --
async function icon(Comp, color = "#2CC2A6", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

async function cropTop(file, ratio = 16 / 10) {
  const img = sharp(file);
  const meta = await img.metadata();
  const h = Math.min(meta.height, Math.round(meta.width / ratio));
  const buf = await img.extract({ left: 0, top: 0, width: meta.width, height: h }).png().toBuffer();
  return { data: "image/png;base64," + buf.toString("base64"), ratio: meta.width / h };
}

// ---------------------------------------------------------------- layouts --
pres.defineSlideMaster({
  title: "SOAR_TITLE",
  background: { color: HEX.bg },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 11.7, h: 1.4, fontSize: 54, bold: true, color: HEX.text, align: "left", valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.5, w: 11.7, h: 0.9, fontSize: 22, color: C.accent1, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SOAR_CONTENT",
  background: { color: HEX.bg },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 30, bold: true, color: HEX.text, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "SOAR IOC Factory · v0.2", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
});

function content(section, title) {
  const s = pres.addSlide({ masterName: "SOAR_CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}

function card(slide, x, y, w, h, name, fill = HEX.card) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: HEX.line, width: 0.75 }, objectName: name,
  });
}

async function iconCircle(slide, x, y, Comp, name, d = 0.62, fill = HEX.card2, color = "#2CC2A6") {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: HEX.teal, width: 1 }, objectName: `${name}-circle` });
  slide.addImage({ data: await icon(Comp, color), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: name, objectName: `${name}-icon` });
}

function stat(slide, x, y, w, value, label, color = HEX.teal, size = 44) {
  slide.addText(String(value), { x, y, w, h: 0.85, fontSize: size, bold: true, color, margin: 0, isTextBox: true, objectName: `stat-${label}` });
  slide.addText(label, { x, y: y + 0.85, w, h: 0.55, fontSize: 13, color: HEX.muted, margin: 0, valign: "top", isTextBox: true });
}

function shot(slide, data, x, y, w, ratio, name) {
  const h = w / ratio;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: 0.06, fill: { color: HEX.line }, line: { color: HEX.line }, objectName: `${name}-frame` });
  slide.addImage({ data, x, y, w, h, altText: name, objectName: name });
  return h;
}

const CHART_TEXT = { catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", legendFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 11, dataLabelColor: HEX.text, legendColor: HEX.muted, legendFontSize: 11 };

// ================================================================= slides ==
async function build() {
  const testsPassed = F.tests.reduce((n, t) => n + t.passed, 0);
  const before = F.security_scans.reduce((n, s) => n + s.before, 0);

  // 1 — titre ---------------------------------------------------------------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "SOAR_TITLE", sectionTitle: "Introduction" });
  s.addText("SOAR IOC Factory", { placeholder: "title" });
  s.addText("v0.2 — une plateforme SOC de Threat Intelligence, prouvée par ses données", { placeholder: "body" });
  await iconCircle(s, 0.8, 0.8, fa.FaShieldAlt, "logo", 0.8);
  const big = [[nf(S.total_iocs), "IOC en base locale"], [nf(testsPassed), "tests réussis"], ["0", "constat de sécurité ouvert"], ["8/8", "e2e sur AWS"]];
  big.forEach(([v, l], i) => stat(s, 0.8 + i * 3.0, 5.0, 2.8, v, l, i === 2 ? HEX.teal : HEX.text, 40));
  s.addText("Projet 3 · Cyber Threat Intelligence · 16 novembre 2026", { x: 0.8, y: 6.75, w: 8, h: 0.35, fontSize: 12, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("Présentation de la version 0.2. Message principal : la plateforme est désormais exploitable par une équipe SOC, sécurisée, déployée sur AWS, et chaque chiffre affiché vient de la base de données.");

  // 2 — chaîne --------------------------------------------------------------
  s = content("Introduction", "Une usine à IOC, de la collecte au retrait vérifié");
  const stages = F.local.funnel.stages;
  stages.forEach((st, i) => {
    const col = i % 5, row = Math.floor(i / 5);
    const x = 0.6 + col * 2.45, y = 1.55 + row * 2.35;
    card(s, x, y, 2.2, 2.0, `stage-${st.key}`, st.count ? HEX.card : "10151C");
    s.addText(`${i + 1}`, { x: x + 0.2, y: y + 0.18, w: 0.5, h: 0.4, fontSize: 14, bold: true, color: HEX.teal, margin: 0, isTextBox: true });
    s.addText(st.label, { x: x + 0.2, y: y + 0.55, w: 1.9, h: 0.45, fontSize: 15, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(nf(st.count), { x: x + 0.2, y: y + 1.0, w: 1.9, h: 0.6, fontSize: 28, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(st.current !== null ? `actuellement ${nf(st.current)}` : "opérations tracées", { x: x + 0.2, y: y + 1.55, w: 1.9, h: 0.3, fontSize: 11, color: HEX.muted, margin: 0, isTextBox: true });
  });
  s.addText("Chaque compteur est adossé à sa table de preuve (audit_logs, lifecycle_events) — aucune valeur estimée.", { x: 0.6, y: 6.35, w: 12.1, h: 0.4, fontSize: 13, italic: true, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("Les dix étapes du cycle de vie. Les chiffres sont ceux de la base locale au moment de la génération : collecte, normalisation, déduplication, enrichissement, score, décision, publication, surveillance, expiration et retrait vérifié.");

  // 3 — audit ---------------------------------------------------------------
  pres.addSection({ title: "Audit et sécurité" });
  s = content("Audit et sécurité", "L'audit initial a révélé 11 constats, dont 4 critiques ou élevés");
  [["1", "Critique", HEX.red], ["3", "Élevée", HEX.amber], ["5", "Moyenne", HEX.blue], ["2", "Faible", HEX.slate]].forEach(([v, l, c], i) => {
    card(s, 0.6 + i * 1.5, 1.6, 1.35, 1.7, `sev-${l}`);
    s.addText(v, { x: 0.6 + i * 1.5, y: 1.75, w: 1.35, h: 0.9, fontSize: 44, bold: true, color: c, align: "center", margin: 0, isTextBox: true });
    s.addText(l, { x: 0.6 + i * 1.5, y: 2.65, w: 1.35, h: 0.4, fontSize: 13, color: HEX.muted, align: "center", margin: 0, isTextBox: true });
  });
  s.addText("Toutes corrigées en v0.2, chacune couverte par un test ou un outil d'analyse.", { x: 0.6, y: 3.6, w: 5.8, h: 0.8, fontSize: 15, color: HEX.text, margin: 0, isTextBox: true });
  const findings = [
    [fa.FaLockOpen, "API entièrement ouverte", "aucune authentification, écritures comprises"],
    [fa.FaFolderOpen, "Traversée de chemin", "lecture de fichiers arbitraires via ?path="],
    [fa.FaUserSecret, "Acteur d'audit falsifiable", "identité fournie par le client"],
    [fa.FaBug, "Dépendances et images vulnérables", "Starlette, zlib, wheel ; nginx en root"],
  ];
  for (let i = 0; i < findings.length; i++) {
    const [ic, t, d] = findings[i];
    const y = 1.6 + i * 1.2;
    await iconCircle(s, 7.0, y, ic, `finding-${i}`, 0.7, HEX.card2, "#F0605D");
    s.addText(t, { x: 7.9, y, w: 4.8, h: 0.4, fontSize: 17, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(d, { x: 7.9, y: y + 0.4, w: 4.8, h: 0.4, fontSize: 13, color: HEX.muted, margin: 0, isTextBox: true });
  }
  s.addNotes("Avant de modifier le code, audit complet : architecture, API, modèles, workflows, intégrations, frontend, tests, Docker. Onze constats, dont un critique (API ouverte) et trois élevés.");

  // 4 — accès ---------------------------------------------------------------
  s = content("Audit et sécurité", "Un accès contrôlé de bout en bout");
  const ctrls = [
    [fa.FaKey, "Argon2id", "mots de passe ≥ 12 caractères, 3 classes"],
    [fa.FaIdBadge, "JWT 60 min", "compte relu à chaque requête : révocation immédiate"],
    [fa.FaUsersCog, "3 rôles", "lecteur · analyste · administrateur"],
    [fa.FaUserLock, "Anti force brute", "verrouillage après 5 échecs + 10 req/min/IP"],
    [fa.FaRobot, "Clé de service n8n", "comparaison à temps constant, jamais dans les JSON"],
    [fa.FaFingerprint, "Audit infalsifiable", "l'acteur vient du jeton, jamais de la requête"],
  ];
  for (let i = 0; i < ctrls.length; i++) {
    const [ic, t, d] = ctrls[i];
    const x = 0.6 + (i % 3) * 4.1, y = 1.6 + Math.floor(i / 3) * 2.45;
    card(s, x, y, 3.85, 2.15, `ctrl-${i}`);
    await iconCircle(s, x + 0.3, y + 0.3, ic, `ctrl-icon-${i}`);
    s.addText(t, { x: x + 0.3, y: y + 1.05, w: 3.3, h: 0.45, fontSize: 18, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(d, { x: x + 0.3, y: y + 1.5, w: 3.3, h: 0.55, fontSize: 13, color: HEX.muted, margin: 0, valign: "top", isTextBox: true });
  }
  s.addNotes("Six contrôles d'accès, chacun prouvé par un test HTTP dans test_auth_api.py (22 tests). En production, l'API refuse de démarrer avec un secret faible ou l'authentification désactivée.");

  // 5 — analyses ------------------------------------------------------------
  s = content("Audit et sécurité", `${before} constats de sécurité traités, 0 ouvert`);
  s.addChart(pres.charts.BAR, [
    { name: "Avant", labels: F.security_scans.map((x) => x.tool), values: F.security_scans.map((x) => x.before) },
    { name: "Après", labels: F.security_scans.map((x) => x.tool), values: F.security_scans.map((x) => x.after) },
  ], {
    x: 0.6, y: 1.5, w: 7.6, h: 5.1, barDir: "col", barGrouping: "clustered", chartColors: [HEX.red, HEX.teal],
    showValue: true, dataLabelPosition: "outEnd", showLegend: true, legendPos: "t",
    valGridLine: { color: HEX.line, size: 0.5 }, catGridLine: { style: "none" }, valAxisMaxVal: 26, valAxisMinVal: 0,
    showTitle: false, ...CHART_TEXT, objectName: "chart-security",
  });
  const scanList = [["Bandit", "1 faux positif annoté"], ["pip-audit", "Starlette 1.10 · PyJWT 2.15"], ["Trivy", "image durcie, nginx non-root"], ["OWASP ZAP", "0 FAIL · 60 PASS"]];
  card(s, 8.6, 1.5, 4.1, 5.1, "scan-card");
  scanList.forEach(([t, d], i) => {
    s.addText(t, { x: 8.9, y: 1.8 + i * 1.15, w: 3.6, h: 0.4, fontSize: 17, bold: true, color: HEX.teal, margin: 0, isTextBox: true });
    s.addText(d, { x: 8.9, y: 2.2 + i * 1.15, w: 3.6, h: 0.4, fontSize: 13, color: HEX.text, margin: 0, isTextBox: true });
  });
  s.addNotes("Bandit, pip-audit, npm audit, Trivy (image et configuration) et OWASP ZAP ont été exécutés. Les 24 avis pip-audit venaient de Starlette (préexistant) et de PyJWT, corrigés par montée de version. ZAP ne remonte que deux avertissements documentés.");

  // 6 — console -------------------------------------------------------------
  pres.addSection({ title: "Console SOC" });
  s = content("Console SOC", "Une console SOC pensée pour l'analyste");
  const ov = await cropTop(SHOT("v2-02-overview.png"), 1440 / 900);
  shot(s, ov.data, 0.6, 1.45, 8.4, ov.ratio, "overview-shot");
  const feats = [
    [fa.FaSearch, "Recherche Ctrl K", "IOC et sources, au clavier"],
    [fa.FaBell, "Notifications réelles", "échecs, détections, revues"],
    [fa.FaCheckDouble, "Confirmation", "avant toute action sensible"],
    [fa.FaMobileAlt, "Responsive", "bureau, tablette, mobile"],
  ];
  for (let i = 0; i < feats.length; i++) {
    const [ic, t, d] = feats[i];
    const y = 1.5 + i * 1.3;
    await iconCircle(s, 9.4, y, ic, `feat-${i}`, 0.6);
    s.addText(t, { x: 10.15, y, w: 2.6, h: 0.35, fontSize: 16, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(d, { x: 10.15, y: y + 0.36, w: 2.6, h: 0.5, fontSize: 13, color: HEX.muted, margin: 0, valign: "top", isTextBox: true });
  }
  s.addNotes("Design system établi avec ui-ux-pro-max : style minimaliste suisse, palette graphite et accent sarcelle, aucune couleur fluorescente. 13 pages chargées à la demande, toutes connectées à l'API.");

  // 7 — détection & dossier -------------------------------------------------
  s = content("Console SOC", "Détecter, qualifier, prouver");
  const det = await cropTop(SHOT("v2-03-detection-center.png"), 1440 / 900);
  const ioc = await cropTop(SHOT("v2-05-ioc-detail.png"), 1440 / 900);
  shot(s, det.data, 0.6, 1.5, 5.9, det.ratio, "detection-shot");
  shot(s, ioc.data, 6.8, 1.5, 5.9, ioc.ratio, "ioc-shot");
  s.addText([{ text: "Detection Center", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "sévérité déclarée par le capteur, preuve brute conservée, qualification confirmée / faux positif", options: { color: HEX.muted } }], { x: 0.6, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addText([{ text: "Dossier de preuve d'un IOC", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "score justifié composante par composante, cycle de vie, provenance, publications, audit", options: { color: HEX.muted } }], { x: 6.8, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Le Detection Center rapproche les alertes Suricata et Wazuh de l'inventaire. Un faux positif qualifié pénalise le score au calcul suivant. Le dossier IOC regroupe toute la preuve d'un indicateur.");

  // 8 — données -------------------------------------------------------------
  pres.addSection({ title: "Données et automatisation" });
  s = content("Données et automatisation", "Des chiffres issus de PostgreSQL, jamais simulés");
  const order = ["NORMALIZED", "MONITORED", "REJECTED", "PUBLISHED", "REMOVED"];
  const labels = { NORMALIZED: "Normalisés", MONITORED: "Surveillés", REJECTED: "Rejetés", PUBLISHED: "Publiés", REMOVED: "Retirés" };
  const present = order.filter((k) => S.by_status[k]);
  s.addChart(pres.charts.BAR, [{ name: "IOC", labels: present.map((k) => labels[k]), values: present.map((k) => S.by_status[k]) }], {
    x: 0.6, y: 1.5, w: 7.6, h: 5.1, barDir: "bar", chartColors: [HEX.teal], showValue: true, dataLabelPosition: "outEnd",
    showLegend: false, valGridLine: { color: HEX.line, size: 0.5 }, catGridLine: { style: "none" },
    showTitle: true, title: "Inventaire local par statut", titleColor: HEX.text, titleFontSize: 14, ...CHART_TEXT, objectName: "chart-status",
  });
  stat(s, 8.7, 1.6, 4, nf(S.total_iocs), "IOC en base locale", HEX.text);
  stat(s, 8.7, 3.25, 4, nf(S.by_status.NORMALIZED || 0), "IOC réels collectés le 16/11, en attente d'enrichissement", HEX.amber);
  stat(s, 8.7, 4.9, 4, nf(S.synthetic_iocs), "IOC synthétique (marqueur LAB sinon)", HEX.teal);
  s.addNotes("Toutes les valeurs viennent de la base. Une collecte manuelle du 16/11 a ajouté des IOC réels : ils restent au statut NORMALIZED tant que l'enrichissement n'a pas tourné, sans score anticipé.");

  // 9 — automatisation ------------------------------------------------------
  s = content("Données et automatisation", "Une automatisation n8n authentifiée et mesurée");
  const auto = await cropTop(SHOT("v2-09-automation.png"), 1440 / 900);
  shot(s, auto.data, 0.6, 1.5, 7.6, auto.ratio, "automation-shot");
  stat(s, 8.7, 1.6, 4, "8", "workflows n8n avec clé de service", HEX.text);
  stat(s, 8.7, 3.25, 4, "success", "exécution réelle du workflow 8 (local et AWS)", HEX.teal, 36);
  stat(s, 8.7, 4.9, 4, nf(F.local.runs.total), "exécutions de pipeline tracées, durée mesurée depuis la v0.2", HEX.text);
  s.addNotes("Les workflows envoient X-API-Key, lu dans l'environnement n8n, et X-Actor pour signer l'audit. Chaque exécution enregistre sa durée réelle ; les anciennes sont affichées « non mesurée ».");

  // 10 — AWS ----------------------------------------------------------------
  pres.addSection({ title: "Déploiement et qualité" });
  s = content("Déploiement et qualité", "Déployée sur AWS sans aucun port public");
  const steps = ["Sauvegarde pg_dump + dossier v0.1 conservé", "Code v0.2 + secrets générés sur le serveur", `Migration Alembic ${AWS.alembic || ""}`, "Reconstruction : 4 conteneurs healthy", "8 workflows importés, exécution réelle OK", "Playwright via tunnel SSH : 8/8"];
  steps.forEach((t, i) => {
    const y = 1.55 + i * 0.82;
    s.addShape(pres.shapes.OVAL, { x: 0.6, y, w: 0.5, h: 0.5, fill: { color: HEX.teal }, line: { color: HEX.teal }, objectName: `step-${i}` });
    s.addText(String(i + 1), { x: 0.6, y, w: 0.5, h: 0.5, fontSize: 14, bold: true, color: HEX.bg, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(t, { x: 1.3, y, w: 4.6, h: 0.5, fontSize: 15, color: HEX.text, valign: "middle", margin: 0, isTextBox: true });
  });
  const aw = await cropTop(SHOT("aws-v2-02-overview.png"), 1440 / 900);
  shot(s, aw.data, 6.3, 1.5, 6.4, aw.ratio, "aws-shot");
  s.addText([{ text: "0 $", options: { bold: true, color: HEX.teal, fontSize: 22 } }, { text: "  de surcoût : même t2.large (≈ 2,23 $/jour allumée), mêmes 4 conteneurs", options: { color: HEX.muted, fontSize: 13 } }], { x: 6.3, y: 5.75, w: 6.4, h: 0.6, margin: 0, isTextBox: true });
  s.addNotes("Déploiement sur l'instance EC2 du Learner Lab : sauvegarde, migration, reconstruction, import des workflows. Tous les services écoutent sur 127.0.0.1, l'accès se fait par tunnel SSH. Aucun coût supplémentaire.");

  // 11 — tests --------------------------------------------------------------
  s = content("Déploiement et qualité", `${nf(testsPassed)} tests réussis et 5 défauts réels corrigés avant livraison`);
  F.tests.forEach((t, i) => {
    card(s, 0.6 + i * 3.05, 1.5, 2.85, 1.9, `test-${i}`);
    s.addText(`${t.passed}/${t.count}`, { x: 0.8 + i * 3.05, y: 1.65, w: 2.5, h: 0.85, fontSize: 36, bold: true, color: HEX.teal, margin: 0, isTextBox: true });
    s.addText(t.suite, { x: 0.8 + i * 3.05, y: 2.5, w: 2.5, h: 0.75, fontSize: 13, color: HEX.muted, margin: 0, valign: "top", isTextBox: true });
  });
  const defects = [
    "Collision /health : la page affichait le JSON de la sonde au rechargement",
    "Sources « Connecté » avec 0 collecte enregistrée → historique d'audit",
    "Erreur 500 sur /detections pour les alertes manuelles",
    "Adresse cliente non IP → échec d'écriture INET au login",
    "Navigation non étiquetée et polices bloquées par la CSP",
  ];
  s.addText(defects.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < defects.length - 1 } })), { x: 0.6, y: 3.75, w: 12.1, h: 2.8, fontSize: 15, color: HEX.text, paraSpaceAfter: 8, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Tests backend sur un vrai PostgreSQL, tests de composants Vitest, scénarios Playwright sur la pile réelle en local puis sur AWS. Ils ont révélé cinq défauts réels, tous corrigés et couverts par un test de régression.");

  // 12 — limites ------------------------------------------------------------
  s = content("Déploiement et qualité", "Limites assumées et prochaines étapes");
  card(s, 0.6, 1.5, 5.9, 5.1, "limits");
  card(s, 6.8, 1.5, 5.9, 5.1, "next");
  await iconCircle(s, 0.9, 1.75, fa.FaExclamationTriangle, "limits-icon", 0.6, HEX.card2, "#E0A43B");
  await iconCircle(s, 7.1, 1.75, fa.FaRoute, "next-icon", 0.6);
  s.addText("Hors d'atteinte ici", { x: 1.7, y: 1.8, w: 4.6, h: 0.5, fontSize: 19, bold: true, color: HEX.text, margin: 0, isTextBox: true });
  s.addText("Prochaines étapes", { x: 7.9, y: 1.8, w: 4.6, h: 0.5, fontSize: 19, bold: true, color: HEX.text, margin: 0, isTextBox: true });
  const lim = ["MISP réel : aucun serveur ni clé (« Configuration manquante »)", "Capteurs Suricata/Wazuh non démarrés pendant la session", "Anciennes alertes Wazuh sans niveau → « non fournie »", "Jeton en sessionStorage, limiteur par processus"];
  const nxt = ["MISP de laboratoire pour la publication vérifiée", "Profils Suricata et Wazuh pour une démo en direct", "Rôles PostgreSQL séparés, rate limit au proxy", "Jetons de rafraîchissement avec révocation"];
  s.addText(lim.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < lim.length - 1 } })), { x: 0.9, y: 2.7, w: 5.3, h: 3.6, fontSize: 15, color: HEX.muted, paraSpaceAfter: 10, margin: 0, valign: "top", isTextBox: true });
  s.addText(nxt.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < nxt.length - 1 } })), { x: 7.1, y: 2.7, w: 5.3, h: 3.6, fontSize: 15, color: HEX.text, paraSpaceAfter: 10, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Ce qui n'a pas pu être finalisé faute d'accès est affiché honnêtement par la plateforme, sans simulation. Les prochaines étapes visent à exercer MISP et les capteurs en conditions réelles.");

  // 13 — conclusion ---------------------------------------------------------
  pres.addSection({ title: "Conclusion" });
  s = pres.addSlide({ masterName: "SOAR_TITLE", sectionTitle: "Conclusion" });
  s.addText("Cohérente, sécurisée, démontrable", { placeholder: "title" });
  s.addText("Chaque chiffre vient de la base · chaque action est authentifiée, confirmée et journalisée", { placeholder: "body" });
  const take = [[fa.FaDatabase, "Données réelles", "aucune valeur simulée"], [fa.FaShieldAlt, "Sécurité vérifiée", "0 constat ouvert"], [fa.FaCloud, "Local et AWS", "e2e au vert sur les deux"]];
  for (let i = 0; i < take.length; i++) {
    const [ic, t, d] = take[i];
    const x = 0.8 + i * 4.0;
    await iconCircle(s, x, 4.9, ic, `take-${i}`, 0.7);
    s.addText(t, { x: x + 0.9, y: 4.9, w: 3.0, h: 0.4, fontSize: 18, bold: true, color: HEX.text, margin: 0, isTextBox: true });
    s.addText(d, { x: x + 0.9, y: 5.3, w: 3.0, h: 0.4, fontSize: 14, color: HEX.muted, margin: 0, isTextBox: true });
  }
  s.addNotes("Conclusion : la v0.2 livre une plateforme cohérente et démontrable devant un jury. Rapport technique complet : reports/RAPPORT_V2_SOAR_IOC_FACTORY.docx.");

  // 14 — questions ----------------------------------------------------------
  s = pres.addSlide({ masterName: "SOAR_TITLE", sectionTitle: "Conclusion" });
  s.addText("Questions", { placeholder: "title" });
  s.addText("Démonstration en direct : console locale et serveur AWS via tunnel SSH", { placeholder: "body" });
  await iconCircle(s, 0.8, 0.8, fa.FaComments, "questions", 0.8);
  s.addText("github.com/souhaylchiibi/soar-ioc-factory", { x: 0.8, y: 6.6, w: 8, h: 0.4, fontSize: 14, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("Proposer la démonstration : connexion, Overview, recherche Ctrl K, dossier IOC, Detection Center, lancement confirmé d'une opération, Audit Center.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("deck ->", OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
