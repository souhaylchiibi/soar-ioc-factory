-- =====================================================================
-- SOAR IOC Factory — Schéma PostgreSQL 16
-- Phase 1 (conception) — source de vérité pour les migrations Alembic.
-- Convention : snake_case, UUID en PK, horodatages timestamptz UTC,
-- contraintes CHECK pour les énumérations, index pour les hot paths.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------- Énumérations ------------------------------------------------
CREATE TYPE ioc_type AS ENUM
  ('IP', 'DOMAIN', 'URL', 'HASH_MD5', 'HASH_SHA1', 'HASH_SHA256');

CREATE TYPE ioc_status AS ENUM
  ('NEW', 'NORMALIZED', 'ENRICHED', 'SCORED', 'PUBLISHED', 'MONITORED',
   'EXPIRED', 'REMOVED', 'REJECTED', 'DUPLICATE', 'REVIEW_REQUIRED');

CREATE TYPE risk_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

CREATE TYPE source_kind AS ENUM ('COMMERCIAL', 'COMMUNITY', 'OPEN_SOURCE', 'INTERNAL', 'SYNTHETIC');

CREATE TYPE role_name AS ENUM ('admin', 'analyst', 'viewer');

CREATE TYPE event_action AS ENUM
  ('COLLECT', 'NORMALIZE', 'DEDUP', 'ENRICH', 'SCORE', 'TRANSITION',
   'PUBLISH', 'OBSERVE', 'EXPIRE', 'REMOVE', 'LOGIN', 'CONFIG_CHANGE', 'EXPORT');

-- ---------- Sources de renseignement -------------------------------------
CREATE TABLE intel_sources (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(120) NOT NULL UNIQUE,
    url              TEXT,
    kind             source_kind NOT NULL DEFAULT 'OPEN_SOURCE',
    -- Groupe de provenance : plusieurs flux qui recopient la même source
    -- partagent le même groupe => comptés comme UNE source indépendante.
    provenance_group VARCHAR(120) NOT NULL,
    -- Fiabilité déclarée 0..100, ajustable (table de confiance).
    reliability      SMALLINT NOT NULL DEFAULT 50
                     CHECK (reliability BETWEEN 0 AND 100),
    requires_api_key BOOLEAN NOT NULL DEFAULT FALSE,
    rate_limit_rpm   INTEGER NOT NULL DEFAULT 60,
    enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    last_success_at  TIMESTAMPTZ,
    last_error_at    TIMESTAMPTZ,
    last_error       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- IOC ----------------------------------------------------------
CREATE TABLE iocs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type              ioc_type NOT NULL,
    -- Valeur normalisée (minuscules pour DOMAIN/HASH, IP canonisée, URL sans fragment).
    value             TEXT NOT NULL,
    -- Valeur brute telle que collectée, pour traçabilité.
    raw_value         TEXT NOT NULL,
    status            ioc_status NOT NULL DEFAULT 'NEW',

    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ,
    removed_at        TIMESTAMPTZ,

    -- Scoring
    score             SMALLINT CHECK (score BETWEEN 0 AND 100),
    score_breakdown   JSONB,            -- {composante: {valeur, poids, explication}}
    scored_at         TIMESTAMPTZ,
    risk_level        risk_level,

    -- Déduplication : empreinte déterministe (type + valeur normalisée).
    fingerprint       CHAR(64) NOT NULL UNIQUE,
    duplicate_of      UUID REFERENCES iocs(id) ON DELETE SET NULL,

    -- Corrélations
    detection_count   INTEGER NOT NULL DEFAULT 0,
    false_positive_count INTEGER NOT NULL DEFAULT 0,
    last_detection_at TIMESTAMPTZ,

    -- Contexte
    is_synthetic      BOOLEAN NOT NULL DEFAULT FALSE,   -- jeu de test explicitement marqué
    tags              TEXT[] NOT NULL DEFAULT '{}',
    context           JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_iocs_status      ON iocs (status);
CREATE INDEX idx_iocs_type        ON iocs (type);
CREATE INDEX idx_iocs_expires_at  ON iocs (expires_at) WHERE status NOT IN ('REMOVED','REJECTED','DUPLICATE');
CREATE INDEX idx_iocs_score       ON iocs (score DESC);
CREATE INDEX idx_iocs_last_seen   ON iocs (last_seen_at DESC);
CREATE INDEX idx_iocs_context     ON iocs USING gin (context jsonb_path_ops);
CREATE INDEX idx_iocs_tags        ON iocs USING gin (tags);

-- ---------- Observations de provenance (many-to-many) ---------------------
CREATE TABLE ioc_sources (
    ioc_id       UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    source_id    UUID NOT NULL REFERENCES intel_sources(id) ON DELETE CASCADE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    external_id   TEXT,               -- identifiant chez la source (pulse_id, …)
    external_url TEXT,
    PRIMARY KEY (ioc_id, source_id)
);

-- Sources INdépendantes = groupes de provenance distincts ayant rapporté l'IOC.
CREATE INDEX idx_ioc_sources_source ON ioc_sources (source_id);

-- ---------- Enrichissements ----------------------------------------------
CREATE TABLE enrichments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_id       UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    provider     TEXT NOT NULL,          -- ex. 'otx', 'abuse.ch', 'internal_sandbox'
    -- Réponse agrégée, validated : verbatim de l'extérieur.
    data         JSONB NOT NULL,
    verdict      TEXT,                   -- malicious / suspicious / benign / unknown
    reputation   SMALLINT CHECK (reputation BETWEEN -100 AND 100),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ,
    UNIQUE (ioc_id, provider, fetched_at)
);
CREATE INDEX idx_enrichments_ioc ON enrichments (ioc_id, fetched_at DESC);

-- ---------- Scoring -------------------------------------------------------
CREATE TABLE score_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_id      UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    score       SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    risk_level  risk_level,
    breakdown   JSONB NOT NULL,          -- explication complète du calcul
    policy      TEXT NOT NULL,           -- version de la politique utilisée
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_score_history_ioc ON score_history (ioc_id, computed_at DESC);

-- ---------- Cycle de vie ---------------------------------------------------
CREATE TABLE lifecycle_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_id      UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    from_status ioc_status,
    to_status   ioc_status NOT NULL,
    reason      TEXT NOT NULL,
    actor       TEXT NOT NULL DEFAULT 'system',   -- 'system' ou identifiant utilisateur
    triggered_by TEXT,                             -- workflow n8n, scheduler, utilisateur
    score_before SMALLINT,
    score_after  SMALLINT,
    verified     BOOLEAN NOT NULL DEFAULT FALSE,  -- retrait/publication confirmé
    verification_detail JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_lifecycle_ioc   ON lifecycle_events (ioc_id, created_at DESC);
CREATE INDEX idx_lifecycle_state ON lifecycle_events (to_status, created_at DESC);

-- ---------- Détections observées (Wazuh / Suricata) ------------------------
CREATE TABLE detections (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_id       UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    sensor       TEXT NOT NULL,           -- 'wazuh' | 'suricata' | 'misp'
    rule_id      TEXT,
    raw_event    JSONB NOT NULL,
    matched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Évaluation du faux positif
    is_false_positive BOOLEAN,
    reviewed_by  TEXT,
    review_note  TEXT
);
CREATE INDEX idx_detections_ioc ON detections (ioc_id, matched_at DESC);
CREATE INDEX idx_detections_fp  ON detections (is_false_positive) WHERE is_false_positive IS TRUE;

-- ---------- Publications ---------------------------------------------------
CREATE TABLE publications (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_id         UUID NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    target         TEXT NOT NULL,          -- 'misp' | 'detection_list' | 'stix'
    target_ref     TEXT,                   -- UUID MISP, chemin de fichier, …
    status         TEXT NOT NULL,          -- 'pending' | 'verified' | 'failed' | 'revoked'
    detail         JSONB,
    published_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at     TIMESTAMPTZ
);
CREATE INDEX idx_publications_ioc ON publications (ioc_id, published_at DESC);
CREATE INDEX idx_publications_status ON publications (status);

-- ---------- Journal d'audit (append-only) ---------------------------------
CREATE TABLE audit_logs (
    id         BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor      TEXT NOT NULL,             -- utilisateur, workflow, service
    role       role_name,
    action     event_action NOT NULL,
    entity_type TEXT,                     -- 'ioc' | 'source' | 'workflow' | 'config'
    entity_id  TEXT,
    detail     JSONB NOT NULL DEFAULT '{}',
    ip_address INET,
    success    BOOLEAN NOT NULL DEFAULT TRUE,
    error      TEXT
);
CREATE INDEX idx_audit_time  ON audit_logs (occurred_at DESC);
CREATE INDEX idx_audit_actor ON audit_logs (actor, occurred_at DESC);
CREATE INDEX idx_audit_action ON audit_logs (action, occurred_at DESC);

-- Déclencheur d'immutabilité : pas de UPDATE/DELETE sur l'audit.
CREATE OR REPLACE FUNCTION forbid_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs est append-only';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();

-- ---------- Utilisateurs & rôles -------------------------------------------
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(64) NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- argon2
    role          role_name NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- ---------- Politique de scoring (configurable, versionnée) -----------------
CREATE TABLE scoring_policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version     INTEGER NOT NULL UNIQUE,
    active      BOOLEAN NOT NULL DEFAULT FALSE,
    params      JSONB NOT NULL,
    -- poids, demi-vies, seuils : {weights:{...}, half_life_days:{...}, thresholds:{auto_publish:80,...}}
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Une seule politique active.
CREATE UNIQUE INDEX idx_single_active_policy
    ON scoring_policies (active) WHERE active;

-- ---------- Rapports --------------------------------------------------------
CREATE TABLE reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'daily',
    payload     JSONB NOT NULL,           -- statistiques réelles calculées
    file_path   TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (report_date, kind)
);

-- ---------- Vue utilitaire : IOC avec sources indépendantes -----------------
CREATE VIEW v_ioc_independent_sources AS
SELECT i.id,
       i.value,
       i.type,
       count(DISTINCT s.provenance_group) AS independent_source_count
FROM iocs i
JOIN ioc_sources src ON src.ioc_id = i.id
JOIN intel_sources s ON s.id = src.source_id
GROUP BY i.id, i.value, i.type;

COMMENT ON TABLE iocs                IS 'Inventaire des indicateurs — entité centrale';
COMMENT ON TABLE intel_sources       IS 'Sources TI ; provenance_group évite le comptage double (anti-collusion)';
COMMENT ON TABLE lifecycle_events    IS 'Piste d''audit complète du cycle de vie, append-only logiquement';
COMMENT ON TABLE audit_logs          IS 'Journal d''audit système, strictement append-only (trigger)';
COMMENT ON COLUMN iocs.is_synthetic  IS 'TRUE = IOC de test synthétique, jamais présenté comme réel';
