# Phase 7 - Evaluation de l'usine a indicateurs

> Genere automatiquement le 2026-11-17T01:00:51.072232+00:00 depuis la base `soar_ioc` - **aucune valeur n'est inventee**.

Ce document distingue systematiquement :

- les **mesures** : lues dans PostgreSQL (inventaire, scores, detections, audit) ;
- les **hypotheses** : le modele manuel de comparaison, explicitement pose et modifiable dans `scripts/evaluate_platform.py` ;
- ce qui **n'a pas pu etre mesure**, avec la raison.

## 1. Inventaire traite

| Indicateur | Valeur |
|---|---|
| Indicateurs en base | 454 |
| Types | DOMAIN=194, IP=98, URL=70, HASH_SHA256=50, HASH_MD5=22, HASH_SHA1=20 |
| Niveaux de risque | CRITICAL=2, HIGH=7, MEDIUM=361, LOW=84 |
| Synthetiques (marques `is_synthetic`) | 0 |
| Avec empreinte de doublon | 0 |
| Avec date d'expiration | 1 |

## 2. Qualite de la donnee et deduplication

| Mesure | Valeur |
|---|---|
| Elements bruts collectes | 545 |
| Indicateurs crees | 691 |
| Indicateurs mis a jour | 111 |
| Doublons ecartes a l'ingestion | 2 |
| Valeurs invalides rejetees | 1 |
| **Taux de deduplication** (DEDUP / NORMALIZE+DEDUP) | **16.3 %** |
| Part de l'inventaire issu d'un doublon | 0.0 % |

> Le taux de deduplication est calcule sur les evenements d'audit (`DEDUP` / (`NORMALIZE` + `DEDUP`)), pas sur une estimation.

## 3. Enrichissement

| Mesure | Valeur |
|---|---|
| Resultats d'enrichissement stockes | 471 |
| Indicateurs enrichis | 419 |
| Couverture | 92.3 % |
| Taux de succes fournisseurs | 95.5 % |
| Erreurs fournisseurs | 21 |
| Resultats moyens par indicateur enrichi | 1.12 |
| Repartition par fournisseur | otx=420, abuseipdb=51 |
| Repartition par verdict | abuseipdb/benign=3, abuseipdb/malicious=28, abuseipdb/suspicious=10, abuseipdb/unknown=10, otx/malicious=45, otx/suspicious=33, otx/unknown=342 |

## 4. Notation et decisions

| Mesure | Valeur |
|---|---|
| Indicateurs notes | 454 (100.0 %) |
| Score moyen | 54.0 |
| Score median | 54.0 |
| 95e percentile | 64.0 |
| Minimum / maximum | 37.0 / 82.0 |
| Notation explicable (score_breakdown) | 454 (100.0 %) |
| Politique active | v1 |

| Decision | Indicateurs | Part des indicateurs notes |
|---|---|---|
| publish | 1 | 0.2 % |
| monitor | 368 | 81.1 % |
| reject | 84 | 18.5 % |

### Contribution moyenne des composantes du score

| Composante | Points moyens | Maximum | % du maximum |
|---|---|---|---|
| Consensus d'enrichissement | 9.82 | 20.0 | 49.1 |
| Fraîcheur | 17.9 | 20.0 | 89.5 |
| Sources indépendantes | 8.61 | 20.0 | 43.1 |
| Détections observées | 0.07 | 15.0 | 0.4 |
| Fiabilité de la source | 17.69 | 25.0 | 70.7 |

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
| Couverture de l'inventaire | 0.4 % |
| Faux positifs | 0 |
| Taux de faux positifs | 0.0 % |
| Par capteur | manual=10, wazuh=4, suricata=2 |

## 7. Cycle de vie et delais

| Etape (transition) | Observee | Duree moyenne (a chaud) | Duree max |
|---|---|---|---|
| NORMALIZED | 454 | 0.0 s | 0.0 s |
| ENRICHED | 454 | 1643.12 s | 597904.44 s |
| SCORED | 454 | 103.39 s | 597737.8 s |
| MONITORED | 370 | 107.65 s | 597737.8 s |
| REJECTED | 84 | 37.8 s | 597737.8 s |
| PUBLISHED | 2 | 2492.87 s | 3016.63 s |
| EXPIRED | 1 | 37.66 s | 37.66 s |
| REMOVED | 1 | 0.21 s | 0.21 s |

- Cycle complet mesure (NEW -> REMOVED) : **2050.8 s** (34.2 min), 7 transitions tracees, indicateur `162.243.103.246`.
- Transitions journalisees au total : **1820**.

> Les durees Â« a chaud Â» excluent le backlog repris apres un arret volontaire de la plateforme ; les durees completes restent visibles dans `metrics.json`.

## 8. Performance mesuree

| Mesure | Valeur |
|---|---|
| Traitement a chaud (ingestion -> score) | 1936.1 s en moyenne sur 345 indicateurs |
| Debit du lot a chaud | 0.18 indicateurs/s |
| Backlog repris apres arret | 109 indicateurs, 163.6 h en moyenne |
| Moteur de notation (CPU pur) | 36.5 us/score = 27365.0 scores/s |

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
| Total automatise par indicateur (mesure) | 32.27 min |
| Facteur de reduction | x0.5 |
| Charge manuelle pour cet inventaire (hypothese) | 128.6 h |
| Charge automatisee pour cet inventaire | 244.18 h |
| Temps economise (hypothese) | -115.5 h |

> Temps unitaires par indicateur pour un analyste SOC sans automatisation. Modele explicite servant de point de comparaison : ce n'est PAS une mesure du passe. Les chiffres automatises, eux, viennent tous de la base.

## 10. TraÃ§abilite

| Action d'audit | Evenements |
|---|---|
| SCORE | 457 |
| NORMALIZE | 456 |
| DEDUP | 89 |
| LOGIN | 44 |
| COLLECT | 21 |
| OBSERVE | 14 |
| ENRICH | 13 |
| PUBLISH | 5 |
| EXPORT | 4 |
| USER_CREATE | 1 |
| REMOVE | 1 |
| CONFIG_CHANGE | 1 |
| EXPIRE | 1 |

- Total : **1107** evenements, dont **9** en echec (les echecs sont conserves, jamais masques).
- Le journal est **append-only** : un trigger PostgreSQL refuse tout UPDATE et DELETE (verifie par test automatise).

## 11. Sources

| Source | Type | Fiabilite | Active | Indicateurs |
|---|---|---|---|---|
| urlscan | OPEN_SOURCE | 70 | oui | 123 |
| alienvault_otx | OPEN_SOURCE | 80 | oui | 90 |
| blocklist_de | COMMUNITY | 60 | oui | 89 |
| urlhaus | COMMUNITY | 70 | oui | 65 |
| threatfox | COMMUNITY | 75 | oui | 63 |
| malwarebazaar | COMMUNITY | 70 | oui | 21 |
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

