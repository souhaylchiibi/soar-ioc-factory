# BRIEF — Rapport final du projet SOAR IOC Factory

> **À qui ce fichier s'adresse :** à Claude Code (ou tout assistant de génération de
> documents) chargé de produire le **rapport final de projet** à partir du dépôt.
> **But :** obtenir un rapport juste, complet et vérifiable, sans jamais inventer de
> chiffre, en réutilisant les preuves déjà présentes dans le dépôt.
>
> Rédigé le 14/11/2026. Toutes les valeurs citées ont été lues en base ou via l'API
> à cette date — elles restent des **instantanés** : en cas de doute, relire
> `reports/evaluation/metrics.json` plutôt que ce fichier.

---

## 0. Prompt à coller dans Claude Code

```text
Tu es chargé de rédiger le rapport final du projet "SOAR IOC Factory" (Projet 3 —
usine à indicateurs de compromission) pour un jury académique. La langue du rapport
est le français ; le code et les commentaires du dépôt restent en anglais.

Étape 1 — Lis, dans cet ordre, et sans rien modifier :
  1. BRIEF_CLAUDE_RAPPORT.md (ce fichier)
  2. README.md
  3. docs/ARCHITECTURE.md
  4. reports/evaluation/EVALUATION.md
  5. reports/evaluation/metrics.json
  6. docs/TESTING.md, docs/SECURITY.md, docs/WORKFLOWS.md, docs/USER_GUIDE.md
  7. docs/AWS_DEPLOYMENT.md

Étape 2 — Vérifie l'état réel avant d'écrire (lecture seule) :
  - git log --oneline | head -20 ; git status --short
  - curl http://127.0.0.1:8000/api/v1/system/health
  - curl http://127.0.0.1:8000/api/v1/iocs/stats/dashboard
  - python -m pytest backend/tests -q (si l'environnement le permet)

Étape 3 — Produis le rapport :
  - plan imposé : voir §6 du brief ;
  - chaque chiffre doit être traçable vers metrics.json, l'API ou un fichier cité ;
  - les figures sont reports/figures/eval_01..07*.png et capture/*.jpg ;
  - génère docs/RAPPORT_FINAL.md puis reports/RAPPORT_FINAL.docx
    (convertisseur fourni : scripts/md_to_docx.py) ;
  - ne supprime ni ne réécris les livrables existants.

Contraintes absolues :
  - AUCUN chiffre inventé, aucune capture inventée, aucun résultat simulé.
  - Ne lis jamais .env et ne manipule jamais *.pem ni de clés.
  - N'exécute AUCUNE commande AWS (pas de start/stop/create/delete).
  - Aucune action destructive (pas de docker compose down -v, pas de purge).
  - Si une donnée manque, écris "non mesuré" et explique pourquoi.

Livrables attendus : docs/RAPPORT_FINAL.md + reports/RAPPORT_FINAL.docx, plus une
liste des écarts/incohérences éventuellement détectés dans les documents existants.
```

---

## 1. Règles absolues (non négociables)

1. **Zéro invention.** Un chiffre sans source est un défaut grave. Si une valeur est
   absente, écrire « non mesuré » ou « non disponible », jamais une estimation
   présentée comme une mesure.
2. **Distinguer les trois natures de chiffres** : *mesuré* (base/API), *hypothèse*
   (modèle manuel de comparaison), *non mesurable* (précision/rappel sans vérité
   terrain).
3. **Aucun secret** dans le rapport : pas de mot de passe, pas de clé API, pas de
   jeton AWS, pas de contenu de `.env`, pas de clé privée.
4. **Aucune action cloud.** Le rapport décrit ce qui existe ; il ne crée, ne démarre
   et n'arrête rien.
5. **Aucune action destructive.** Pas de purge, pas de `down -v`, pas de suppression
   de fichiers existants.
6. **Traçabilité.** Chaque affirmation technique renvoie à un fichier, une route,
   une table ou un test.
7. **Honnêteté sur les limites.** Les manques sont listés explicitement (§9).

---

## 2. Le projet en une page

**SOAR IOC Factory** automatise le cycle de vie complet des indicateurs de
compromission :

> collecte → normalisation → déduplication → enrichissement → notation →
> décision → publication → surveillance → expiration → retrait vérifié

- **Backend** : FastAPI + SQLAlchemy 2 + Pydantic 2, Python 3.11, PostgreSQL 16.
- **Orchestration** : 8 workflows n8n (JSON exportés, IDs stables).
- **Frontend** : React 19 + TypeScript + Tailwind 4 + Recharts 3 — 13 routes.
- **Intégrations SOC** : Suricata (rejeu PCAP par lots), Wazuh 4.12 (alertes
  réelles), client MISP REST (serveur non déployé).
- **Déploiement** : Docker Compose, profils mémoire (`n8n`, `detection`, `misp`),
  instance EC2 existante réutilisée, accès par tunnel SSH uniquement.
- **Preuve** : journal d'audit PostgreSQL **append-only** (trigger), 177 tests
  automatisés sur un vrai PostgreSQL, évaluation mesurée depuis la base.

**Ce qui distingue le projet** : la plateforme refuse de mentir. Une publication
n'est marquée « vérifiée » qu'après relecture ; une révocation non confirmée
empêche le passage à `REMOVED` ; un fournisseur en panne n'est jamais transformé en
verdict « bénin ».

---

## 3. Chiffres vérifiés (instantané du 14/11/2026)

Toujours recoupables dans `reports/evaluation/metrics.json` (généré par
`scripts/evaluate_platform.py`).

### 3.1 Inventaire local (base `soar_ioc`)

| Mesure | Valeur |
|---|---|
| Indicateurs en base | **174** |
| Répartition par type | DOMAIN 93 · IP 56 · HASH_SHA256 11 · HASH_MD5 8 · HASH_SHA1 5 · URL 1 |
| Niveaux de risque | MEDIUM 87 · LOW 83 · CRITICAL 2 · HIGH 2 |
| Statuts actuels | MONITORED 89 · REJECTED 83 · PUBLISHED 1 · REMOVED 1 |
| Indicateurs synthétiques (`is_synthetic`) | **0** |
| Date d'expiration renseignée | 1 |

### 3.2 Qualité et déduplication

| Mesure | Valeur |
|---|---|
| Éléments bruts collectés | 210 |
| Créés / mis à jour | 174 / 35 |
| Doublons écartés (événements `DEDUP`) | 35 |
| Valeurs invalides rejetées | 1 |
| Taux de déduplication (`DEDUP / (NORMALIZE + DEDUP)`) | **16,6 %** |

### 3.3 Enrichissement

| Mesure | Valeur |
|---|---|
| Résultats stockés | 149 (OTX 140 · AbuseIPDB 9) |
| Indicateurs enrichis | 139 / 174 (**79,9 %**) |
| Succès / erreurs fournisseurs | 91,9 % / 12 erreurs |

### 3.4 Notation et décisions

| Mesure | Valeur |
|---|---|
| Indicateurs notés | 174 / 174 (**100 %**) |
| Score moyen / médian / p95 | **51,9 / 52 / 64** |
| Score min / max | 37 / 82 |
| Scores expliqués (`score_breakdown` persisté) | 174 (**100 %**) |
| Décisions | publier **1** · surveiller **89** · rejeter **83** |
| Politique de score | `v1` |

Contribution moyenne des composantes (sur 100) : fiabilité de la source 17,39/25
(69,6 %) · fraîcheur 15,03/20 (75,1 %) · sources indépendantes 8,61/20 (43,0 %) ·
consensus d'enrichissement 10,67/20 (53,4 %) · détections observées 0,17/15 (1,1 %).

> Conséquence à expliquer dans le rapport : sans détection, le score plafonne vers
> **67/100** ; publier (≥ 80) exige donc une **observation réelle** par un capteur,
> pas un empilement de sources.

### 3.5 Publication, détection, cycle de vie

| Mesure | Valeur |
|---|---|
| Publications enregistrées | 2 (1 vérifiée active, 1 révoquée) |
| Détections rapprochées | **16** sur **2** indicateurs (manual 10 · Wazuh 4 · Suricata 2) |
| Faux positifs observés | 0 (0,0 %) |
| Transitions de cycle de vie journalisées | 700 |
| Cycle complet mesuré (NEW → REMOVED) | **2050,8 s ≈ 34,2 min**, 7 transitions |

### 3.6 Performance

| Mesure | Valeur |
|---|---|
| Latence à chaud (ingestion → score) | **43,8 s** en moyenne sur **65** indicateurs |
| Débit du lot à chaud | **1,48 indicateur/s** |
| Backlog repris après arrêt volontaire | 109 indicateurs, 163,6 h en moyenne — **exclu** de la latence à chaud |
| Moteur de notation (CPU pur) | **27 159 scores/s** (36,8 µs/score) |

### 3.7 Automatisation : hypothèse vs mesure

| Comparaison | Valeur |
|---|---|
| Modèle manuel par IOC — **HYPOTHÈSE** | **17 min** (1 + 2 + 2 + 4 + 3 + 4 + 1) |
| Plateforme par IOC — **MESURÉ** | **0,73 min** |
| Facteur de réduction | **×23,3** |
| Charge pour cet inventaire | 49,3 h (hypothèse) vs 2,12 h (mesuré) |
| Temps économisé | 47,2 h (hypothèse) |

> Le modèle manuel vit dans `MANUAL_BASELINE` (`scripts/evaluate_platform.py`) et
> est modifiable. Il ne doit **jamais** être présenté comme un historique mesuré.

### 3.8 Tests

**177 tests, 177 au vert (~42 s)**, sur un vrai PostgreSQL (`soar_ioc_test`, migré
par Alembic) — pas de SQLite de substitution.

| Module | Tests |
|---|---:|
| `test_normalization.py` | 35 |
| `test_security.py` | 27 |
| `test_lifecycle.py` | 23 |
| `test_ingest.py` | 21 |
| `test_scoring.py` | 19 |
| `test_misp.py` | 18 |
| `test_providers.py` | 16 |
| `test_pipeline.py` | 11 |
| `test_health.py` | 7 |

### 3.9 Plateforme et dépôt

| Élément | Valeur |
|---|---|
| Routes API | 25 chemins / 27 opérations (`/openapi.json`) |
| Pages dashboard | 13 routes React |
| Workflows n8n | 8 (IDs stables) |
| Tables PostgreSQL | 13 (dont `alembic_version`) |
| Migration courante | `dadb423768cb` (head) |
| Captures d'écran | 14 `.jpg` dans `capture/` |
| Figures d'évaluation | 7 PNG dans `reports/figures/` |
| Commits | `git rev-list --count HEAD` (20 au 14/11/2026) |
| Fichiers suivis | `git ls-files \| wc -l` (160 au 14/11/2026) |

### 3.10 Sources de threat intelligence

| Source | Type | Fiabilité | Indicateurs |
|---|---|---:|---:|
| urlscan | OPEN_SOURCE | 70 | 79 |
| blocklist.de | COMMUNITY | 60 | 50 |
| AlienVault OTX | OPEN_SOURCE | 80 | 40 |
| Feodo Tracker | COMMUNITY | 75 | 5 |
| URLhaus | COMMUNITY | 70 | 0 (clé abuse.ch refusée) |
| synthetic_lab | SYNTHETIC | 50 | 0 |

### 3.11 Déploiement EC2 (second jeu de données, distinct du local)

| Mesure | Valeur |
|---|---|
| Instance | `[masqué : ID instance EC2]`, t2.large, us-east-1c |
| Inventaire EC2 | 94 IOC (73 actifs, 21 rejetés), score moyen 54,7 |
| Accès | tunnel SSH `-L 8091:127.0.0.1:80`, aucun port applicatif ouvert |
| SSH | restreint à l'IP de l'administrateur (`/32`) depuis le 14/11/2026 |
| Coût | ≈ 0,093 $/h (≈ 2,23 $/jour) quand l'instance tourne |

> Ne pas fusionner les deux inventaires : local (174) et EC2 (94) sont deux bases
> séparées. Le dire explicitement.

---

## 4. Sources de vérité (ordre de lecture)

| Fichier | Ce qu'on y trouve |
|---|---|
| `README.md` | entrée du projet, chiffres clés, accès, structure |
| `docs/ARCHITECTURE.md` | conception, modèle de données, choix techniques |
| `docs/PHASE0_AUDIT.md` | audit initial de l'environnement |
| `docs/AWS_DEPLOYMENT.md` | déploiement, coûts, sécurité, tunnel, durcissement |
| `docs/WORKFLOWS.md` | 8 workflows n8n, fréquences, routes, ID, vérification |
| `docs/SECURITY.md` | modèle de menace, contrôles, preuves, limites |
| `docs/TESTING.md` | stratégie, 177 tests, ce qui n'est pas couvert |
| `docs/USER_GUIDE.md` | dashboard et API côté utilisateur |
| `reports/evaluation/EVALUATION.md` | évaluation Phase 7 rédigée |
| `reports/evaluation/metrics.json` | **source de vérité chiffrée** |
| `reports/figures/eval_*.png` | 7 graphiques générés depuis la base |
| `capture/*.jpg` | 14 captures d'écran réelles |
| `backend/app/**` | code (normalisation, scoring, machine à états, pipeline) |
| `backend/tests/**` | 177 tests |
| `workflows/n8n/*.json` | workflows exportés |
| `database/migrations/**` | schéma Alembic |
| `infrastructure/**` | Dockerfiles, scripts AWS, compose |

**Ne pas se contenter de lire ce brief** : les chiffres doivent être recoupés.

---

## 5. Preuves disponibles (à citer dans le rapport)

### 5.1 Captures (`capture/`)

| Fichier | Contenu |
|---|---|
| `01-phase0-audit-environnement.jpg` | audit Phase 0 |
| `02-phase2-swagger-socle.jpg` | OpenAPI + healthchecks |
| `03-phase3-tests-104-verts.jpg` | rapport de tests du moteur (à l'époque 104) |
| `04-phase3-cycle-de-vie-demo.jpg` | cycle de vie démontré |
| `05-phase4-n8n-automatisation.jpg` | 8 workflows n8n |
| `06-phase5-integration-soc.jpg` | Suricata + Wazuh réels |
| `07-dashboard-general.jpg` | dashboard général |
| `07b-dashboard-graphiques.jpg` | graphiques |
| `08-scoring-classement.jpg` | classement par score |
| `08b-scoring-detail-explicatif.jpg` | détail explicatif d'un score |
| `09-ioc-detail.jpg` | fiche IOC |
| `09b-ioc-cycle-de-vie.jpg` | historique d'un IOC |
| `10-system-health.jpg` | santé système |
| `11-aws-dashboard-ec2.jpg` | dashboard sur EC2 |

### 5.2 Figures d'évaluation (`reports/figures/`)

| Fichier | Contenu |
|---|---|
| `eval_01_cycle_de_vie.png` | répartition par étape |
| `eval_02_scores.png` | distribution des scores et seuils |
| `eval_03_entonnoir.png` | entonnoir des transitions |
| `eval_04_enrichissement.png` | verdicts par fournisseur |
| `eval_05_collecte_dedup.png` | volume collecté et qualité |
| `eval_06_automatisation.png` | manuel (hypothèse) vs plateforme (mesuré) |
| `eval_07_sources.png` | contribution des sources |

### 5.3 Preuves techniques

- **Audit immuable** : trigger `trg_audit_immutable` ; tests
  `test_audit_rows_cannot_be_updated/deleted`, `test_trigger_is_present_in_schema`.
- **Anti-collusion** : comptage par `provenance_group` ; test
  `test_same_organisation_does_not_multiply_independent_sources`.
- **Refus de mentir** : publication vérifiée par relecture ; `REMOVED` impossible
  sans révocation confirmée ; MISP non configuré → réponse `{"status":"skipped"}`.
- **Entrées hostiles** : `'; DROP TABLE iocs; --` rejeté, table intacte.
- **Ports** : test automatisé qui refuse tout port publié hors `127.0.0.1`
  (compose local et AWS, y compris syntaxe longue).
- **Secrets** : tests `git ls-files`, `.gitignore`, motifs de credentials.
- **AWS** : relecture du security group après durcissement (`[masqué : ID règle SG]`,
  `0.0.0.0/0` retirée), test SSH réel, port 80 filtré depuis Internet.

---

## 6. Plan du rapport demandé

Le rapport doit être un **document de projet**, pas une simple collection de
captures. Plan imposé (adapter la numérotation si besoin, mais ne rien retirer) :

1. **Page de garde** — titre, sous-titre, candidat, contexte (Projet 3), date,
   environnement, nombre de tests/commits/captures.
2. **Résumé exécutif** (1 page) — problème, solution, 6 à 8 chiffres vérifiés,
   ce qui est démontré, ce qui ne l'est pas.
3. **Sommaire** et **table des figures**.
4. **Contexte et problématique** — pourquoi les IOC sont bruyants/dupliqués/
   obsolètes ; ce que doit faire une usine à indicateurs.
5. **Exigences** — les 10 étapes du cycle de vie, exigences de sécurité
   (pas d'exposition, pas de blocage réel, pas de secret), de traçabilité et
   d'automatisation.
6. **Architecture** — schéma (Mermaid ou figure), composants, flux, modèle de
   données (13 tables), machine à états (`TRANSITIONS`), séparation
   orchestration (n8n) / décision (API).
7. **Phase 0 — audit** — environnement, contraintes mémoire, décisions.
8. **Phase 1 — conception** — modèle, choix (PostgreSQL, Alembic, pas de SQLite).
9. **Phase 2 — socle** — API, healthchecks, Docker Compose, profils.
10. **Phase 3 — moteur IOC** — normalisation stricte, empreinte SHA-256
    `TYPE:value`, déduplication, enrichissement (cache 24 h, erreurs conservées),
    scoring explicable 5 composantes + pénalités, seuils 80/50, cycle de vie.
11. **Phase 4 — automatisation n8n** — tableau des 8 workflows (fichier, fréquence,
    route), idempotence, reprise, exécution CLI.
12. **Phase 5 — intégrations SOC** — Suricata (mode IDS, rejeu PCAP, sid dédiés),
    Wazuh (alertes réelles, volume partagé en lecture seule), MISP (client REST,
    vérification par relecture, serveur non déployé).
13. **Phase 6 — dashboard** — 13 routes, React/TS/Tailwind/Recharts, valeurs lues
    sur l'API, build sans erreur.
14. **Phase 7 — évaluation** — méthode (mesuré vs hypothèse), tableaux §3,
    les 7 figures, explication du plafond à 67 sans détection, performance à chaud
    vs backlog, facteur ×23,3 **explicitement étiqueté hypothèse**.
15. **Phase 8 — AWS** — instance réutilisée, zéro ressource créée, ports loopback,
    tunnel, durcissement SSH appliqué, coûts.
16. **Phase 9 — documentation et exploitation** — README, 5 guides, procédures
    d'ouverture/fermeture, reproductibilité.
17. **Sécurité** — modèle de menace (tableau), contrôles, preuves, risques résiduels.
18. **Tests** — 177 tests, répartition, ce qui n'est **pas** couvert (interface,
    charge, pentest), pourquoi.
19. **Limites et perspectives** — voir §9, plus les évolutions crédibles.
20. **Bilan** — ce qui est démontré, ce qui reste ouvert.
21. **Annexes** — A) 25 routes API ; B) schéma des 13 tables ; C) commandes ;
    D) liste des figures/captures ; E) glossaire des statuts.

### Style attendu

- Français professionnel, phrases courtes, pas de marketing.
- Chaque tableau a une source en légende (« source : metrics.json »,
  « source : API /stats/dashboard », « source : git »).
- Les captures et figures sont numérotées et **légendées** (ce qui est montré,
  quand, sur quel environnement).
- Pas de « nous » royal ; préférer « la plateforme », « le pipeline ».
- Les chiffres gardent la virgule décimale française à l'écrit (51,9) — le JSON
  utilise le point, c'est normal.

---

## 7. Livrables attendus

| Livrable | Chemin | Remarque |
|---|---|---|
| Rapport Markdown | `docs/RAPPORT_FINAL.md` | source éditable, versionnable |
| Rapport Word | `reports/RAPPORT_FINAL.docx` | conversion via `scripts/md_to_docx.py` |
| Liste d'écarts | `docs/RAPPORT_ECARTS.md` | incohérences détectées dans les docs existants |

**Ne pas écraser** `reports/RAPPORT_SOAR_IOC_FACTORY.docx` ni
`reports/PROCEDURE_OUVRIR_LE_PROJET.docx` : ce sont des livrables déjà remis.

Conversion :

```powershell
cd "C:\Users\T480s\Desktop\SOAR project"
.\backend\.venv\Scripts\python.exe scripts\md_to_docx.py docs\RAPPORT_FINAL.md "reports\RAPPORT_FINAL.docx"
```

---

## 8. Commandes utiles (lecture seule)

```powershell
# Santé et chiffres live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/iocs/stats/dashboard

# Régénérer les métriques + les 7 figures + EVALUATION.md (lit PostgreSQL)
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py

# Tests (177) — nécessite PostgreSQL local et le mot de passe dans .env
cd backend
$env:PYTHONPATH="$PWD"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m pytest tests -q

# Régénérer le rapport Word existant (référence de mise en forme)
.\backend\.venv\Scripts\python.exe scripts\generate_report.py
```

> `python` n'est pas dans le PATH sur ce poste : utiliser `py` ou
> `backend\.venv\Scripts\python.exe`.
> PowerShell 5.1 lit les `.ps1` sans BOM en ANSI : préférer les commandes directes
> ou des scripts Python en UTF-8 (`sys.stdout.reconfigure(encoding="utf-8")`).

---

## 9. Limites à énoncer honnêtement

1. **Précision / rappel non calculables** : pas de vérité terrain annotée (les IOC
   viennent de flux publics). Le rapport doit parler de *proxys mesurés* (taux de
   publication, couverture d'enrichissement, faux positifs observés), jamais de
   précision.
2. **Clé abuse.ch invalide** (`unknown_auth_key`) : URLhaus / ThreatFox /
   MalwareBazaar sont câblés mais **inactifs**. Aucune donnée n'a été simulée pour
   compenser.
3. **MISP non déployé** (option B) : client REST complet + 18 tests mockés ;
   l'endpoint répond `{"status":"skipped"}` sans `MISP_URL` / `MISP_KEY`.
4. **Faux positifs partiels** : seules les détections revues sont renseignées ;
   une détection non revue reste `NULL`, jamais comptée comme bénigne.
5. **Backlog** : 109 indicateurs traités après un arrêt volontaire de la plateforme
   (163,6 h en moyenne) — mesure d'indisponibilité, exclue de la latence à chaud.
6. **API sans authentification** : assumé en laboratoire mono-utilisateur sur
   `127.0.0.1` ; à corriger avant tout usage multi-utilisateur.
7. **Pas de tests frontend** : couverture par `tsc -b`, build Vite et vérification
   manuelle des 13 routes (0 erreur console), pas par des tests unitaires.
8. **Pas de CI** : contrainte du laboratoire ; le job `pytest` est documenté.
9. **IP administrateur dynamique** : le SSH est restreint à un `/32` ; si l'IP
   change, l'accès est refusé jusqu'à mise à jour (comportement attendu).
10. **Deux jeux de données** : local (174 IOC) et EC2 (94 IOC) sont séparés — ne pas
    les additionner ni les confondre.

---

## 10. Checklist avant de rendre

- [ ] Tous les chiffres du rapport se retrouvent dans `metrics.json`, l'API, ou un
      fichier cité.
- [ ] Aucune occurrence de « 150 tests » (chiffre périmé) ; le total est **177**.
- [ ] Aucun « TODO », « None », « indisponible » non justifié, aucune capture
      manquante.
- [ ] Le facteur **×23,3** est explicitement décrit comme une hypothèse.
- [ ] Les 7 figures d'évaluation et les 14 captures sont présentes et légendées.
- [ ] Le DOCX s'ouvre (test `python-docx`), contient le bon nombre de titres et de
      figures, et pèse un poids plausible (> 1 Mo).
- [ ] Aucun secret : recherche `ASIA`, `-----BEGIN`, `POSTGRES_PASSWORD=`,
      `MISP_KEY=` dans le document produit.
- [ ] La table des figures correspond aux figures réellement intégrées.
- [ ] Les limites du §9 sont reprises, sans être édulcorées.
- [ ] `git status` : seuls les nouveaux livrables apparaissent (pas de fichier
      temporaire, pas de `.env`, pas de `.pem`).

---

## 11. Ce qu'il ne faut surtout pas faire

- ❌ Inventer un chiffre « plausible » pour combler un trou.
- ❌ Présenter le modèle manuel (17 min/IOC) comme une mesure historique.
- ❌ Écrire que MISP est déployé ou que la clé abuse.ch fonctionne.
- ❌ Additionner local (174) et EC2 (94).
- ❌ Exécuter `docker compose down -v`, `docker volume rm`, `docker system prune`,
  `scripts/purge_lab_data.py`.
- ❌ Lancer une commande AWS (start/stop/create/delete) ou modifier un security group.
- ❌ Lire ou recopier `.env`, `*.pem`, jetons AWS.
- ❌ Modifier le code applicatif pour « faire coller » le rapport aux chiffres :
  c'est le rapport qui décrit le code, pas l'inverse.
- ❌ Supprimer ou renommer les livrables existants (`RAPPORT_SOAR_IOC_FACTORY.docx`,
  `PROCEDURE_OUVRIR_LE_PROJET.docx`, `capture/`, `reports/figures/`).

---

## 12. Contexte technique du poste

| Élément | Valeur |
|---|---|
| OS | Windows 10/11, PowerShell 5.1 |
| Python | 3.11 (`py -3.11`), venv `backend\.venv` |
| Node | 25.x, frontend `frontend/` (Vite, port 5173) |
| Docker | Docker Desktop, backend WSL2 |
| Stack locale | `soar-api` (8000), `soar-postgres` (5432), `soar-n8n` (5678) |
| Accès | API `http://127.0.0.1:8000`, dashboard `http://127.0.0.1:5173` |
| Tunnel EC2 | `http://127.0.0.1:8091` quand l'instance tourne |
| Base | `soar_ioc` (données), `soar_ioc_test` (tests) |

Encodage : les fichiers du dépôt sont en UTF-8 ; sous PowerShell, préférer
`Get-Content -Encoding UTF8` et éviter d'écrire des scripts `.ps1` sans BOM.

---

## 13. Critère de réussite

Le rapport est réussi si un membre du jury, sans accès au code, peut répondre à ces
questions **uniquement en le lisant** :

1. Quel problème le projet résout-il, et pour qui ?
2. Quelles sont les 10 étapes du cycle de vie, et où sont-elles implémentées ?
3. Comment une décision de publication est-elle prise, et pourquoi est-elle
   explicable ?
4. Qu'est-ce qui empêche la plateforme de publier un faux positif ou de mentir sur
   un retrait ?
5. Quels chiffres sont **mesurés**, lesquels sont **hypothétiques**, et pourquoi ?
6. Quelles sont les limites, et comment le projet les assume-t-il ?
7. Que se passe-t-il si un fournisseur tombe, si la base est attaquée, si l'IP
   change, si une clé est révoquée ?
