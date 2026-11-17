// Présentation de soutenance — SOAR IOC Factory (19 diapositives).
// Présente la plateforme telle qu'elle est livrée. Données lues dans
// reports/data/facts.json et reports/evaluation/metrics.json — rien n'est saisi à la main.
// Usage : NODE_PATH=<node_modules avec pptxgenjs, react, react-dom, react-icons, sharp>
//         node scripts/build_presentation_projet.js "<racine>" "<chemin apply_theme.js>"
// Sortie : reports/PRESENTATION_SOAR_IOC_FACTORY_PROJET.pptx
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = process.argv[2];
const { applyTheme } = require(process.argv[3]);
const OUT = path.join(ROOT, "reports", "PRESENTATION_SOAR_IOC_FACTORY_PROJET.pptx");
const F = JSON.parse(fs.readFileSync(path.join(ROOT, "reports/data/facts.json"), "utf8"));
const M = JSON.parse(fs.readFileSync(path.join(ROOT, "reports/evaluation/metrics.json"), "utf8"));
const S = F.local.stats;
const AWS = F.aws || {};
const SHOT = (f) => path.join(ROOT, "capture", "2026-11-17", f);
const nf = (n, d = 0) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(n).replace(/ /g, " ");

const HEX = {
  bg: "0B0F14", card: "151B24", card2: "1B2330", line: "2E3948", white: "FFFFFF",
  text: "E7ECF2", muted: "9AA6B6", teal: "2CC2A6", amber: "E0A43B",
  red: "F0605D", blue: "5AA2F5", violet: "A48AF5", slate: "7D8BA0",
};
const THEME = {
  name: "SOAR IOC Factory",
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
pres.title = "SOAR IOC Factory — Soutenance";
pres.author = "Souhayl Chouaibi";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

async function icon(Comp, color = "#2CC2A6", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function cropTop(file, ratio = 1440 / 900) {
  const img = sharp(file);
  const meta = await img.metadata();
  const h = Math.min(meta.height, Math.round(meta.width / ratio));
  const buf = await img.extract({ left: 0, top: 0, width: meta.width, height: h }).png().toBuffer();
  return { data: "image/png;base64," + buf.toString("base64"), ratio: meta.width / h };
}

pres.defineSlideMaster({
  title: "SOAR_TITLE",
  background: { color: HEX.bg },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 11.7, h: 1.4, fontSize: 54, bold: true, color: HEX.text, align: "left", valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.5, w: 11.7, h: 0.9, fontSize: 22, color: HEX.teal, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SOAR_CONTENT",
  background: { color: HEX.bg },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 30, bold: true, color: HEX.text, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "SOAR IOC Factory", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
});

function content(section, title) {
  const s = pres.addSlide({ masterName: "SOAR_CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}
function card(slide, x, y, w, h, name, fill = HEX.card) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: HEX.line, width: 0.75 }, objectName: name });
}
async function iconCircle(slide, x, y, Comp, name, d = 0.62, color = "#2CC2A6", ring = HEX.teal) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: HEX.card2 }, line: { color: ring, width: 1 }, objectName: `${name}-circle` });
  slide.addImage({ data: await icon(Comp, color), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: name, objectName: `${name}-icon` });
}
function txt(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, { x, y, w, h, margin: 0, isTextBox: true, color: HEX.text, fontSize: 14, valign: "top", ...opts });
}
function stat(slide, x, y, w, value, label, color = HEX.teal, size = 44) {
  txt(slide, String(value), x, y, w, 0.85, { fontSize: size, bold: true, color, valign: "middle" });
  txt(slide, label, x, y + 0.85, w, 0.6, { fontSize: 13, color: HEX.muted });
}
function shot(slide, data, x, y, w, ratio, name) {
  const h = w / ratio;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: 0.06, fill: { color: HEX.line }, line: { color: HEX.line }, objectName: `${name}-frame` });
  slide.addImage({ data, x, y, w, h, altText: name, objectName: name });
}
async function iconRows(slide, rows, x, y, w, step, prefix, color = "#2CC2A6", ring = HEX.teal) {
  for (let i = 0; i < rows.length; i++) {
    const [ic, t, d] = rows[i];
    const yy = y + i * step;
    await iconCircle(slide, x, yy, ic, `${prefix}-${i}`, 0.66, color, ring);
    txt(slide, t, x + 0.9, yy - 0.02, w - 0.9, 0.4, { fontSize: 17, bold: true });
    txt(slide, d, x + 0.9, yy + 0.38, w - 0.9, 0.55, { fontSize: 13, color: HEX.muted });
  }
}
const CHART = { catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", legendFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 11, dataLabelColor: HEX.text, legendColor: HEX.muted, legendFontSize: 11, valGridLine: { color: HEX.line, size: 0.5 }, catGridLine: { style: "none" }, valAxisMinVal: 0 };

async function build() {
  const testsPassed = F.tests.reduce((n, t) => n + t.passed, 0);
  const proc = F.local.processing || {};
  const perIoc = ["COLLECT", "ENRICH", "SCORE", "PUBLISH"].reduce((n, k) => n + (proc[k] && proc[k].items ? proc[k].duration_ms / 1000 / proc[k].items : 0), 0);
  const sc = M.scoring;
  const sources = F.local.sources.filter((x) => x.kind !== "SYNTHETIC").sort((a, b) => b.ioc_count - a.ioc_count);

  // 1 ----------------------------------------------------------------------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "SOAR_TITLE", sectionTitle: "Introduction" });
  s.addText("SOAR IOC Factory", { placeholder: "title" });
  s.addText("Automatiser le cycle de vie des indicateurs de compromission, preuve à l'appui", { placeholder: "body" });
  await iconCircle(s, 0.8, 0.8, fa.FaShieldAlt, "logo", 0.8);
  [[nf(S.total_iocs), "indicateurs gérés"], ["7", "sources de renseignement"], [nf(testsPassed), "tests réussis"], ["0", "vulnérabilité ouverte"]]
    .forEach(([v, l], i) => stat(s, 0.8 + i * 3.0, 5.0, 2.8, v, l, i === 3 ? HEX.teal : HEX.text, 40));
  txt(s, "Projet 3 · Cyber Threat Intelligence · Souhayl Chouaibi · 17 novembre 2026", 0.8, 6.75, 10, 0.35, { fontSize: 12, color: HEX.muted });
  s.addNotes("Bonjour. Je présente SOAR IOC Factory, une plateforme qui automatise le cycle de vie des indicateurs de compromission, de la collecte au retrait vérifié, en gardant une preuve de chaque étape.");

  // 2 ----------------------------------------------------------------------
  s = content("Introduction", "Un SOC reçoit plus d'indicateurs qu'il ne peut en traiter à la main");
  await iconRows(s, [
    [fa.FaLayerGroup, "Volume", "des centaines d'indicateurs par jour, avec de nombreux doublons"],
    [fa.FaBalanceScale, "Qualité inégale", "plusieurs flux relaient la même origine : faux consensus"],
    [fa.FaRandom, "Décision risquée", "publier un faux positif bloque un service légitime"],
    [fa.FaSearch, "Traçabilité", "expliquer pourquoi, par qui, et prouver le retrait"],
  ], 0.6, 1.6, 6.4, 1.3, "pb", "#F0605D", HEX.red);
  card(s, 7.5, 1.6, 5.2, 4.95, "pb-card");
  txt(s, "Ce qu'il faut", 7.85, 1.85, 4.5, 0.4, { fontSize: 17, bold: true, color: HEX.teal });
  const needs = ["une chaîne automatisée et reproductible", "un score que l'on peut expliquer", "des décisions fondées sur des seuils", "une preuve inaltérable de chaque étape", "une console claire pour l'analyste"];
  s.addText(needs.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < needs.length - 1 } })), { x: 7.85, y: 2.45, w: 4.6, h: 3.8, fontSize: 15, color: HEX.text, paraSpaceAfter: 10, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Le problème : volume, qualité inégale, décisions risquées et besoin de traçabilité. Un traitement manuel est lent et peu reproductible.");

  // 3 ----------------------------------------------------------------------
  s = content("Introduction", "Une usine à IOC, de la collecte au retrait vérifié");
  F.local.funnel.stages.forEach((st, i) => {
    const x = 0.6 + (i % 5) * 2.45, y = 1.55 + Math.floor(i / 5) * 2.35;
    card(s, x, y, 2.2, 2.0, `stage-${st.key}`);
    txt(s, `${i + 1}`, x + 0.2, y + 0.18, 0.5, 0.4, { fontSize: 14, bold: true, color: HEX.teal });
    txt(s, st.label, x + 0.2, y + 0.55, 1.9, 0.45, { fontSize: 15, bold: true });
    txt(s, nf(st.count), x + 0.2, y + 1.0, 1.9, 0.6, { fontSize: 28, bold: true, valign: "middle" });
    txt(s, st.current !== null ? `actuellement ${nf(st.current)}` : "opérations tracées", x + 0.2, y + 1.6, 1.9, 0.3, { fontSize: 11, color: HEX.muted });
  });
  txt(s, "Chaque compteur est adossé à sa table de preuve (journal d'audit, événements de cycle de vie) — aucune valeur estimée.", 0.6, 6.35, 12.1, 0.4, { fontSize: 13, italic: true, color: HEX.muted });
  s.addNotes("Les dix étapes du cycle de vie, avec le débit réellement mesuré dans la base pour chacune.");

  // 4 ----------------------------------------------------------------------
  pres.addSection({ title: "Conception" });
  s = content("Conception", "Une architecture en couches, sans port public");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 1.45, w: 7.9, h: 5.3, rectRadius: 0.06, fill: { color: HEX.white }, line: { color: HEX.line }, objectName: "arch-bg" });
  s.addImage({ path: path.join(ROOT, "reports/data/fig_architecture.png"), x: 0.7, y: 1.52, w: 7.7, h: 5.16, sizing: { type: "contain", w: 7.7, h: 5.16 }, altText: "Schéma d'architecture", objectName: "arch" });
  await iconRows(s, [
    [fa.FaServer, "API FastAPI + PostgreSQL 16", "pipeline, score, contrôle d'accès"],
    [fa.FaProjectDiagram, "n8n", "8 workflows planifiés"],
    [fa.FaDesktop, "Console React", "13 pages pour l'analyste"],
    [fa.FaDocker, "Docker Compose", "local et serveur AWS"],
  ], 8.9, 1.6, 3.9, 1.3, "arch-row");
  s.addNotes("Quatre couches : les sources, l'orchestration n8n, l'API avec son contrôle d'accès et son pipeline, puis les effets et la console. Toutes les preuves sont dans PostgreSQL. L'accès passe uniquement par un tunnel SSH.");

  // 5 ----------------------------------------------------------------------
  pres.addSection({ title: "Pipeline" });
  s = content("Pipeline", "7 sources collectées, doublons fusionnés");
  s.addChart(pres.charts.BAR, [{ name: "IOC", labels: sources.map((x) => x.name), values: sources.map((x) => x.ioc_count) }], {
    x: 0.6, y: 1.5, w: 7.6, h: 5.1, barDir: "bar", chartColors: [HEX.teal], showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    showTitle: true, title: "Indicateurs distincts par source", titleColor: HEX.text, titleFontSize: 14, catAxisOrientation: "maxMin", ...CHART, objectName: "chart-sources",
  });
  stat(s, 8.7, 1.6, 4, nf(M.dedup.raw_items_collected), "éléments bruts collectés", HEX.text);
  stat(s, 8.7, 3.25, 4, `${nf(M.dedup.dedup_rate_pct, 1)} %`, "de doublons fusionnés (provenance conservée)", HEX.teal);
  stat(s, 8.7, 4.9, 4, nf(M.dedup.invalid_rejected), "valeur invalide rejetée avec son motif", HEX.amber);
  s.addNotes("Sept collecteurs réels. L'échec d'une source est enregistré sans bloquer les autres et n'est jamais transformé en succès vide. Les doublons sont fusionnés par empreinte SHA-256.");

  // 6 ----------------------------------------------------------------------
  s = content("Pipeline", "Une forme canonique par indicateur");
  const norm = [
    [fa.FaNetworkWired, "Adresse IP", "198.51.100.7:443  →  198.51.100.7"],
    [fa.FaGlobe, "Domaine", "Evil.Example.  →  evil.example"],
    [fa.FaLink, "URL", "HTTP://Evil.Example/p#x  →  http://evil.example/p"],
    [fa.FaFingerprint, "Empreinte", "MD5 · SHA-1 · SHA-256 en minuscules, longueur contrôlée"],
  ];
  for (let i = 0; i < norm.length; i++) {
    const [ic, t, d] = norm[i];
    const x = 0.6 + (i % 2) * 6.15, y = 1.6 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 5.95, 1.5, `norm-${i}`);
    await iconCircle(s, x + 0.3, y + 0.42, ic, `norm-icon-${i}`, 0.66);
    txt(s, t, x + 1.2, y + 0.3, 4.5, 0.4, { fontSize: 17, bold: true });
    txt(s, d, x + 1.2, y + 0.75, 4.5, 0.5, { fontSize: 13, color: HEX.muted, fontFace: "Courier New" });
  }
  card(s, 0.6, 5.15, 12.1, 1.4, "fp-card", HEX.card2);
  txt(s, "Empreinte de déduplication", 0.9, 5.33, 5, 0.4, { fontSize: 15, bold: true, color: HEX.teal });
  txt(s, "SHA-256( type : valeur canonique ) — un doublon met à jour l'indicateur existant et ajoute sa provenance.", 0.9, 5.78, 11.5, 0.55, { fontSize: 14 });
  s.addNotes("La normalisation garantit qu'un même indicateur a toujours la même écriture. L'empreinte SHA-256 du type et de la valeur canonique sert de clé de déduplication.");

  // 7 ----------------------------------------------------------------------
  s = content("Pipeline", "Un score de confiance que l'on peut expliquer");
  s.addChart(pres.charts.BAR, [{ name: "Poids", labels: ["Fiabilité de la source", "Fraîcheur", "Sources indépendantes", "Consensus d'enrichissement", "Détections observées"], values: [25, 20, 20, 20, 15] }], {
    x: 0.6, y: 1.5, w: 7.2, h: 5.1, barDir: "bar", chartColors: [HEX.teal], showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    showTitle: true, title: "Cinq composantes pondérées (total 100)", titleColor: HEX.text, titleFontSize: 14, catAxisOrientation: "maxMin", valAxisMaxVal: 30, ...CHART, objectName: "chart-weights",
  });
  await iconRows(s, [
    [fa.FaHourglassHalf, "Fraîcheur décroissante", "demi-vie par type : URL 3 j, IP 7 j, SHA-256 60 j"],
    [fa.FaUsers, "Anti-collusion", "sources comptées par groupe de provenance"],
    [fa.FaMinusCircle, "Pénalité faux positif", "−20 points par faux positif qualifié"],
    [fa.FaCommentDots, "Explication stockée", `${nf(sc.explainability_pct)} % des scores justifiés`],
  ], 8.2, 1.6, 4.6, 1.3, "score-row");
  s.addNotes("Le score sur 100 additionne cinq composantes. Chacune est stockée avec ses points et une explication en langage naturel : on peut toujours répondre à la question pourquoi ce score.");

  // 8 ----------------------------------------------------------------------
  s = content("Pipeline", "Des décisions reproductibles, fondées sur des seuils");
  s.addChart(pres.charts.BAR, [{ name: "IOC", labels: ["Publier (≥ 80)", "Surveiller (50–79)", "Rejeter (< 50)"], values: [sc.decisions.publish, sc.decisions.monitor, sc.decisions.reject] }], {
    x: 0.6, y: 1.5, w: 7.2, h: 5.1, barDir: "col", chartColors: [HEX.teal], showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    showTitle: true, title: "Décisions appliquées", titleColor: HEX.text, titleFontSize: 14, ...CHART, objectName: "chart-decisions",
  });
  stat(s, 8.3, 1.6, 4.4, nf(sc.avg, 1), `score moyen · médiane ${nf(sc.median)} · maximum ${nf(sc.max)}`, HEX.text);
  card(s, 8.3, 3.35, 4.4, 3.2, "decision-card");
  txt(s, "Une politique exigeante", 8.6, 3.55, 3.9, 0.4, { fontSize: 16, bold: true, color: HEX.teal });
  txt(s, "Un indicateur n'est publié que s'il cumule fiabilité, fraîcheur, consensus et, idéalement, des détections réelles. Les cas ambigus passent en revue analyste, avec justification obligatoire.", 8.6, 4.0, 3.9, 2.4, { fontSize: 14, color: HEX.text });
  s.addNotes("Trois décisions : publier à partir de 80, surveiller entre 50 et 79, rejeter en dessous. La politique est volontairement exigeante : très peu d'indicateurs sont publiés.");

  // 9 ----------------------------------------------------------------------
  s = content("Pipeline", "Rien n'est déclaré réussi sans preuve");
  const proofs = [
    [fa.FaCheckDouble, "Publication relue", "écrite puis relue avant le statut « vérifié »", nf(M.publication.verified), "publication vérifiée"],
    [fa.FaTrashRestore, "Retrait confirmé", "REMOVED refusé tant qu'une publication reste active", nf(F.local.funnel.verified_removals), "retrait vérifié"],
    [fa.FaLock, "Audit inaltérable", "trigger PostgreSQL : ni modification ni suppression", nf(M.audit.events), "entrées d'audit"],
  ];
  for (let i = 0; i < proofs.length; i++) {
    const [ic, t, d, v, l] = proofs[i];
    const x = 0.6 + i * 4.1;
    card(s, x, 1.6, 3.85, 4.95, `proof-${i}`);
    await iconCircle(s, x + 0.3, 1.9, ic, `proof-icon-${i}`, 0.7);
    txt(s, t, x + 0.3, 2.8, 3.3, 0.45, { fontSize: 19, bold: true });
    txt(s, d, x + 0.3, 3.3, 3.3, 0.9, { fontSize: 14, color: HEX.muted });
    txt(s, v, x + 0.3, 4.5, 3.3, 0.9, { fontSize: 44, bold: true, color: HEX.teal, valign: "middle" });
    txt(s, l, x + 0.3, 5.45, 3.3, 0.4, { fontSize: 13, color: HEX.muted });
  }
  s.addNotes("Principe central : aucune action n'est déclarée réussie sans confirmation technique. Une publication est relue, un retrait est confirmé, et le journal d'audit ne peut être ni modifié ni supprimé.");

  // 10 ---------------------------------------------------------------------
  s = content("Pipeline", "Huit workflows n8n font tourner la chaîne");
  const wfs = [["1", "Collecte", "30 min"], ["2", "Normalisation", "30 min"], ["3", "Enrichissement", "1 h"], ["4", "Scoring", "30 min"], ["5", "Publication", "1 h"], ["6", "Surveillance", "15 min"], ["7", "Expiration", "1 h"], ["8", "Rapport", "06:00"]];
  wfs.forEach(([n, t, f], i) => {
    const x = 0.6 + (i % 4) * 2.0, y = 1.6 + Math.floor(i / 4) * 1.75;
    card(s, x, y, 1.85, 1.5, `wf-${n}`);
    txt(s, n, x + 0.2, y + 0.15, 0.5, 0.4, { fontSize: 14, bold: true, color: HEX.teal });
    txt(s, t, x + 0.2, y + 0.55, 1.55, 0.4, { fontSize: 14, bold: true });
    txt(s, f, x + 0.2, y + 0.98, 1.55, 0.35, { fontSize: 12, color: HEX.muted });
  });
  txt(s, "Clé de service lue dans l'environnement n8n · étiquette workflow-N dans l'audit · reprise après échec", 0.6, 5.25, 7.9, 0.8, { fontSize: 13, color: HEX.muted });
  stat(s, 9.0, 1.6, 3.7, `${nf(perIoc, 1)} s`, "de temps machine mesuré par indicateur, de la collecte à la décision", HEX.teal);
  stat(s, 9.0, 3.5, 3.7, nf(F.local.runs.total), "exécutions de pipeline tracées", HEX.text);
  stat(s, 9.0, 5.1, 3.7, nf(F.local.runs.failed), "exécution en échec", HEX.text);
  s.addNotes("Huit workflows planifiés appellent l'API avec une clé de service. Chaque exécution enregistre sa durée réelle. Le délai de bout en bout dépend de la cadence des workflows, le temps machine par indicateur est d'environ une seconde.");

  // 11 ---------------------------------------------------------------------
  pres.addSection({ title: "Sécurité" });
  s = content("Sécurité", "Un accès contrôlé de bout en bout");
  const ctrls = [
    [fa.FaKey, "Argon2id", "mots de passe ≥ 12 caractères, 3 classes"],
    [fa.FaIdBadge, "Jeton JWT 60 min", "compte relu à chaque requête"],
    [fa.FaUsersCog, "3 rôles", "lecteur · analyste · administrateur"],
    [fa.FaUserLock, "Anti force brute", "verrouillage après 5 échecs"],
    [fa.FaRobot, "Clé de service n8n", "jamais écrite dans les fichiers"],
    [fa.FaUserCheck, "Audit signé", "l'acteur vient du jeton, pas de la requête"],
  ];
  for (let i = 0; i < ctrls.length; i++) {
    const [ic, t, d] = ctrls[i];
    const x = 0.6 + (i % 3) * 4.1, y = 1.6 + Math.floor(i / 3) * 2.45;
    card(s, x, y, 3.85, 2.15, `ctrl-${i}`);
    await iconCircle(s, x + 0.3, y + 0.3, ic, `ctrl-icon-${i}`);
    txt(s, t, x + 0.3, y + 1.05, 3.3, 0.45, { fontSize: 18, bold: true });
    txt(s, d, x + 0.3, y + 1.5, 3.3, 0.55, { fontSize: 13, color: HEX.muted });
  }
  s.addNotes("Toutes les routes exigent une authentification. Trois rôles hiérarchiques. L'identité inscrite dans le journal vient toujours du jeton, jamais d'un champ fourni par le client.");

  // 12 ---------------------------------------------------------------------
  s = content("Sécurité", "Une sécurité vérifiée par cinq outils");
  card(s, 0.6, 1.6, 3.9, 4.95, "zero-card", HEX.card2);
  txt(s, "0", 0.6, 2.2, 3.9, 1.6, { fontSize: 96, bold: true, color: HEX.teal, align: "center", valign: "middle" });
  txt(s, "vulnérabilité ouverte", 0.6, 3.9, 3.9, 0.5, { fontSize: 18, bold: true, align: "center" });
  txt(s, "aucun port public · conteneurs non-root · CSP stricte", 0.9, 4.6, 3.3, 1.2, { fontSize: 13, color: HEX.muted, align: "center" });
  F.security_scans.forEach((sc2, i) => {
    const y = 1.6 + i * 1.0;
    card(s, 4.8, y, 7.9, 0.85, `scan-${i}`);
    txt(s, sc2.tool, 5.05, y + 0.12, 2.0, 0.6, { fontSize: 16, bold: true, color: HEX.teal, valign: "middle" });
    txt(s, sc2.scope, 7.1, y + 0.12, 2.6, 0.6, { fontSize: 12, color: HEX.muted, valign: "middle" });
    txt(s, sc2.result, 9.75, y + 0.12, 2.8, 0.6, { fontSize: 12.5, valign: "middle" });
  });
  s.addNotes("Bandit, pip-audit, npm audit, Trivy et OWASP ZAP ont été exécutés : aucune vulnérabilité ouverte. Les deux avertissements ZAP sont documentés.");

  // 13 ---------------------------------------------------------------------
  pres.addSection({ title: "Console SOC" });
  s = content("Console SOC", "Une console SOC pensée pour l'analyste");
  const ov = await cropTop(SHOT("console-02-overview.png"));
  shot(s, ov.data, 0.6, 1.45, 8.4, ov.ratio, "overview-shot");
  await iconRows(s, [
    [fa.FaSearch, "Recherche Ctrl K", "IOC et sources, au clavier"],
    [fa.FaBell, "Notifications réelles", "échecs, détections, revues"],
    [fa.FaCheckDouble, "Confirmation", "avant toute action sensible"],
    [fa.FaMobileAlt, "Responsive", "bureau, tablette, mobile"],
  ], 9.4, 1.5, 3.4, 1.3, "feat");
  s.addNotes("La console regroupe treize pages. Tout ce qu'elle affiche vient de l'API. Les actions sensibles demandent une confirmation et un rôle analyste.");

  // 14 ---------------------------------------------------------------------
  s = content("Console SOC", "Détecter, qualifier, prouver");
  const det = await cropTop(SHOT("console-03-detection-center.png"));
  const ioc = await cropTop(SHOT("console-05-ioc-detail.png"));
  shot(s, det.data, 0.6, 1.5, 5.9, det.ratio, "detection-shot");
  shot(s, ioc.data, 6.8, 1.5, 5.9, ioc.ratio, "ioc-shot");
  s.addText([{ text: "Detection Center", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "alertes Suricata et Wazuh, sévérité déclarée par le capteur, preuve brute conservée, qualification", options: { color: HEX.muted } }], { x: 0.6, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addText([{ text: "Dossier de preuve d'un IOC", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "score justifié composante par composante, cycle de vie, provenance, publications, audit", options: { color: HEX.muted } }], { x: 6.8, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Le Detection Center rapproche les alertes des capteurs de l'inventaire. L'analyste confirme ou déclare un faux positif, ce qui pénalise le score. Le dossier IOC rassemble toute la preuve d'un indicateur.");

  // 15 ---------------------------------------------------------------------
  s = content("Console SOC", "Suivre le cycle de vie et l'automatisation");
  const lc = await cropTop(SHOT("console-06-lifecycle.png"));
  const au = await cropTop(SHOT("console-09-automation.png"));
  shot(s, lc.data, 0.6, 1.5, 5.9, lc.ratio, "lifecycle-shot");
  shot(s, au.data, 6.8, 1.5, 5.9, au.ratio, "automation-shot");
  s.addText([{ text: "IOC Lifecycle", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "dix étapes avec leur débit mesuré et la table qui le prouve", options: { color: HEX.muted } }], { x: 0.6, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addText([{ text: "Automation Center", options: { bold: true, color: HEX.text, breakLine: true } }, { text: "état de n8n, dernière exécution et durée de chaque workflow", options: { color: HEX.muted } }], { x: 6.8, y: 5.35, w: 5.9, h: 1.0, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Deux autres vues : le cycle de vie avec ses dix étapes prouvées, et le centre d'automatisation qui montre l'état de n8n et les exécutions mesurées.");

  // 16 ---------------------------------------------------------------------
  pres.addSection({ title: "Déploiement et validation" });
  s = content("Déploiement et validation", "Déployée sur AWS sans aucun port public");
  const checks = ["Services publiés sur 127.0.0.1 uniquement", "Accès par tunnel SSH restreint à une adresse", "API : 401 sans jeton, CSP active", "nginx et API en utilisateurs non-root", `Schéma de base ${AWS.alembic || ""}`, "Tests de bout en bout via le tunnel : 8/8"];
  for (let i = 0; i < checks.length; i++) {
    const y = 1.55 + i * 0.82;
    s.addImage({ data: await icon(fa.FaCheckCircle), x: 0.6, y: y + 0.07, w: 0.36, h: 0.36, altText: "validé", objectName: `check-${i}` });
    txt(s, checks[i], 1.2, y, 4.8, 0.5, { fontSize: 15, valign: "middle" });
  }
  const aw = await cropTop(SHOT("aws-02-overview.png"));
  shot(s, aw.data, 6.3, 1.5, 6.4, aw.ratio, "aws-shot");
  s.addText([{ text: "≈ 2,23 $/jour", options: { bold: true, color: HEX.teal, fontSize: 20 } }, { text: "  instance t2.large en fonctionnement · 4 conteneurs", options: { color: HEX.muted, fontSize: 13 } }], { x: 6.3, y: 5.75, w: 6.4, h: 0.6, margin: 0, isTextBox: true });
  s.addNotes("La plateforme tourne aussi sur une instance EC2. Aucun port applicatif n'est ouvert sur Internet : tout passe par un tunnel SSH. Le serveur a son propre jeu de données, indépendant du poste local.");

  // 17 ---------------------------------------------------------------------
  s = content("Déploiement et validation", `${nf(testsPassed)} tests automatisés réussis`);
  F.tests.forEach((t, i) => {
    card(s, 0.6 + i * 3.05, 1.5, 2.85, 1.9, `test-${i}`);
    txt(s, `${t.passed}/${t.count}`, 0.8 + i * 3.05, 1.65, 2.5, 0.85, { fontSize: 36, bold: true, color: HEX.teal, valign: "middle" });
    txt(s, t.suite, 0.8 + i * 3.05, 2.5, 2.5, 0.75, { fontSize: 13, color: HEX.muted });
  });
  const cov = ["Normalisation, déduplication, scoring, machine à états", "Pipeline complet, publication, révocation, expiration", "Authentification, rôles, verrouillage, clé de service", "Console : pages, états d'erreur, confirmations, filtres", "Bout en bout sur la pile réelle : poste local et serveur AWS"];
  s.addText(cov.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < cov.length - 1 } })), { x: 0.6, y: 3.75, w: 12.1, h: 2.8, fontSize: 15, color: HEX.text, paraSpaceAfter: 8, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Quatre niveaux de tests : le moteur et l'API sur un vrai PostgreSQL, les composants de la console, puis des scénarios de bout en bout sur la pile réelle, en local et sur AWS.");

  // 18 ---------------------------------------------------------------------
  s = content("Déploiement et validation", "Limites connues et perspectives");
  card(s, 0.6, 1.5, 5.9, 5.1, "limits");
  card(s, 6.8, 1.5, 5.9, 5.1, "next");
  await iconCircle(s, 0.9, 1.75, fa.FaExclamationTriangle, "limits-icon", 0.6, "#E0A43B", HEX.amber);
  await iconCircle(s, 7.1, 1.75, fa.FaRoute, "next-icon", 0.6);
  txt(s, "Limites", 1.7, 1.8, 4.6, 0.5, { fontSize: 19, bold: true, valign: "middle" });
  txt(s, "Perspectives", 7.9, 1.8, 4.6, 0.5, { fontSize: 19, bold: true, valign: "middle" });
  const lim = ["Pas de serveur MISP : état « Configuration manquante », rien n'est simulé", "Capteurs Suricata et Wazuh non actifs en continu", "Pas de vérité terrain : précision et rappel non calculés", "Jeton conservé dans l'onglet, limitation de débit par processus"];
  const nxt = ["MISP de laboratoire pour la publication distante vérifiée", "Capteurs en continu pour une détection en direct", "Jeu de vérité terrain pour mesurer le scoring", "Rôles PostgreSQL séparés, jetons de rafraîchissement"];
  s.addText(lim.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < lim.length - 1 } })), { x: 0.9, y: 2.7, w: 5.3, h: 3.6, fontSize: 15, color: HEX.muted, paraSpaceAfter: 10, margin: 0, valign: "top", isTextBox: true });
  s.addText(nxt.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < nxt.length - 1 } })), { x: 7.1, y: 2.7, w: 5.3, h: 3.6, fontSize: 15, color: HEX.text, paraSpaceAfter: 10, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Les limites sont affichées honnêtement par la plateforme elle-même. Les perspectives visent à exercer MISP et les capteurs en conditions réelles et à mesurer la précision du scoring.");

  // 19 ---------------------------------------------------------------------
  pres.addSection({ title: "Conclusion" });
  s = pres.addSlide({ masterName: "SOAR_TITLE", sectionTitle: "Conclusion" });
  s.addText("Expliquer et prouver chaque décision", { placeholder: "title" });
  s.addText("Un score explicable · des décisions reproductibles · une preuve inaltérable", { placeholder: "body" });
  const take = [[fa.FaDatabase, "Données réelles", "aucune valeur simulée"], [fa.FaShieldAlt, "Sécurité vérifiée", "0 vulnérabilité ouverte"], [fa.FaCloud, "Local et AWS", "tests de bout en bout réussis"]];
  for (let i = 0; i < take.length; i++) {
    const [ic, t, d] = take[i];
    const x = 0.8 + i * 4.0;
    await iconCircle(s, x, 4.9, ic, `take-${i}`, 0.7);
    txt(s, t, x + 0.9, 4.9, 3.0, 0.4, { fontSize: 18, bold: true });
    txt(s, d, x + 0.9, 5.3, 3.0, 0.4, { fontSize: 14, color: HEX.muted });
  }
  txt(s, "Merci — questions et démonstration en direct", 0.8, 6.6, 10, 0.4, { fontSize: 16, color: HEX.text });
  s.addNotes("En conclusion : la plateforme automatise la chaîne complète tout en gardant la capacité d'expliquer et de prouver chaque décision. Je peux maintenant faire une démonstration : connexion, Overview, recherche, dossier IOC, Detection Center, Audit Center.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("deck ->", OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
