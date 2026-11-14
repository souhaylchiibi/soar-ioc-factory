# Phase 7 - Evaluation de l'usine a indicateurs

> Genere automatiquement le 2026-11-14T01:13:39.865374+00:00 depuis la base `soar_ioc` - **aucune valeur n'est inventee**.

Ce document distingue systematiquement :

- les **mesures** : lues dans PostgreSQL (inventaire, scores, detections, audit) ;
- les **hypotheses** : le modele manuel de comparaison, explicitement pose et modifiable dans `scripts/evaluate_platform.py` ;
- ce qui **n'a pas pu etre mesure**, avec la raison.

## 1. Inventaire traite

| Indicateur | Valeur |
|---|---|
| Indicateurs en base | 217 |
| Types | DOMAIN=99, IP=58, HASH_SHA256=28, URL=19, HASH_MD5=8, HASH_SHA1=5 |
| Niveaux de risque | CRITICAL=2, HIGH=3, MEDIUM=129, LOW=83 |
| Synthetiques (marques `is_synthetic`) | 0 |
| Avec empreinte de doublon | 0 |
| Avec date d'expiration | 1 |

## 2. Qualite de la donnee et deduplication

| Mesure | Valeur |
|---|---|
| Elements bruts collectes | 285 |
| Indicateurs crees | 217 |
| Indicateurs mis a jour | 67 |
| Doublons ecartes a l'ingestion | 0 |
| Valeurs invalides rejetees | 1 |
| **Taux de deduplication** (DEDUP / NORMALIZE+DEDUP) | **23.4 %** |
| Part de l'inventaire issu d'un doublon | 0.0 % |

> Le taux de deduplication est calcule sur les evenements d'audit (`DEDUP` / (`NORMALIZE` + `DEDUP`)), pas sur une estimation.

## 3. Enrichissement

| Mesure | Valeur |
|---|---|
| Resultats d'enrichissement stockes | 194 |
| Indicateurs enrichis | 182 |
| Couverture | 83.9 % |
| Taux de succes fournisseurs | 92.8 % |
| Erreurs fournisseurs | 14 |
| Resultats moyens par indicateur enrichi | 1.07 |
| Repartition par fournisseur | otx=183, abuseipdb=11 |
| Repartition par verdict | abuseipdb/benign=2, abuseipdb/malicious=1, abuseipdb/suspicious=3, abuseipdb/unknown=5, otx/malicious=28, otx/suspicious=14, otx/unknown=141 |

## 4. Notation et decisions

| Mesure | Valeur |
|---|---|
| Indicateurs notes | 217 (100.0 %) |
| Score moyen | 52.4 |
| Score median | 54.0 |
| 95e percentile | 64.0 |
| Minimum / maximum | 37.0 / 82.0 |
| Notation explicable (score_breakdown) | 217 (100.0 %) |
| Politique active | v1 |

| Decision | Indicateurs | Part des indicateurs notes |
|---|---|---|
| publish | 1 | 0.5 % |
| monitor | 132 | 60.8 % |
| reject | 83 | 38.2 % |

### Contribution moyenne des composantes du score

| Composante | Points moyens | Maximum | % du maximum |
|---|---|---|---|
| Consensus d'enrichissement | 10.18 | 20.0 | 50.9 |
| Fraîcheur | 16.0 | 20.0 | 80.0 |
| Sources indépendantes | 8.61 | 20.0 | 43.0 |
| Détections observées | 0.14 | 15.0 | 0.9 |
| Fiabilité de la source | 17.49 | 25.0 | 70.0 |

> Un score sans detection reste plafonne autour de 67/100 : c'est la composante `observed_detections` (15 points) qui permet d'atteindre le seuil de publication (>= 80). Les indicateurs publies le sont donc **parce qu'un capteur les a reellement observes**, pas par empilement de sources.

## 5. Publication et verification

| Mesure | Valeur |
|---|---|
| Publications enregistrees | 2 |
| Verifiees par relecture | 1 |
| Retirees (revocation confirmee) | 1 |
| Actives | 1 |
| Indicateurs au statut PUBLISHED | 1 |

## 6. Detections

| Mesure | Valeur |
|---|---|
| Detections enregistrees | 16 |
| Indicateurs ayant declenche | 2 |
| Couverture de l'inventaire | 0.9 % |
| Faux positifs | 0 |
| Taux de faux positifs | 0.0 % |
| Par capteur | manual=10, wazuh=4, suricata=2 |

## 7. Cycle de vie et delais

| Etape (transition) | Observee | Duree moyenne (a chaud) | Duree max |
|---|---|---|---|
| NORMALIZED | 217 | 0.0 s | 0.0 s |
| ENRICHED | 217 | 96.47 s | 597904.44 s |
| SCORED | 217 | 38.61 s | 597737.8 s |
| MONITORED | 134 | 39.76 s | 597737.8 s |
| REJECTED | 83 | 31.98 s | 597737.8 s |
| PUBLISHED | 2 | 2492.87 s | 3016.63 s |
| EXPIRED | 1 | 37.66 s | 37.66 s |
| REMOVED | 1 | 0.21 s | 0.21 s |

- Cycle complet mesure (NEW -> REMOVED) : **2050.8 s** (34.2 min), 7 transitions tracees, indicateur `162.243.103.246`.
- Transitions journalisees au total : **872**.

> Les durees Â« a chaud Â» excluent le backlog repris apres un arret volontaire de la plateforme ; les durees completes restent visibles dans `metrics.json`.

## 8. Performance mesuree

| Mesure | Valeur |
|---|---|
| Traitement a chaud (ingestion -> score) | 81.8 s en moyenne sur 108 indicateurs |
| Debit du lot a chaud | 1.32 indicateurs/s |
| Backlog repris apres arret | 109 indicateurs, 163.6 h en moyenne |
| Moteur de notation (CPU pur) | 45.9 us/score = 21809.0 scores/s |

> Les indicateurs 'backlog' ont ete notations apres un arret volontaire de la plateforme (07/11 -> 14/11) : ce delai mesure l'indisponibilite, pas la performance.

## 9. Automatisation : avant / apres

**Apres (mesure)** : la plateforme a traite l'inventaire ci-dessus avec les latences reelles du tableau precedent.

**Avant (hypothese documentee)** : modele d'un analyste sans automatisation, temps unitaires par indicateur :

| Etape manuelle | Minutes / indicateur |
|---|---|
| collecte et verification source | 1.0 |
| normalisation et validation | 2.0 |
| recherche de doublons | 2.0 |
| enrichissement 2 sources | 4.0 |
| notation et decision | 3.0 |
| publication et verification | 4.0 |
| journalisation et tracabilite | 1.0 |

| Comparaison | Valeur |
|---|---|
| Total manuel par indicateur (hypothese) | 17.0 min |
| Total automatise par indicateur (mesure) | 1.36 min |
| Facteur de reduction | x12.5 |
| Charge manuelle pour cet inventaire (hypothese) | 61.5 h |
| Charge automatisee pour cet inventaire | 4.92 h |
| Temps economise (hypothese) | 56.6 h |

> Temps unitaires par indicateur pour un analyste SOC sans automatisation. Modele explicite servant de point de comparaison : ce n'est PAS une mesure du passe. Les chiffres automatises, eux, viennent tous de la base.

## 10. TraÃ§abilite

| Action d'audit | Evenements |
|---|---|
| SCORE | 219 |
| NORMALIZE | 219 |
| DEDUP | 67 |
| OBSERVE | 14 |
| COLLECT | 13 |
| ENRICH | 7 |
| PUBLISH | 4 |
| EXPORT | 2 |
| CONFIG_CHANGE | 1 |
| REMOVE | 1 |
| EXPIRE | 1 |

- Total : **548** evenements, dont **2** en echec (les echecs sont conserves, jamais masques).
- Le journal est **append-only** : un trigger PostgreSQL refuse tout UPDATE et DELETE (verifie par test automatise).

## 11. Sources

| Source | Type | Fiabilite | Active | Indicateurs |
|---|---|---|---|---|
| urlscan | OPEN_SOURCE | 70 | oui | 79 |
| blocklist_de | COMMUNITY | 60 | oui | 50 |
| alienvault_otx | OPEN_SOURCE | 80 | oui | 40 |
| malwarebazaar | COMMUNITY | 70 | oui | 16 |
| urlhaus | COMMUNITY | 70 | oui | 15 |
| threatfox | COMMUNITY | 75 | oui | 13 |
| feodotracker | COMMUNITY | 75 | oui | 5 |
| synthetic_lab | SYNTHETIC | 50 | oui | 0 |

## 12. Figures

![eval_01_cycle_de_vie.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_01_cycle_de_vie.png)

![eval_02_scores.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_02_scores.png)

![eval_03_entonnoir.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_03_entonnoir.png)

![eval_04_enrichissement.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_04_enrichissement.png)

![eval_05_collecte_dedup.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_05_collecte_dedup.png)

![eval_06_automatisation.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_06_automatisation.png)

![eval_07_sources.png](C:/Users/T480s/Desktop/SOAR project/reports/figures/eval_07_sources.png)

## 13. Limites assumees

- Les **faux positifs** ne sont renseignes que pour les detections revues ; les detections non revues restent `NULL` et ne sont pas comptees comme benignes.
- Le **modele manuel** est une hypothese de comparaison, pas une mesure historique.
- Les collecteurs URLhaus / ThreatFox / MalwareBazaar sont **inactifs** : la cle abuse.ch fournie a ete refusee par le serveur (`unknown_auth_key`). Aucune donnee n'a ete simulee pour compenser.
- Le **backlog** (indicateurs traites apres l'arret de la plateforme) gonfle la latence moyenne globale ; il est isole dans les metriques.
- La **precision/rappel** au sens strict exigerait un jeu de verite terrain annote ; les indicateurs etant issus de flux publics, aucune verite terrain n'est revendiquee. Les proxies reportes (taux de publication, taux de faux positifs observes, couverture d'enrichissement) sont ceux qui sont reellement mesurables ici.

