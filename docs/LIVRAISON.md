# Livraison — SOAR IOC Factory (17/11/2026)

Plateforme de Cyber Threat Intelligence et de gestion automatisée du cycle de
vie des IOC, avec console SOC, contrôle d'accès par rôles et déploiement AWS.
Stack : FastAPI · PostgreSQL 16 · SQLAlchemy · Alembic · React 19 ·
TypeScript · Tailwind 4 · Recharts · n8n · Docker Compose.

Livrables : rapport de projet `reports/RAPPORT_SOAR_IOC_FACTORY_PROJET.docx`
(29 pages, PDF à côté) et présentation de soutenance
`reports/PRESENTATION_SOAR_IOC_FACTORY_PROJET.pptx` (19 diapositives, notes
orateur).

---

## 1. Fonctionnalités

### API et moteur
- **Pipeline complet** : collecte (7 sources réelles + collecteur de
  laboratoire marqué), normalisation, déduplication par empreinte SHA-256,
  enrichissement OTX / AbuseIPDB, score explicable, décision, publication
  relue, surveillance, expiration et retrait vérifié.
- **Contrôle d'accès** : JWT + Argon2id, rôles `viewer / analyst / admin`,
  verrouillage après 5 échecs, administration des comptes, premier
  administrateur créé depuis `.env`, connexion journalisée
  (`app/api/auth.py`, `app/core/security.py`).
- **Automatisation** : 8 workflows n8n authentifiés par clé de service
  (`X-API-Key`, lue dans l'environnement n8n) et signés dans l'audit
  (`X-Actor: workflow-N`).
- **API SOC** (`app/api/soc.py`) : état des intégrations (sondes réelles),
  notifications, funnel du cycle de vie avec preuve, série temporelle, sources
  et historique des collectes, Detection Center et qualification, historique
  des exécutions avec durée mesurée, dossier complet d'un IOC, recherche
  globale.
- **Traçabilité** : journal append-only (trigger PostgreSQL) ; chaque
  exécution de pipeline enregistre sa durée réelle (`duration_ms`).
- **Durcissement** : limitation de débit, en-têtes de sécurité, CORS
  restreint, validation sans écho des valeurs soumises, refus de démarrer en
  production avec une configuration faible, Swagger désactivé en production,
  lecture des capteurs limitée à `SENSOR_ROOT`, TLS MISP vérifié par défaut.

### Console SOC
- Barre latérale rétractable (tiroir mobile), fil d'Ariane, recherche
  `Ctrl K`, notifications, menu profil, lien d'évitement.
- 13 pages : Login, SOC Overview, Detection Center, Threat Intelligence,
  dossier IOC, IOC Lifecycle, Scoring & Risk, Sources, Automation Center,
  Audit Center, Rapports, System Health, Utilisateurs.
- Toutes alimentées par l'API ; squelettes de chargement, erreurs explicites
  (HTTP + réessai), états vides rédigés, confirmation avant toute action,
  notifications reflétant la réponse réelle de l'API.
- Code découpé par page ; polices embarquées (CSP stricte) ; design system
  documenté dans `docs/DESIGN_SYSTEM.md`.

### Déploiement
- **Local** : Docker Compose, tous les ports sur 127.0.0.1.
- **AWS EC2** (t2.large, us-east-1) : accès uniquement par tunnel SSH ;
  vérifié : 401 sans jeton, CSP active, nginx UID 101, ports sur 127.0.0.1,
  exécution n8n `success`, Playwright 8/8 via le tunnel.

---

## 2. Fonctionnalités partielles

| Élément | État | Ce qui manque |
|---|---|---|
| Sévérité Wazuh | dérivée du niveau de règle quand l'alerte le contient | 4 alertes enregistrées sans niveau → « non fournie » (pas d'estimation) |
| Durée des exécutions | mesurée pour chaque exécution qui la fournit | les exécutions sans mesure sont affichées « non mesurée » |
| Notifications | calculées sur 48 h, lu/non lu par poste | pas de notification push ni d'e-mail |

## 3. Hors d'atteinte faute d'accès ou de configuration

| Élément | Raison | Comportement de la plateforme |
|---|---|---|
| Publication / révocation **MISP réelle** | aucun serveur MISP ni clé | client REST + 18 tests sur transport simulé ; « Configuration manquante » ; endpoint `skipped` |
| Alertes Suricata / Wazuh en continu | capteurs non démarrés en continu | ingestion sur fichiers montés en lecture seule ; « Aucune donnée » si absent |

---

## 4. Validation

| Suite | Commande | Résultat |
|---|---|---|
| API et moteur (pytest, PostgreSQL de test migré) | `pytest tests -q` | **224 passed** |
| Console (Vitest + React Testing Library) | `npm test` | **23 passed** |
| Bout en bout local (Playwright, Chrome, pile réelle) | `npm run test:e2e` | **8 passed** |
| Bout en bout AWS (via le tunnel SSH) | `E2E_BASE_URL=http://127.0.0.1:8091 npm run test:e2e` | **8 passed** |
| Typage TypeScript | `npm run typecheck` | 0 erreur |
| Build de production | `npm run build` | OK |
| Migrations | `alembic upgrade head` | `b7e41c2a9f10` (head) |
| n8n → API | `n8n execute` (workflows 3, 4, 5, 8) | `status: success` |
| Contrôle visuel | captures `capture/2026-11-17/` | bureau 1440 px et mobile 390 px, aucun débordement |
| Sécurité | Bandit, pip-audit, npm audit, Trivy, OWASP ZAP | **0 vulnérabilité ouverte**, 2 avertissements ZAP documentés (`SECURITY.md`) |

La campagne de validation a détecté et fait corriger cinq défauts avant mise en
service, chacun couvert ensuite par un test : collision entre la page de santé
et la sonde `/health`, état des sources incohérent, erreur sur les détections
manuelles, adresse cliente non IP au login, polices bloquées par la CSP.

---

## 5. Limites et risques résiduels

- Jeton dans `sessionStorage` (atténué par la CSP stricte et 60 min de
  validité) ; pas de révocation individuelle de jeton (désactiver le compte
  la remplace).
- Limitation de débit en mémoire, par processus (à porter au reverse proxy si
  plusieurs workers).
- `style-src 'unsafe-inline'` requis par les styles inline React/Recharts
  (aucun script inline).
- Un seul rôle PostgreSQL (propriétaire du schéma) pour l'API et les
  migrations.
- Pas de TLS entre conteneurs (réseau bridge mono-hôte).
- Les bases locale et AWS sont indépendantes, sans synchronisation.
- Pas de vérité terrain : précision et rappel non calculés.

---

## 6. Commandes

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

# 6. Tests console
npm test
npm run typecheck
$env:E2E_USER="admin"
$env:E2E_PASSWORD=(Select-String -Path ..\.env -Pattern '^ADMIN_PASSWORD=(.+)$').Matches[0].Groups[1].Value
npm run test:e2e

# 7. Serveur AWS (instance démarrée) : transférer le code puis
#    sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build
#    + infrastructure/aws/run_migrations.sh ; SERVICE_API_KEY / ADMIN_PASSWORD dans le .env du serveur
```
