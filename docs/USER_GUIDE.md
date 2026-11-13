# Guide utilisateur — dashboard et API

> Public : analyste SOC, étudiant, membre du jury.
> Objectif : savoir quoi regarder, quoi faire, et comment lire les chiffres.

---

## 1. Accès

| Interface | URL | Prérequis |
|---|---|---|
| Dashboard SOC | <http://127.0.0.1:5173/> | `npm run dev` dans `frontend/` |
| Documentation API (Swagger) | <http://127.0.0.1:8000/docs> | stack Docker démarrée |
| n8n | <http://127.0.0.1:5678/> | profil `n8n` |
| EC2 (via tunnel) | <http://127.0.0.1:8091/> | tunnel SSH actif |

Démarrage complet : [`INSTALLATION.md`](INSTALLATION.md).

---

## 2. Carte du dashboard (13 pages)

| Page | Route | À quoi elle sert |
|---|---|---|
| Dashboard général | `/` | vue d'ensemble : volumes, scores, décisions, activité récente |
| IOC Inventory | `/inventory` | liste filtrable de tous les indicateurs |
| Threat Intel Sources | `/sources` | contribution et fiabilité de chaque source |
| IOC Scoring | `/scoring` | classement par score + détail explicatif |
| IOC Lifecycle | `/lifecycle` | transitions d'état et historique |
| Published Indicators | `/published` | indicateurs publiés et leur cible |
| Detection Monitoring | `/monitoring` | alertes Suricata / Wazuh rapprochées |
| Expired Indicators | `/expired` | indicateurs expirés et retirés |
| Automation Workflows | `/workflows` | activité des 8 workflows n8n |
| Audit Logs | `/audit` | journal append-only de toutes les actions |
| Reports | `/reports` | rapport quotidien généré depuis la base |
| System Health | `/system-health` | santé API / base / collecteurs |
| Fiche IOC | `/iocs/:id` | tout sur un indicateur : score, sources, cycle, détections |

---

## 3. Lire le dashboard général

Les cartes du haut répondent à « combien ? » :

- **IOC au total** : taille de l'inventaire (174 au 14/11/2026) ;
- **actifs** : indicateurs non expirés et non rejetés ;
- **publiés** : score ≥ 80 **et** détections observées ;
- **score moyen** : moyenne des scores calculés ;
- **taux de déduplication** : doublons écartés / éléments normalisés.

Les graphiques répondent à « où ? » :

- répartition par **type** (domaine, IP, hachage, URL) ;
- répartition par **statut** (entonnoir du cycle de vie) ;
- distribution des **scores** par tranche ;
- activité des **14 derniers jours**.

> Tous les chiffres viennent de `GET /api/v1/iocs/stats/dashboard`.
> Aucune valeur n'est calculée côté navigateur.

---

## 4. Scénarios d'utilisation

### 4.1 Vérifier qu'un indicateur est digne de confiance

1. **Inventory** → rechercher la valeur.
2. Ouvrir la **fiche IOC**.
3. Lire, dans l'ordre :
   - **sources** : combien d'**organisations distinctes** (pas de flux) ;
   - **enrichissement** : verdicts OTX / AbuseIPDB, avec date de récupération ;
   - **score** : détail composante par composante ;
   - **détections** : un capteur l'a-t-il réellement observé ?
4. Décider : publier, surveiller, ou ignorer.

### 4.2 Comprendre un score

Exemple de décomposition réelle (IOC publié, score 82) :

| Composante | Points | Maximum | Explication |
|---|---:|---:|---|
| Fiabilité de la source | 18,75 | 25 | source notée 75/100 |
| Fraîcheur | 20,0 | 20 | vu il y a < 1 jour (demi-vie 7 j) |
| Sources indépendantes | 8,6 | 20 | 1 organisation distincte |
| Consensus d'enrichissement | 20,0 | 20 | OTX : `malicious` |
| Détections observées | 15,0 | 15 | 11 alertes (saturation à 5) |
| **Total** | **82** | **100** | décision : **publier** |

Sans détection, le maximum atteignable est ≈ **67** : la publication exige
donc une **observation réelle**, pas seulement un empilement de sources.

### 4.3 Suivre une publication

1. **Published Indicators** : la liste des IOC publiés.
2. Vérifier la colonne **cible** (`detection_list`, `misp`) et l'état
   (`verified` / `revoked`).
3. **Detection Monitoring** : les alertes qui confirment l'utilité de l'IOC.

### 4.4 Contrôler le retrait d'un indicateur

1. **Expired Indicators** : IOC dont `expires_at` est dépassé.
2. Un IOC ne passe `REMOVED` qu'après **révocation vérifiée** de toutes ses
   publications.
3. **Audit Logs** → filtrer `REMOVE` : la preuve (`revoked`, `verified`) est
   dans le détail de l'événement.

### 4.5 Auditer une action

1. **Audit Logs**.
2. Filtrer par action (`COLLECT`, `SCORE`, `PUBLISH`, `REMOVE`, `EXPIRE`…).
3. Chaque ligne contient : acteur, action, entité, détail JSON, succès/échec.
4. Le journal est **append-only** : aucune ligne ne peut être modifiée ni
   supprimée, même par un administrateur de la base (trigger PostgreSQL).

---

## 5. Utiliser l'API

Base : `http://127.0.0.1:8000/api/v1`

### 5.1 Consulter

```powershell
# Statistiques agrégées
Invoke-RestMethod http://127.0.0.1:8000/api/v1/iocs/stats/dashboard

# Liste paginée et filtrée
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/iocs?status=MONITORED&limit=50"

# Détail d'un IOC
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/iocs/<uuid>"

# Sources et Contribution
Invoke-RestMethod http://127.0.0.1:8000/api/v1/iocs/stats/sources

# Journal d'audit
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/audit?limit=100"
```

### 5.2 Injecter un indicateur (manuel)

```powershell
$body = @{
  items = @(
    @{ value = "203.0.113.77"; type = "IP"; source = "manual_test"; tags = @("lab") }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/iocs/ingest `
  -ContentType "application/json" -Body $body
```

Réponse : `{created, updated, duplicates, rejected, results[]}`.
Une valeur invalide revient en `rejected` avec la raison — jamais stockée.

### 5.3 Dérouler le pipeline

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/iocs/collect/run?limit=50"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/iocs/normalize/run?limit=200"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/iocs/enrich/run?limit=50"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/iocs/scoring/run" `
  -ContentType "application/json" -Body "{}"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/iocs/publish/run"
```

### 5.4 Enregistrer une détection

```powershell
Invoke-RestMethod -Method Post `
  "http://127.0.0.1:8000/api/v1/iocs/<uuid>/detections?sensor=manual&rule_id=LAB-1"
```

### 5.5 Expirer puis retirer

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/iocs/expire/run
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/iocs/remove/run
```

Le second appel refuse de marquer `REMOVED` si une publication reste active.

### 5.6 Ajuster une échéance ou des tags

```powershell
Invoke-RestMethod -Method Patch `
  "http://127.0.0.1:8000/api/v1/iocs/<uuid>?expires_at=2026-12-31T00:00:00Z&add_tags=reviewed"
```

Refusé (409) si l'IOC est dans un état terminal (`REMOVED`, `REJECTED`, `DUPLICATE`).

### 5.7 Générer le rapport du jour

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/reports/daily
Invoke-RestMethod http://127.0.0.1:8000/api/v1/reports/daily
```

---

## 6. Glossaire des statuts

| Statut | Signification | Sortie possible |
|---|---|---|
| `NEW` | ingéré, pas encore validé | `NORMALIZED`, `DUPLICATE`, `REJECTED` |
| `NORMALIZED` | validé et canonique | `ENRICHED`, `REVIEW_REQUIRED`, `REJECTED` |
| `ENRICHED` | au moins un verdict externe | `SCORED` |
| `SCORED` | score calculé | `PUBLISHED`, `MONITORED`, `REJECTED`, `REVIEW_REQUIRED` |
| `MONITORED` | 50 ≤ score < 80 | `PUBLISHED`, `REVIEW_REQUIRED`, `EXPIRED` |
| `PUBLISHED` | score ≥ 80 et détections | `MONITORED`, `REVIEW_REQUIRED`, `EXPIRED` |
| `REVIEW_REQUIRED` | cas ambigu, décision humaine | `PUBLISHED`, `MONITORED`, `REJECTED` |
| `REJECTED` | score < 50 (terminal) | — |
| `DUPLICATE` | doublon d'un IOC existant (terminal) | — |
| `EXPIRED` | échéance dépassée | `REMOVED` |
| `REMOVED` | retiré, publications révoquées (terminal) | — |

Un `REJECTED` ou un `REMOVED` ne peut **jamais** redevenir actif : la machine à
états le refuse.

---

## 7. Questions fréquentes

**Pourquoi seulement 1 IOC publié sur 174 ?**
Le seuil de publication est 80 et la composante « détections observées »
(15 points) exige des alertes réelles. Sans détection, le plafond est ≈ 67.
C'est un choix : publier peu, mais publier juste.

**Pourquoi 83 rejets ?**
Score < 50 : sources peu fiables, indicateurs anciens, enrichissement
`unknown`/`benign`. Le rejet est une décision tracée, pas une suppression.

**Un IOC reste `NORMALIZED`, est-ce un bug ?**
Non : l'enrichissement n'a pas encore tourné, ou tous les fournisseurs ont
échoué (réseau, quota). Le prochain passage le reprend.

**Le score a changé, pourquoi ?**
La fraîcheur décroît avec le temps, les détections s'ajoutent, les faux
positifs pénalisent. Chaque recalcul laisse une ligne dans `score_history`
avec la politique utilisée.

**Où sont les faux positifs ?**
`detections.is_false_positive`. Tant qu'une détection n'est pas revue, elle
reste `NULL` : elle n'est ni comptée comme vraie, ni comme fausse.

**Comment régénérer le rapport Word ?**

```powershell
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py
.\backend\.venv\Scripts\python.exe scripts\generate_report.py
```

**Que faire si l'API répond « healthy » mais ne répond plus depuis Windows ?**
Proxy Docker Desktop périmé : `docker restart soar-postgres soar-api soar-n8n`.

---

## 8. Bonnes pratiques d'analyse

1. Ne jamais publier sur la base d'**une seule** source non recoupée.
2. Vérifier la **date de dernière observation** : un IOC de 2023 est rarement
   encore actif.
3. Un verdict `unknown` n'est **pas** un verdict bénin : c'est une absence
   d'information.
4. Croiser avec une détection : c'est la preuve la plus forte disponible ici.
5. Documenter tout override manuel via les tags (`reviewed`, `whitelisted`…)
   et l'échéance — l'action est auditée automatiquement.
