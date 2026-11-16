# SOAR IOC Factory

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![n8n](https://img.shields.io/badge/n8n-8_workflows-EA4B71?logo=n8n&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-EC2-FF9900?logo=amazonwebservices&logoColor=white)
![Tests](https://img.shields.io/badge/tests-224_backend_%2B_31_frontend-brightgreen)
![Auth](https://img.shields.io/badge/auth-JWT_%2B_RBAC-2cc2a6)
![Security](https://img.shields.io/badge/Trivy%20%C2%B7%20pip--audit%20%C2%B7%20ZAP-0_open_finding-brightgreen)

![Console SOC v0.2](capture/2026-11-16/v2-02-overview.png)

> Usine à indicateurs de compromission : **collecter → normaliser → dédupliquer →
> enrichir → noter → décider → publier → surveiller → expirer → retirer**,
> avec preuve, journal d'audit et tableau de bord SOC.

Projet 3 — plateforme SOAR de production d'IOC, livrée avec son automatisation
n8n, ses intégrations SOC (Suricata, Wazuh, MISP), son déploiement AWS et son
évaluation mesurée.

---

## Ce que fait la plateforme

| Étape | Ce qui se passe réellement | Preuve |
|---|---|---|
| **Collecte** | 7 collecteurs actifs (OTX, URLscan, Blocklist.de, Feodo Tracker, URLhaus, ThreatFox, MalwareBazaar) + collecteur synthétique de laboratoire | `audit_logs.action='COLLECT'` |
| **Normalisation** | validation stricte (IP, domaine, URL, MD5/SHA1/SHA256), forme canonique unique | `app/services/normalization.py` |
| **Déduplication** | empreinte SHA-256 `TYPE:value`, doublons reliés par `duplicate_of` | taux mesuré : **23,4 %** |
| **Enrichissement** | OTX + AbuseIPDB, cache 24 h, erreurs jamais transformées en verdict | **182** IOC enrichis |
| **Notation** | 5 composantes pondérées + pénalités faux positifs, **explication stockée** | `score_breakdown`, 100 % des scores |
| **Décision** | ≥ 80 publier · 50-79 surveiller · < 50 rejeter | seuils configurables |
| **Publication** | écriture puis **relecture** avant de marquer « vérifié » | `publications.status` |
| **Surveillance** | alertes Suricata / Wazuh rapprochées de l'inventaire | 16 détections réelles |
| **Expiration / retrait** | révocation confirmée avant de passer `REMOVED` | cycle complet mesuré : **34,2 min** |
| **Traçabilité** | journal **append-only** protégé par trigger PostgreSQL | 27 tests de sécurité |

Rien n'est inventé : si un fournisseur échoue, l'erreur est conservée et
affichée ; si une donnée n'a pas pu être mesurée, la documentation le dit.

---

## Chiffres au 14/11/2026

Source de vérité : [`reports/evaluation/metrics.json`](reports/evaluation/metrics.json).

| Indicateur | Valeur mesurée |
|---|---|
| Indicateurs en base | **217** (99 domaines, 58 IP, 41 hachages, 19 URL) |
| Scores calculés | **217 / 217** (100 %) |
| Score moyen / médian | **52,4 / 54** (min 37, max 82) |
| Décisions | 1 publier · 132 surveiller · 83 rejeter |
| Doublons écartés | **67** (taux de dédup **23,4 %**) |
| Enrichissements | **194** résultats sur **182** IOC (83,9 %) |
| Détections rapprochées | **16** (Suricata 2, Wazuh 4, manuel 10) |
| Latence à chaud (ingestion → score) | **81,8 s** par lot, **1,32 IOC/s** |
| Réduction du temps de traitement | **×12,5** (modèle manuel explicite, voir limites) |
| Tests automatisés | **192** (dont 27 de sécurité) — au 16/11 : **224** backend + **31** frontend (23 Vitest, 8 Playwright) |

> Le facteur ×12,5 compare la plateforme mesurée à un **modèle manuel posé
> comme hypothèse** (17 min/IOC), pas à un historique réel. L'hypothèse est
> détaillée et modifiable dans `scripts/evaluate_platform.py`.

---

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        OTX[AlienVault OTX]
        US[URLscan]
        BL[Blocklist.de]
        FD[Feodo Tracker]
        UH[URLhaus]
        TF[ThreatFox]
        MB[MalwareBazaar]
    end

    subgraph Coeur["Usine (FastAPI + PostgreSQL 16)"]
        ING[Ingestion<br/>normalisation + dedup]
        ENR[Enrichissement<br/>OTX / AbuseIPDB]
        SCO[Notation explicable]
        DEC{Décision}
        PUB[Publication vérifiée]
        EXP[Expiration / retrait]
    end

    subgraph SOC
        SUR[Suricata]
        WAZ[Wazuh]
        MISP[MISP]
    end

    subgraph Pilotage
        N8N[n8n — 8 workflows]
        DASH[Dashboard React — 13 pages]
        API[REST API — 25 routes]
    end

    OTX & US & BL & FD & UH & TF & MB --> ING --> ENR --> SCO --> DEC
    DEC -->|>= 80| PUB --> SUR
    DEC -->|50-79| MON[Surveillance] --> SUR & WAZ
    DEC -->|< 50| REJ[Rejet]
    PUB -.-> MISP
    SUR & WAZ --> MON --> SCO
    MON --> EXP
    N8N --> API
    DASH --> API
    API --- Coeur
```

Détail complet : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Démarrage rapide (local, ≈ 2 minutes)

Prérequis : Docker Desktop, Python 3.11, Node 20+.

```powershell
# 1. Socle : PostgreSQL + API + n8n
docker compose --profile n8n up -d

# 2. Vérifications
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health

# 3. Console SOC
cd frontend
npm install      # une seule fois
npm run dev      # -> http://127.0.0.1:5173/login
```

Connexion avec le compte administrateur défini dans `.env`
(`ADMIN_USERNAME` / `ADMIN_PASSWORD`, créé au premier démarrage).

| Accès | URL |
|---|---|
| Console SOC (13 pages, authentifiée) | <http://127.0.0.1:5173/> |
| API + Swagger (désactivé en production) | <http://127.0.0.1:8000/docs> |
| n8n (8 workflows, clé de service) | <http://127.0.0.1:5678> |

Procédure détaillée (installation, AWS, fermeture, pièges connus) :
[`OUVRIR_LE_PROJET.md`](OUVRIR_LE_PROJET.md) et
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

---

## Aperçu — console v0.2 (16/11/2026)

| Detection Center | Dossier de preuve d'un IOC |
|---|---|
| ![Detection Center](capture/2026-11-16/v2-03-detection-center.png) | ![Dossier IOC](capture/2026-11-16/v2-05-ioc-detail.png) |
| **IOC Lifecycle (10 étapes prouvées)** | **Sources : état réel et historique** |
| ![Cycle de vie](capture/2026-11-16/v2-06-lifecycle.png) | ![Sources](capture/2026-11-16/v2-08-sources.png) |
| **Automation Center** | **System Health** |
| ![Automation](capture/2026-11-16/v2-09-automation.png) | ![Santé](capture/2026-11-16/v2-11-system-health.png) |

Nouveautés v0.2 : authentification JWT + rôles (lecteur / analyste /
administrateur), console SOC redessinée (design system dédié, recherche
`Ctrl K`, notifications, confirmations), Detection Center avec qualification
des alertes, état réel des intégrations, durées d'exécution mesurées,
durcissement (rate limiting, CSP, images non-root, dépendances corrigées).
Détail : [`docs/LIVRAISON_V2.md`](docs/LIVRAISON_V2.md) · rapport
[`reports/RAPPORT_V2_SOAR_IOC_FACTORY.docx`](reports/RAPPORT_V2_SOAR_IOC_FACTORY.docx)
(18 pages, PDF à côté) · soutenance
[`reports/PRESENTATION_V2_SOAR_IOC_FACTORY.pptx`](reports/PRESENTATION_V2_SOAR_IOC_FACTORY.pptx) (14 diapositives).

### Console v0.1 (14/11/2026)

| Inventaire des IOC | Sources de threat intelligence |
|---|---|
| ![Inventaire](capture/2026-11-14/13-inventaire.jpg) | ![Sources](capture/2026-11-14/13b-sources.jpg) |
| **Score explicable** | **Fiche IOC** |
| ![Scoring](capture/2026-11-14/14-scoring-detail.jpg) | ![Fiche IOC](capture/2026-11-14/15-ioc-detail.jpg) |
| **Cycle de vie** | **Indicateurs publiés** |
| ![Cycle de vie](capture/2026-11-14/16-cycle-de-vie.jpg) | ![Publiés](capture/2026-11-14/17-publies.jpg) |
| **Détections Suricata / Wazuh** | **Workflows n8n** |
| ![Détections](capture/2026-11-14/18-detections.jpg) | ![Workflows](capture/2026-11-14/19-workflows.jpg) |
| **Journal d'audit append-only** | **Santé du système** |
| ![Audit](capture/2026-11-14/20-audit.jpg) | ![Santé](capture/2026-11-14/21-system-health.jpg) |

> **Publication publique** : les identifiants d'infrastructure (compte AWS,
> instance, security groups, IP d'administration) et les données personnelles
> ont été remplacés dans le dépôt et dans son historique par des commentaires
> `[masqué : …]`. Les adresses IP restantes sont des **IOC issus de flux
> publics** (données du projet), pas de l'infrastructure.

### Captures par phase

| # | Écran | Fichier |
|---|---|---|
| 1 | Audit de l'environnement (Phase 0) | `capture/01-phase0-audit-environnement.jpg` |
| 2 | Socle API (Phase 2) | `capture/02-phase2-swagger-socle.jpg` |
| 3 | Tests au vert (Phase 3) | `capture/03-phase3-tests-104-verts.jpg` |
| 4 | Cycle de vie démontré | `capture/04-phase3-cycle-de-vie-demo.jpg` |
| 5 | Automatisation n8n (Phase 4) | `capture/05-phase4-n8n-automatisation.jpg` |
| 6 | Intégration SOC (Phase 5) | `capture/06-phase5-integration-soc.jpg` |
| 7 | Dashboard général | `capture/07-dashboard-general.jpg` |
| 8 | Graphiques du dashboard | `capture/07b-dashboard-graphiques.jpg` |
| 9 | Classement par score | `capture/08-scoring-classement.jpg` |
| 10 | Détail explicatif d'un score | `capture/08b-scoring-detail-explicatif.jpg` |
| 11 | Fiche IOC | `capture/09-ioc-detail.jpg` |
| 12 | Cycle de vie d'un IOC | `capture/09b-ioc-cycle-de-vie.jpg` |
| 13 | Santé système | `capture/10-system-health.jpg` |
| 14 | Déploiement AWS | `capture/11-aws-dashboard-ec2.jpg` |

---

## Documentation

| Document | Contenu |
|---|---|
| [`OUVRIR_LE_PROJET.md`](OUVRIR_LE_PROJET.md) | Ouvrir / fermer le projet (local + AWS) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Conception, modèle de données, choix techniques |
| [`docs/INSTALLATION.md`](docs/INSTALLATION.md) | Installation reproductible, configuration, dépannage |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | Les 8 workflows n8n, import, exécution, vérification |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Modèle de menace, contrôles, preuves, limites |
| [`docs/TESTING.md`](docs/TESTING.md) | Stratégie de test : 224 tests backend, 23 Vitest, 8 Playwright |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Utilisation de la console SOC (rôles, pages, états) |
| [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) | Direction artistique, jetons, composants, accessibilité |
| [`docs/LIVRAISON_V2.md`](docs/LIVRAISON_V2.md) | Livraison v0.2 : diagnostic, fonctionnalités, tests exécutés, limites |
| [`docs/architecture/GRAPH_REPORT.md`](docs/architecture/GRAPH_REPORT.md) | Carte du code (graphify) : 827 nœuds, aucune dépendance circulaire |
| [`docs/AWS_DEPLOYMENT.md`](docs/AWS_DEPLOYMENT.md) | Déploiement EC2, coûts, accès par tunnel |
| [`docs/PHASE0_AUDIT.md`](docs/PHASE0_AUDIT.md) | Audit initial de l'environnement |
| [`reports/evaluation/EVALUATION.md`](reports/evaluation/EVALUATION.md) | Évaluation Phase 7 (métriques + graphiques) |
| [`reports/RAPPORT_SOAR_IOC_FACTORY.docx`](reports/RAPPORT_SOAR_IOC_FACTORY.docx) | Rapport Word pour le jury (version courte) |
| [`reports/RAPPORT_FINAL.docx`](reports/RAPPORT_FINAL.docx) | Rapport final complet : 19 chapitres + 5 annexes, 22 figures |

---

## Structure du dépôt

```
backend/            API FastAPI, moteur, tests (224)
  app/api/          25 routes REST
  app/services/     ingestion, normalisation, pipeline, MISP
  app/scoring/      moteur de notation explicable
  app/lifecycle/    machine à états
  app/collectors/   OTX, URLscan, Blocklist.de, Feodo, URLhaus, ThreatFox, MalwareBazaar, synthétique
  app/enrichment/   OTX, AbuseIPDB, agrégation + cache
  app/integrations/ Suricata, Wazuh, MISP
  tests/            10 modules de tests
database/           schéma SQL + migrations Alembic
frontend/           React 19 + TypeScript + Tailwind 4 + Recharts 3
infrastructure/     Dockerfiles, scripts AWS idempotents
integrations/       règles Suricata, décodeurs Wazuh, client MISP
workflows/n8n/      8 workflows exportés (importables)
scripts/            génération, évaluation, rapport, purge
docs/               documentation
reports/            rapport Word, évaluation, figures
capture/            14 captures d'écran
```

---

## Sécurité (résumé)

- **Aucun port exposé publiquement** : toutes les publications Docker sont sur
  `127.0.0.1` ; sur EC2, accès **uniquement par tunnel SSH** (vérifié 4 façons).
- **SSH restreint à l'IP de l'administrateur** (`/32`) depuis le 14/11/2026 ; la
  règle `0.0.0.0/0` du security group a été retirée après vérification
  (`docs/AWS_DEPLOYMENT.md` §2.2).
- **Secrets hors du dépôt** : `.env`, `*.pem`, clés AWS ignorés par git ;
  test automatisé qui vérifie qu'aucun secret n'est suivi.
- **Journal d'audit append-only** : trigger PostgreSQL qui refuse UPDATE/DELETE.
- **Entrées hostiles rejetées** : validation stricte, aucune concaténation SQL.
- **Aucune affirmation non vérifiée** : une publication n'est marquée vérifiée
  qu'après relecture ; une révocation n'est acceptée qu'après confirmation.
- **Aucune infrastructure réelle bloquée** : les IOC sont publiés vers une liste
  de détection de laboratoire, jamais vers un pare-feu de production.
- **Authentification et rôles (v0.2)** : JWT + Argon2id, lecteur / analyste /
  administrateur, verrouillage après 5 échecs, clé de service pour n8n,
  acteur d'audit toujours issu du jeton.
- **Durcissement (v0.2)** : rate limiting, CSP stricte, en-têtes de sécurité,
  images non-root, garde de configuration en production ; Bandit, pip-audit,
  npm audit, Trivy et OWASP ZAP exécutés — 0 finding ouvert
  (`docs/SECURITY.md` § 7 bis).

Détail et limites assumées : [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Limites connues

1. **Collecte abuse.ch** : URLhaus, ThreatFox et MalwareBazaar sont **actifs**
   depuis le 14/11/2026 (clé `ABUSECH_AUTH_KEY` dans `.env`) ; l'exécution
   réelle s'est limitée à 15 indicateurs par source, pas à un suivi continu.
2. **MISP** : client REST complet + tests mockés ; serveur non déployé (images
   officielles non disponibles anonymement). L'endpoint répond honnêtement
   `skipped` tant que `MISP_URL` / `MISP_KEY` sont absents.
3. **Précision / rappel** : pas de vérité terrain annotée (les IOC viennent de
   flux publics) ; seuls des proxys mesurables sont revendiqués.
4. ~~API sans authentification~~ : **corrigé en v0.2** (JWT + rôles).
5. **Instance AWS** : v0.2 **déployée le 16/11/2026** (migration `b7e41c2a9f10`, 8 scénarios
   Playwright réussis via le tunnel SSH) ; sa base (94 IOC) reste distincte de la base locale.

---

## Régénérer les livrables

```powershell
# Métriques + graphiques + EVALUATION.md (lit la base réelle)
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py

# Rapport Word du jury (métriques live + figures + captures)
.\backend\.venv\Scripts\python.exe scripts\generate_report.py

# Rapport final complet (page de garde, sommaire, 32 tableaux, 22 figures)
.\backend\.venv\Scripts\python.exe scripts\build_final_report.py

# Procédure de démarrage en Word
.\backend\.venv\Scripts\python.exe scripts\md_to_docx.py OUVRIR_LE_PROJET.md "reports\PROCEDURE_OUVRIR_LE_PROJET.docx"

# Tests backend (224) — frontend : cd frontend; npm test; npm run test:e2e
cd backend
$env:PYTHONPATH="$PWD"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

*Projet académique — les données collectées proviennent de flux publics de
threat intelligence. Les indicateurs synthétiques éventuels portent
`is_synthetic = true`.*
