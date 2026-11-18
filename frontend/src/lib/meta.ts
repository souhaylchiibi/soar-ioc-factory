/** Display metadata for domain enums — one place for labels and tones. */
import type { ConnState, IocStatus, IocType, RiskLevel } from "./api";

export type Tone = "neutral" | "accent" | "ok" | "warn" | "danger" | "info" | "violet";

export const STATUS_META: Record<IocStatus, { label: string; tone: Tone; hint: string }> = {
  NEW: { label: "Nouveau", tone: "neutral", hint: "Reçu, pas encore normalisé" },
  NORMALIZED: { label: "Normalisé", tone: "info", hint: "Valeur validée et canonique" },
  ENRICHED: { label: "Enrichi", tone: "violet", hint: "Contexte fournisseurs ajouté" },
  SCORED: { label: "Noté", tone: "violet", hint: "Score calculé, décision en attente" },
  PUBLISHED: { label: "Publié", tone: "ok", hint: "Distribué aux capteurs" },
  MONITORED: { label: "Surveillé", tone: "info", hint: "Suivi sans blocage" },
  REVIEW_REQUIRED: { label: "À revoir", tone: "warn", hint: "Décision analyste requise" },
  EXPIRED: { label: "Expiré", tone: "warn", hint: "Validité dépassée, retrait en attente" },
  REMOVED: { label: "Retiré", tone: "neutral", hint: "Retrait vérifié" },
  REJECTED: { label: "Rejeté", tone: "danger", hint: "Score insuffisant ou invalide" },
  DUPLICATE: { label: "Doublon", tone: "neutral", hint: "Rattaché à un IOC existant" },
};

export const RISK_META: Record<RiskLevel, { label: string; color: string }> = {
  CRITICAL: { label: "Critique", color: "var(--color-risk-critical)" },
  HIGH: { label: "Élevé", color: "var(--color-risk-high)" },
  MEDIUM: { label: "Moyen", color: "var(--color-risk-medium)" },
  LOW: { label: "Faible", color: "var(--color-risk-low)" },
};

export const RISK_ORDER: RiskLevel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const TYPE_META: Record<IocType, { label: string; color: string }> = {
  IP: { label: "IP", color: "#5aa2f5" },
  DOMAIN: { label: "Domaine", color: "#2cc2a6" },
  URL: { label: "URL", color: "#a48af5" },
  HASH_MD5: { label: "MD5", color: "#e0a43b" },
  HASH_SHA1: { label: "SHA-1", color: "#ee7aa8" },
  HASH_SHA256: { label: "SHA-256", color: "#7fc8e8" },
};

export const CONN_META: Record<ConnState, { label: string; tone: Tone }> = {
  connected: { label: "Connecté", tone: "ok" },
  degraded: { label: "Dégradé", tone: "warn" },
  no_data: { label: "Aucune donnée", tone: "neutral" },
  not_configured: { label: "Configuration manquante", tone: "warn" },
  unreachable: { label: "Indisponible", tone: "danger" },
  disabled: { label: "Désactivé", tone: "neutral" },
};

export const DECISION_META: Record<string, { label: string; tone: Tone; rule: string }> = {
  publish: { label: "Publier", tone: "ok", rule: "score ≥ 80" },
  monitor: { label: "Surveiller", tone: "info", rule: "50 ≤ score < 80" },
  reject: { label: "Rejeter", tone: "danger", rule: "score < 50" },
  review: { label: "Revue", tone: "warn", rule: "cas ambigu" },
};

export const SEVERITY_META: Record<string, { label: string; color: string }> = {
  critical: { label: "Critique", color: "var(--color-risk-critical)" },
  high: { label: "Élevée", color: "var(--color-risk-high)" },
  medium: { label: "Moyenne", color: "var(--color-risk-medium)" },
  low: { label: "Faible", color: "var(--color-risk-low)" },
};

export const WORKFLOWS: Record<string, { label: string; action: string; path?: string; describe: string }> = {
  "workflow-1": { label: "Collecte", action: "COLLECT", path: "/iocs/collect/run?limit=50", describe: "Interroge les sources de Threat Intelligence et ingère les indicateurs." },
  "workflow-2": { label: "Normalisation", action: "NORMALIZE", path: "/iocs/normalize/run?limit=200", describe: "Rattrape les enregistrements restés au statut NEW." },
  "workflow-3": { label: "Enrichissement", action: "ENRICH", path: "/iocs/enrich/run?limit=50", describe: "Interroge OTX / AbuseIPDB pour les IOC normalisés." },
  "workflow-4": { label: "Scoring", action: "SCORE", describe: "Calcule le score explicable et applique la décision." },
  "workflow-5": { label: "Publication", action: "PUBLISH", path: "/iocs/publish/run?limit=100", describe: "Publie les IOC à score élevé, avec relecture de vérification." },
  "workflow-6": { label: "Surveillance", action: "OBSERVE", describe: "Rapproche les alertes Suricata / Wazuh de l'inventaire." },
  "workflow-7": { label: "Expiration", action: "EXPIRE", path: "/iocs/expire/run", describe: "Expire les IOC échus puis retire les publications (vérifié)." },
  "workflow-8": { label: "Rapport", action: "EXPORT", path: "/reports/daily", describe: "Génère le rapport quotidien depuis PostgreSQL." },
};

export const toneClasses: Record<Tone, string> = {
  neutral: "bg-surface-3 text-fg-muted ring-line-strong",
  accent: "bg-accent/12 text-accent-strong ring-accent/30",
  ok: "bg-ok/12 text-ok ring-ok/30",
  warn: "bg-warn/12 text-warn ring-warn/30",
  danger: "bg-danger/12 text-danger ring-danger/30",
  info: "bg-info/12 text-info ring-info/30",
  violet: "bg-violet/12 text-violet ring-violet/30",
};

export const toneDot: Record<Tone, string> = {
  neutral: "bg-fg-subtle",
  accent: "bg-accent",
  ok: "bg-ok",
  warn: "bg-warn",
  danger: "bg-danger",
  info: "bg-info",
  violet: "bg-violet",
};
