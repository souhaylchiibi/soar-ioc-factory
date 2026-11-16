# Livraison v0.2 — Console SOC professionnelle (16/11/2026)

Évolution de SOAR IOC Factory v0.1 vers une plateforme de Cyber Threat
Intelligence avec console SOC, authentification à rôles et durcissement
sécurité. L'architecture existante (FastAPI · PostgreSQL 16 · SQLAlchemy ·
React 19 · TypeScript · Tailwind 4 · Recharts · n8n · Docker Compose) est
conservée ; aucune technologie n'a été remplacée.

Skills utilisées : **ui-ux-pro-max** (direction artistique, cf.
`DESIGN_SYSTEM.md`), **ponytail** (changements minimaux, aucune règle métier
modifiée sans raison), **graphify** (carte du code, `docs/architecture/`),
**find-skills** (aucune skill supplémentaire nécessaire).

---

## 1. Diagnostic initial (audit avant modification)

| # | Constat | Gravité |
|---|---|---|
| D1 | **Aucune authentification** : toutes les routes, y compris les écritures (transition, collecte, retrait), étaient ouvertes | Critique |
| D2 | **Traversée de chemin** : `POST /iocs/detections/ingest?path=` lisait n'importe quel fichier lisible par l'API | Élevée |
| D3 | **Usurpation d'identité dans l'audit** : l'acteur venait du corps (`TransitionRequest.actor`) ou d'un paramètre (`?actor=`) | Élevée |
| D4 | Dépendances vulnérables : Starlette 0.41.3 (7 avis, via FastAPI 0.115.6) ; image API avec zlib1g, wheel, jaraco.context vulnérables ; nginx en root | Élevée |
| D5 | Pas de rate limiting, pas d'en-têtes de sécurité côté API, CORS `*` sur méthodes/en-têtes, MISP sans vérification TLS par défaut | Moyenne |
| D6 | `intel_sources.last_success_at/last_error` jamais mis à jour par la collecte : l'état réel des sources n'était visible que dans l'audit | Moyenne |
| D7 | Requête N+1 dans `GET /iocs` (1 requête par ligne pour compter les sources) | Faible |
| D8 | Durée des exécutions de workflow non mesurée (impossible d'afficher une durée réelle) | Faible |
| D9 | Frontend : pages monolithiques, icônes emoji, bundle unique de 741 Ko, aucune recherche globale, aucune notification, aucun test | Moyenne |
| D10 | Détections affichées par identifiant tronqué, sans valeur d'IOC, sévérité ni qualification | Moyenne |
| D11 | Intégrations (n8n, MISP, Suricata, Wazuh) sans état visible | Moyenne |

Constat positif conservé tel quel : machine à états stricte, journal d'audit
append-only (trigger), relecture avant « vérifié », anti-collusion par groupe
de provenance, scoring explicable, données synthétiques marquées.

---

## 2. Fonctionnalités réellement terminées

### Backend
- **Authentification** JWT + Argon2id, rôles `viewer / analyst / admin`,
  verrouillage après 5 échecs, administration des comptes, premier admin
  créé depuis `.env`, audit de chaque connexion (`app/api/auth.py`,
  `app/core/security.py`).
- **Clé de service n8n** (`X-API-Key` + `X-Actor`) : les 8 workflows
  régénérés et réimportés ; exécution réelle du workflow 8 vérifiée
  (audit `workflow-8 / EXPORT / succès`).
- **Durcissement** : rate limiting, en-têtes de sécurité, CORS restreint,
  validation 422 sans écho, garde de configuration en production, Swagger
  désactivé en production, correction de la traversée de chemin, TLS MISP
  vérifié par défaut.
- **Nouveaux endpoints SOC** (`app/api/soc.py`) : état des intégrations
  (sondes réelles), notifications, funnel du cycle de vie avec preuve,
  série temporelle, sources + historique des collectes, Detection Center +
  qualification (met à jour le compteur de faux positifs), historique des
  exécutions avec durée mesurée, dossier complet d'un IOC, recherche globale.
- **Traçabilité** : chaque exécution de pipeline écrit une entrée `batch`
  avec `duration_ms` mesuré ; collecte, scoring et expiration ont désormais
  leur entrée d'exécution.
- **Corrections** : D3, D6 (source mise à jour à chaque collecte + historique
  relu dans l'audit), D7, preuves Wazuh enrichies (niveau, description).
- **Migration** `b7e41c2a9f10` appliquée sur la base réelle (après
  sauvegarde `pg_dump`).

### Frontend
- Coque complète : barre latérale rétractable (tiroir mobile), topbar,
  fil d'Ariane, recherche `Ctrl K`, notifications, menu profil, lien
  d'évitement.
- 13 pages : Login, SOC Overview, Detection Center, Threat Intelligence,
  dossier IOC, IOC Lifecycle, Scoring & Risk, Sources, Automation Center,
  Audit Center, Rapports, System Health, Utilisateurs.
- Toutes connectées à l'API ; états de chargement (squelettes), erreurs
  explicites (HTTP + réessai), états vides rédigés, confirmations avant toute
  action, toasts reflétant la réponse réelle de l'API.
- Fonctionnalités v0.1 conservées : *Published* et *Expired* sont des onglets
  de *IOC Lifecycle*, les anciennes URL redirigent.
- Code découpé par page (lazy loading) ; polices embarquées (CSP stricte).

---

### Déploiement AWS (16/11/2026, 22:25 UTC)
- Sauvegarde `pg_dump` + ancien dossier conservé, code v0.2, secrets générés sur le serveur, migration `b7e41c2a9f10`, reconstruction (4 conteneurs healthy), 8 workflows importés.
- Vérifié : 401 sans jeton, CSP active, nginx UID 101, ports sur 127.0.0.1 uniquement, exécution n8n `success`, **Playwright 8/8 via le tunnel SSH**.
- Surcoût : 0 $ (même instance t2.large, mêmes conteneurs).

### Livrables documentaires
- `reports/RAPPORT_V2_SOAR_IOC_FACTORY.docx` + `.pdf` (18 pages, 13 tableaux, 16 figures) — `scripts/collect_v2_facts.py` puis `scripts/build_report_v2.py`, finalisé par `scripts/word_finalize.ps1`.
- `reports/PRESENTATION_V2_SOAR_IOC_FACTORY.pptx` + `.pdf` (14 diapositives, notes orateur) — `scripts/build_presentation_v2.js`.

## 3. Fonctionnalités partiellement terminées

| Élément | État | Ce qui manque |
|---|---|---|
| Sévérité Wazuh | dérivée du niveau de règle pour les **nouvelles** ingestions | les 4 détections Wazuh historiques n'ont pas stocké le niveau → « non fournie » (pas d'estimation rétroactive) |
| Durée des exécutions | mesurée pour toute exécution postérieure au 16/11 | les exécutions antérieures restent « non mesurée » |
| Notifications | calculées sur 48 h, lu/non lu par poste | pas de notification push ni d'e-mail |

## 4. Impossible à finaliser faute d'accès ou de configuration

| Élément | Raison | Comportement actuel (honnête) |
|---|---|---|
| Publication / révocation **MISP réelle** | aucun serveur MISP ni clé disponible | client REST + 18 tests sur transport simulé ; la console affiche « Configuration manquante » ; l'endpoint répond `skipped` |
| Alertes Suricata / Wazuh en direct | capteurs non démarrés pendant la session (profils Docker) | ingestion sur fichiers montés en lecture seule ; « Aucune donnée » si le fichier est absent |
| Clés OTX / AbuseIPDB / abuse.ch | présentes dans `.env`, non modifiées | état affiché par source ; aucune collecte n'a été relancée pendant la session |

---

## 5. Tests réellement exécutés (16/11/2026)

| Suite | Commande | Résultat |
|---|---|---|
| Backend (pytest, base PostgreSQL de test migrée) | `pytest tests -q` | **224 passed** (192 existants + 32 nouveaux) |
| Frontend unitaires (Vitest + RTL) | `npm test` | **23 passed** |
| End-to-end (Playwright, Chrome, pile réelle) | `npm run test:e2e` | **8 passed** (7 desktop + 1 mobile) |
| Typage TypeScript | `npm run typecheck` | 0 erreur |
| Build de production | `npm run build` | OK (un fichier par page) |
| Migration | `alembic upgrade head` | `dadb423768cb → b7e41c2a9f10` appliquée |
| API en conteneur | `docker compose up -d --build api` | healthy ; 401 sans jeton ; `/auth/me` OK |
| n8n → API | `n8n execute --id BcgzzjDErMHIM05i` | `status: success`, audit `workflow-8 EXPORT` |
| Contrôle visuel | navigateur intégré + 12 captures `capture/2026-11-16/v2-*.png` | desktop 1440 px et mobile 390 px, aucun débordement |
| Sécurité | Bandit, pip-audit, npm audit, Trivy (image, config, secrets), OWASP ZAP baseline | voir `SECURITY.md` § 7 bis — **0 finding ouvert** hors 2 WARN ZAP documentés |

---

## 6. Problèmes résolus

1. API entièrement ouverte → authentification + rôles + clé de service (D1).
2. Lecture de fichiers arbitraires via `path=` (D2).
3. Acteur d'audit falsifiable (D3).
4. Vulnérabilités Python : Starlette 0.41.3 (7 avis, préexistant) et PyJWT 2.10.1 (17 avis — version que j'avais d'abord épinglée pour l'authentification, détectée par pip-audit) → FastAPI 0.163.1 / Starlette 1.10.0 / PyJWT 2.15.1, 0 vulnérabilité.
5. 3 vulnérabilités HIGH dans l'image API + nginx en root → image durcie, nginx non-root (D4).
6. 3 vulnérabilités dans l'outillage de test frontend → Vitest 4.
7. Absence de rate limiting / en-têtes / CORS strict / TLS MISP (D5).
8. État des sources incohérent (D6) — découvert grâce aux captures, corrigé et couvert par un test de régression.
9. N+1 dans l'inventaire (D7).
10. Durées d'exécution non mesurées (D8).
11. Route UI `/health` en collision avec la sonde API `/health` (un rechargement affichait du JSON) → `/system-health` + test e2e de lien direct.
12. Landmark de navigation non étiqueté (découvert par Playwright).
13. Polices inlinées en `data:` bloquées par la CSP → émission en fichiers.
14. Détection manuelle avec `rule` texte → 500 sur `/detections` (test de régression ajouté).
15. Adresse IP non valide → échec d'écriture `INET` au login (validation ajoutée).

---

## 7. Limitations restantes et risques résiduels

- Jeton dans `sessionStorage` (XSS = vol de jeton possible ; mitigé par CSP stricte et 60 min de validité) ; pas de révocation individuelle de jeton (désactiver le compte la remplace).
- Rate limiting en mémoire, par processus (à placer dans le reverse proxy si plusieurs workers).
- `style-src 'unsafe-inline'` nécessaire aux styles inline React/Recharts (aucun script inline).
- Un seul rôle PostgreSQL (propriétaire du schéma) pour l'API et les migrations.
- Pas de TLS entre conteneurs (réseau bridge mono-hôte) ; accès distant uniquement par tunnel SSH.
- La base EC2 (94 IOC) est distincte de la base locale ; aucune synchronisation entre les deux.
- Pas de vérité terrain : précision / rappel non calculables (inchangé, documenté).
- 410 avertissements Ruff **de style** (annotations `Optional` au lieu de `X | None`, longueur de ligne, `Depends()` en valeur par défaut — idiome FastAPI) ; catégories erreurs/bugs (`F`, `B904`) : 21 avant → 2 après (dans `normalization.py` et `test_health.py`, non modifiés).

---

## 8. Fichiers

**Nouveaux (backend)** : `app/api/auth.py`, `app/api/soc.py`,
`app/core/security.py`, `app/core/middleware.py`,
`app/services/integrations_status.py`, `tests/test_auth_api.py`,
`tests/test_soc_api.py`,
`database/migrations/versions/b7e41c2a9f10_auth_lockout_and_audit_indexes.py`.

**Modifiés (backend / infra)** : `app/main.py`, `app/core/config.py`,
`app/models/account.py`, `app/api/iocs.py`, `app/api/operations.py`,
`requirements.txt`, `Dockerfile.backend`, `Dockerfile.frontend`,
`nginx.conf`, `docker-compose.yml`, `docker-compose.aws.yml`, `.env.example`,
`.gitignore`, `scripts/generate_n8n_workflows.py`, `workflows/n8n/0*.json`.

**Frontend** : réécrits `App.tsx`, `main.tsx`, `index.css`, `lib/api.ts`,
`vite.config.ts`, `package.json` ; nouveaux `lib/{auth.tsx,format.ts,meta.ts,useApi.ts}`,
`components/{layout,ui,charts,domain}/*`, 13 pages dans `pages/`, tests
(`*.test.ts(x)`, `src/test/`, `vitest.config.ts`), `e2e/`,
`playwright.config.ts` ; supprimés (remplacés) `components/Layout.tsx`,
`components/ui.tsx`, `pages/{Dashboard,Inventory,IocDetailPage,Published,Monitoring,Expired,Workflows,AuditLogs,SystemHealth}.tsx`.

**Documentation** : `docs/INSTALLATION.md`, `docs/USER_GUIDE.md`,
`docs/SECURITY.md`, `docs/TESTING.md` (mis à jour), `docs/DESIGN_SYSTEM.md`,
`docs/LIVRAISON_V2.md`, `docs/architecture/` (nouveaux),
`reports/security/zap-baseline.*`, `capture/2026-11-16/v2-*.png`.

---

## 9. Commandes exactes

```powershell
cd "C:\Users\T480s\Desktop\SOAR project"

# 1. Secrets (une fois) : copier .env.example -> .env et renseigner
#    POSTGRES_PASSWORD, SECRET_KEY, N8N_ENCRYPTION_KEY, SERVICE_API_KEY, ADMIN_PASSWORD

# 2. Socle + orchestration
docker compose --profile n8n up -d --build

# 3. Migrations
cd backend
$env:PYTHONPATH="$PWD"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m alembic upgrade head

# 4. Tests backend
.\.venv\Scripts\python.exe -m pytest tests -q

# 5. Console
cd ..\frontend
npm install
npm run dev            # http://127.0.0.1:5173/login  (compte admin du .env)

# 6. Tests frontend
npm test
npm run typecheck
$env:E2E_USER="admin"
$env:E2E_PASSWORD=(Select-String -Path ..\.env -Pattern '^ADMIN_PASSWORD=(.+)$').Matches[0].Groups[1].Value
npm run test:e2e

# 7. Redéployer sur AWS (instance démarrée, tunnel ouvert) : transférer le code puis
#    sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build
#    + alembic upgrade head + ajouter SERVICE_API_KEY / ADMIN_PASSWORD au .env du serveur
```
