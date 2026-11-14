# Écarts détectés lors de la génération du rapport final

> Relevé le 14/11/2026, lors de la génération de `reports/RAPPORT_FINAL_14-11-2026.docx`.
> Référence chiffrée : `reports/evaluation/metrics.json` (généré le 14/11/2026 à 01:13 UTC)
> et l'API locale (`/iocs/stats/dashboard`, `/system/health`).

## 1. Anomalie applicative

| # | Où | Constat | Preuve | Effet sur le rapport |
|---|---|---|---|---|
| 1 | `backend/app/api/iocs.py` — `source_stats()` (`GET /api/v1/iocs/stats/sources`) | `select(func.count(Ioc.id)).select_from(IocSource)` sans jointure vers `iocs` : produit cartésien, chaque compteur est multiplié par le nombre total d'IOC (217). | feodotracker 1085 = 5 × 217 ; urlscan 17143 = 79 × 217 ; total affiché 47 306 « IOC liés » pour 217 IOC. | **Corrigé le 14/11/2026** : `count(distinct IocSource.ioc_id)` filtré par source ; test `TestSourceStats` ajouté dans `test_ingest.py` (192 tests au vert) ; conteneur `soar-api` reconstruit ; l'API renvoie désormais 218 liens pour 217 IOC. Capture `capture/2026-11-14/13b-sources.jpg` intégrée au rapport. |

## 2. Documents en retard sur les chiffres actuels

L'inventaire est passé de 174 à **217 IOC** et la suite de tests de 177 à **192 tests**
(191 après l'activation des collecteurs abuse.ch, +1 test de non-régression ci-dessus).
`README.md` et `docs/TESTING.md` ont été mis à jour ; les fichiers ci-dessous ne l'ont pas été.

| Fichier | Ligne | Valeur périmée | Valeur actuelle |
|---|---|---|---|
| `docs/USER_GUIDE.md` | 45 | 174 IOC | 217 |
| `docs/USER_GUIDE.md` | 224 | « 1 IOC publié sur 174 » | 1 sur 217 |
| `OUVRIR_LE_PROJET.md` | 32 | 174 IOC locaux | 217 |
| `OUVRIR_LE_PROJET.md` | 47 | 177 passed (~42 s) | 192 tests |
| `OUVRIR_LE_PROJET.md` | 80 | 177 tests | 192 |
| `BRIEF_CLAUDE_RAPPORT.md` | §3, §9, §10 | 174 IOC, 177 tests, clé abuse.ch refusée | 217 IOC, 192 tests, clé abuse.ch valide |

## 3. Points d'attention (non bloquants)

- La fiche de l'IOC publié affiche **11 détections** au total, alors que la composante
  « Détections observées » du score en compte **6** : le score ne compte qu'une partie des
  détections (fenêtre ou filtre). C'est cohérent avec le moteur, mais à expliquer si le jury pose la question.
- Les captures `capture/07…10-*.jpg` du 07/11 montrent l'ancien inventaire ; le rapport
  utilise désormais les captures `capture/2026-11-14/*.jpg`. Les anciennes captures sont conservées.
