# SOAR IOC Factory

> Usine Ã  indicateurs de compromission : **collecter â†’ normaliser â†’ dÃ©dupliquer â†’
> enrichir â†’ noter â†’ dÃ©cider â†’ publier â†’ surveiller â†’ expirer â†’ retirer**,
> avec preuve, journal d'audit et tableau de bord SOC.

Projet 3 â€” plateforme SOAR de production d'IOC, livrÃ©e avec son automatisation
n8n, ses intÃ©grations SOC (Suricata, Wazuh, MISP), son dÃ©ploiement AWS et son
Ã©valuation mesurÃ©e.

---

## Ce que fait la plateforme

| Ã‰tape | Ce qui se passe rÃ©ellement | Preuve |
|---|---|---|
| **Collecte** | 4 collecteurs actifs (OTX, URLscan, Blocklist.de, Feodo Tracker) + collecteur synthÃ©tique de laboratoire | `audit_logs.action='COLLECT'` |
| **Normalisation** | validation stricte (IP, domaine, URL, MD5/SHA1/SHA256), forme canonique unique | `app/services/normalization.py` |
| **DÃ©duplication** | empreinte SHA-256 `TYPE:value`, doublons reliÃ©s par `duplicate_of` | taux mesurÃ© : **16,6 %** |
| **Enrichissement** | OTX + AbuseIPDB, cache 24 h, erreurs jamais transformÃ©es en verdict | **139** IOC enrichis |
| **Notation** | 5 composantes pondÃ©rÃ©es + pÃ©nalitÃ©s faux positifs, **explication stockÃ©e** | `score_breakdown`, 100 % des scores |
| **DÃ©cision** | â‰¥ 80 publier Â· 50-79 surveiller Â· < 50 rejeter | seuils configurables |
| **Publication** | Ã©criture puis **relecture** avant de marquer Â« vÃ©rifiÃ© Â» | `publications.status` |
| **Surveillance** | alertes Suricata / Wazuh rapprochÃ©es de l'inventaire | 16 dÃ©tections rÃ©elles |
| **Expiration / retrait** | rÃ©vocation confirmÃ©e avant de passer `REMOVED` | cycle complet mesurÃ© : **34,2 min** |
| **TraÃ§abilitÃ©** | journal **append-only** protÃ©gÃ© par trigger PostgreSQL | 27 tests de sÃ©curitÃ© |

Rien n'est inventÃ© : si un fournisseur Ã©choue, l'erreur est conservÃ©e et
affichÃ©e ; si une donnÃ©e n'a pas pu Ãªtre mesurÃ©e, la documentation le dit.

---

## Chiffres au 14/11/2026

Source de vÃ©ritÃ© : [`reports/evaluation/metrics.json`](reports/evaluation/metrics.json).

| Indicateur | Valeur mesurÃ©e |
|---|---|
| Indicateurs en base | **174** (93 domaines, 56 IP, 24 hachages, 1 URL) |
| Scores calculÃ©s | **174 / 174** (100 %) |
| Score moyen / mÃ©dian | **51,9 / 52** (min 37, max 82) |
| DÃ©cisions | 1 publier Â· 89 surveiller Â· 83 rejeter |
| Doublons Ã©cartÃ©s | **35** (taux de dÃ©dup **16,6 %**) |
| Enrichissements | **149** rÃ©sultats sur **139** IOC (79,9 %) |
| DÃ©tections rapprochÃ©es | **16** (Suricata 2, Wazuh 4, manuel 10) |
| Latence Ã  chaud (ingestion â†’ score) | **43,8 s** par lot, **1,48 IOC/s** |
| RÃ©duction du temps de traitement | **Ã—23,3** (modÃ¨le manuel explicite, voir limites) |
| Tests automatisÃ©s | **177** (dont 27 de sÃ©curitÃ©) |

> Le facteur Ã—23,3 compare la plateforme mesurÃ©e Ã  un **modÃ¨le manuel posÃ©
> comme hypothÃ¨se** (17 min/IOC), pas Ã  un historique rÃ©el. L'hypothÃ¨se est
> dÃ©taillÃ©e et modifiable dans `scripts/evaluate_platform.py`.

---

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        OTX[AlienVault OTX]
        US[URLscan]
        BL[Blocklist.de]
        FD[Feodo Tracker]
    end

    subgraph Coeur["Usine (FastAPI + PostgreSQL 16)"]
        ING[Ingestion<br/>normalisation + dedup]
        ENR[Enrichissement<br/>OTX / AbuseIPDB]
        SCO[Notation explicable]
        DEC{DÃ©cision}
        PUB[Publication vÃ©rifiÃ©e]
        EXP[Expiration / retrait]
    end

    subgraph SOC
        SUR[Suricata]
        WAZ[Wazuh]
        MISP[MISP]
    end

    subgraph Pilotage
        N8N[n8n â€” 8 workflows]
        DASH[Dashboard React â€” 13 pages]
        API[REST API â€” 25 routes]
    end

    OTX & US & BL & FD --> ING --> ENR --> SCO --> DEC
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

DÃ©tail complet : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## DÃ©marrage rapide (local, â‰ˆ 2 minutes)

PrÃ©requis : Docker Desktop, Python 3.11, Node 20+.

```powershell
# 1. Socle : PostgreSQL + API + n8n
docker compose --profile n8n up -d

# 2. VÃ©rifications
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health

# 3. Tableau de bord
cd frontend
npm install      # une seule fois
npm run dev      # -> http://127.0.0.1:5173/
```

| AccÃ¨s | URL |
|---|---|
| Dashboard SOC (13 pages) | <http://127.0.0.1:5173/> |
| API + Swagger | <http://127.0.0.1:8000/docs> |
| n8n (8 workflows) | <http://127.0.0.1:5678> |

ProcÃ©dure dÃ©taillÃ©e (installation, AWS, fermeture, piÃ¨ges connus) :
[`OUVRIR_LE_PROJET.md`](OUVRIR_LE_PROJET.md) et
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

---

## Captures

| # | Ã‰cran | Fichier |
|---|---|---|
| 1 | Audit de l'environnement (Phase 0) | `capture/01-phase0-audit-environnement.jpg` |
| 2 | Socle API (Phase 2) | `capture/02-phase2-swagger-socle.jpg` |
| 3 | Tests au vert (Phase 3) | `capture/03-phase3-tests-104-verts.jpg` |
| 4 | Cycle de vie dÃ©montrÃ© | `capture/04-phase3-cycle-de-vie-demo.jpg` |
| 5 | Automatisation n8n (Phase 4) | `capture/05-phase4-n8n-automatisation.jpg` |
| 6 | IntÃ©gration SOC (Phase 5) | `capture/06-phase5-integration-soc.jpg` |
| 7 | Dashboard gÃ©nÃ©ral | `capture/07-dashboard-general.jpg` |
| 8 | Graphiques du dashboard | `capture/07b-dashboard-graphiques.jpg` |
| 9 | Classement par score | `capture/08-scoring-classement.jpg` |
| 10 | DÃ©tail explicatif d'un score | `capture/08b-scoring-detail-explicatif.jpg` |
| 11 | Fiche IOC | `capture/09-ioc-detail.jpg` |
| 12 | Cycle de vie d'un IOC | `capture/09b-ioc-cycle-de-vie.jpg` |
| 13 | SantÃ© systÃ¨me | `capture/10-system-health.jpg` |
| 14 | DÃ©ploiement AWS | `capture/11-aws-dashboard-ec2.jpg` |

---

## Documentation

| Document | Contenu |
|---|---|
| [`OUVRIR_LE_PROJET.md`](OUVRIR_LE_PROJET.md) | Ouvrir / fermer le projet (local + AWS) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Conception, modÃ¨le de donnÃ©es, choix techniques |
| [`docs/INSTALLATION.md`](docs/INSTALLATION.md) | Installation reproductible, configuration, dÃ©pannage |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | Les 8 workflows n8n, import, exÃ©cution, vÃ©rification |
| [`docs/SECURITY.md`](docs/SECURITY.md) | ModÃ¨le de menace, contrÃ´les, preuves, limites |
| [`docs/TESTING.md`](docs/TESTING.md) | StratÃ©gie de test, 177 tests, ce qui n'est pas couvert |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Utilisation du dashboard et de l'API |
| [`docs/AWS_DEPLOYMENT.md`](docs/AWS_DEPLOYMENT.md) | DÃ©ploiement EC2, coÃ»ts, accÃ¨s par tunnel |
| [`docs/PHASE0_AUDIT.md`](docs/PHASE0_AUDIT.md) | Audit initial de l'environnement |
| [`reports/evaluation/EVALUATION.md`](reports/evaluation/EVALUATION.md) | Ã‰valuation Phase 7 (mÃ©triques + graphiques) |
| [`reports/RAPPORT_SOAR_IOC_FACTORY.docx`](reports/RAPPORT_SOAR_IOC_FACTORY.docx) | Rapport Word pour le jury (version courte) |
| [`reports/RAPPORT_FINAL.docx`](reports/RAPPORT_FINAL.docx) | Rapport final complet : 19 chapitres + 5 annexes, 22 figures |

---

## Structure du dÃ©pÃ´t

```
backend/            API FastAPI, moteur, tests (177)
  app/api/          25 routes REST
  app/services/     ingestion, normalisation, pipeline, MISP
  app/scoring/      moteur de notation explicable
  app/lifecycle/    machine Ã  Ã©tats
  app/collectors/   OTX, URLscan, Blocklist.de, Feodo, synthÃ©tique
  app/enrichment/   OTX, AbuseIPDB, agrÃ©gation + cache
  app/integrations/ Suricata, Wazuh, MISP
  tests/            9 modules de tests
database/           schÃ©ma SQL + migrations Alembic
frontend/           React 19 + TypeScript + Tailwind 4 + Recharts 3
infrastructure/     Dockerfiles, scripts AWS idempotents
integrations/       rÃ¨gles Suricata, dÃ©codeurs Wazuh, client MISP
workflows/n8n/      8 workflows exportÃ©s (importables)
scripts/            gÃ©nÃ©ration, Ã©valuation, rapport, purge
docs/               documentation
reports/            rapport Word, Ã©valuation, figures
capture/            14 captures d'Ã©cran
```

---

## SÃ©curitÃ© (rÃ©sumÃ©)

- **Aucun port exposÃ© publiquement** : toutes les publications Docker sont sur
  `127.0.0.1` ; sur EC2, accÃ¨s **uniquement par tunnel SSH** (vÃ©rifiÃ© 4 faÃ§ons).
- **SSH restreint Ã  l'IP de l'administrateur** (`/32`) depuis le 14/11/2026 ; la
  rÃ¨gle `0.0.0.0/0` du security group a Ã©tÃ© retirÃ©e aprÃ¨s vÃ©rification
  (`docs/AWS_DEPLOYMENT.md` Â§2.2).
- **Secrets hors du dÃ©pÃ´t** : `.env`, `*.pem`, clÃ©s AWS ignorÃ©s par git ;
  test automatisÃ© qui vÃ©rifie qu'aucun secret n'est suivi.
- **Journal d'audit append-only** : trigger PostgreSQL qui refuse UPDATE/DELETE.
- **EntrÃ©es hostiles rejetÃ©es** : validation stricte, aucune concatÃ©nation SQL.
- **Aucune affirmation non vÃ©rifiÃ©e** : une publication n'est marquÃ©e vÃ©rifiÃ©e
  qu'aprÃ¨s relecture ; une rÃ©vocation n'est acceptÃ©e qu'aprÃ¨s confirmation.
- **Aucune infrastructure rÃ©elle bloquÃ©e** : les IOC sont publiÃ©s vers une liste
  de dÃ©tection de laboratoire, jamais vers un pare-feu de production.

DÃ©tail et limites assumÃ©es : [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Limites connues

1. **ClÃ© abuse.ch refusÃ©e** (`unknown_auth_key`) : URLhaus / ThreatFox /
   MalwareBazaar sont cÃ¢blÃ©s mais **inactifs**. Aucune donnÃ©e n'a Ã©tÃ© simulÃ©e
   pour compenser.
2. **MISP** : client REST complet + tests mockÃ©s ; serveur non dÃ©ployÃ© (images
   officielles non disponibles anonymement). L'endpoint rÃ©pond honnÃªtement
   `skipped` tant que `MISP_URL` / `MISP_KEY` sont absents.
3. **PrÃ©cision / rappel** : pas de vÃ©ritÃ© terrain annotÃ©e (les IOC viennent de
   flux publics) ; seuls des proxys mesurables sont revendiquÃ©s.
4. **API sans authentification** : assumÃ© pour un laboratoire fermÃ© sur
   `127.0.0.1` ; Ã  ajouter avant tout usage multi-utilisateur.

---

## RÃ©gÃ©nÃ©rer les livrables

```powershell
# MÃ©triques + graphiques + EVALUATION.md (lit la base rÃ©elle)
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py

# Rapport Word du jury (mÃ©triques live + figures + captures)
.\backend\.venv\Scripts\python.exe scripts\generate_report.py

# Rapport final complet (page de garde, sommaire, 32 tableaux, 22 figures)
.\backend\.venv\Scripts\python.exe scripts\build_final_report.py

# ProcÃ©dure de dÃ©marrage en Word
.\backend\.venv\Scripts\python.exe scripts\md_to_docx.py OUVRIR_LE_PROJET.md "reports\PROCEDURE_OUVRIR_LE_PROJET.docx"

# Tests (177)
cd backend
$env:PYTHONPATH="$PWD"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

*Projet acadÃ©mique â€” les donnÃ©es collectÃ©es proviennent de flux publics de
threat intelligence. Les indicateurs synthÃ©tiques Ã©ventuels portent
`is_synthetic = true`.*
