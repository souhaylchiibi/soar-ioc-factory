# Tests — stratégie, exécution, couverture réelle

> **177 tests, 177 au vert** (≈ 42 s), exécutés contre un **vrai PostgreSQL**
> migré par Alembic. Aucun mock de base de données.

---

## 1. Principe

Les tests ne vérifient pas des appels de fonctions : ils vérifient des
**propriétés du système réel**.

| Choix | Raison |
|---|---|
| PostgreSQL réel (`soar_ioc_test`) | les contraintes, enums, index, triggers et types JSON sont ceux de la production |
| Migrations Alembic réelles | le schéma testé est exactement celui déployé |
| `TRUNCATE` entre les tests | isolation sans recréer la base |
| Mocks limités aux **services externes** | OTX, AbuseIPDB, MISP, Wazuh, Suricata ne sont pas appelés sur le réseau |
| Horloges explicites (`now=…`) | les tests de fraîcheur et d'expiration sont déterministes |

---

## 2. Exécuter la suite

```powershell
cd backend
$env:PYTHONPATH="$PWD"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value

.\.venv\Scripts\python.exe -m pytest tests -q
```

Résultat attendu :

```
177 passed in ~42s
```

Options utiles :

```powershell
# un module
.\.venv\Scripts\python.exe -m pytest tests/test_security.py -v

# un test précis
.\.venv\Scripts\python.exe -m pytest tests/test_scoring.py::TestThresholds -v

# arrêt au premier échec
.\.venv\Scripts\python.exe -m pytest tests -x -q
```

> Le mot de passe PostgreSQL contient parfois `%` : `database/migrations/env.py`
> gère déjà l'échappement, aucune variable supplémentaire n'est nécessaire.

---

## 3. Répartition des 177 tests

| Module | Tests | Ce qui est prouvé |
|---|---:|---|
| `test_normalization.py` | 35 | types, formes canoniques, rejets, empreintes, inférence |
| `test_security.py` | 27 | audit immuable, entrées hostiles, états, anti-collusion, secrets, ports |
| `test_lifecycle.py` | 23 | transitions légales/illégales, audit, niveaux de risque, expiration |
| `test_ingest.py` | 21 | création, dédup, mise à jour, provenance, rejet, synthétique |
| `test_scoring.py` | 19 | composantes, fraîcheur, seuils, pénalités, explication, anti-collusion |
| `test_misp.py` | 18 | client REST, publication, révocation, relecture, erreurs |
| `test_providers.py` | 16 | collecteurs (parsing, limites, pannes), enrichissement, cache |
| `test_pipeline.py` | 11 | pipeline complet, reprise, décisions, expiration/retrait |
| `test_health.py` | 7 | `/health`, `/ready`, `/system/health`, dégradations |
| **Total** | **177** | |

---

## 4. Ce que couvre chaque famille

### 4.1 Normalisation (35)

- IP v4/v6, forme compressée, `IP:port`, rejet de `0.0.0.0`, multicast,
  loopback, link-local ;
- domaines : casse, point final, port, rejet des URL déguisées, labels
  invalides, longueur > 253 ;
- URL : schémas autorisés, port par défaut retiré, fragment supprimé,
  hôte invalide rejeté ;
- hachages : longueur exacte, hexadécimal, cohérence avec le type déclaré ;
- **aucune réparation silencieuse** : une valeur invalide lève toujours.

### 4.2 Sécurité (27)

| Test | Propriété |
|---|---|
| `test_audit_rows_cannot_be_updated` | UPDATE refusé par le trigger |
| `test_audit_rows_cannot_be_deleted` | DELETE refusé par le trigger |
| `test_trigger_is_present_in_schema` | le trigger existe réellement |
| `test_normalization_rejects_hostile_values` (12 valeurs) | injection, XSS, traversée de chemin, plages non routables |
| `test_injection_attempt_does_not_touch_the_table` | `'; DROP TABLE iocs; --` → rejet, table intacte |
| `test_oversized_value_is_rejected_not_truncated` | pas de troncature silencieuse |
| `test_shortcut` / `test_terminal` | saut d'état et résurrection impossibles |
| `test_same_organisation_does_not_multiply_independent_sources` | anti-collusion |
| `test_no_secret_file_is_tracked` | `git ls-files` sans `.env` / `.pem` |
| `test_gitignore_covers_secrets` | motifs présents |
| `test_no_hardcoded_credential_pattern_in_source` | pas de clé AWS / clé privée / jeton |
| `test_published_ports_are_loopback_only` (×2) | compose principal et AWS |

### 4.3 Cycle de vie (23)

- parcours complet `NEW → … → REMOVED` ;
- refus de chaque transition illégale ;
- enregistrement systématique d'un `LifecycleEvent` ;
- expiration par date, y compris fuseaux horaires ;
- calcul du niveau de risque.

### 4.4 Ingestion (21)

- création + normalisation automatique ;
- déduplication par empreinte (deux feeds → un seul IOC) ;
- mise à jour de `last_seen_at` sans doublon ;
- provenance (`ioc_sources`) et comptage des groupes indépendants ;
- rejet d'une valeur invalide avec audit ;
- marquage `is_synthetic` propagé aux enrichissements.

### 4.5 Notation (19)

- poids et bornes de chaque composante ;
- décroissance exponentielle de la fraîcheur (demi-vie par type) ;
- saturation des sources indépendantes ;
- consensus d'enrichissement (malicious/suspicious/unknown/benign) ;
- pénalité faux positifs plafonnée ;
- seuils 80 / 50 configurables ;
- **explication** complète et persistée.

### 4.6 MISP (18)

Client REST testé avec un transport simulé (aucun appel réseau) :

- création d'événement + attribut ;
- relecture de l'attribut avant de marquer la publication vérifiée ;
- révocation confirmée ;
- erreurs HTTP, timeouts, réponses incohérentes → échec explicite, jamais
  de faux succès.

### 4.7 Pipeline (11)

- `ingest → enrich → score → decide` de bout en bout ;
- reprise après échec d'enrichissement ;
- décision `publish` / `monitor` / `reject` ;
- redescente `PUBLISHED → REJECTED` via `REVIEW_REQUIRED` ;
- expiration puis retrait vérifié.

---

## 5. Ce qui n'est **pas** testé automatiquement

| Élément | Pourquoi | Comment c'est couvert |
|---|---|---|
| Interface React | pas de tests unitaires frontend | `tsc -b` + `vite build` sans erreur, 13 routes vérifiées manuellement, 0 erreur console (captures) |
| Appels réels OTX / AbuseIPDB / MISP | dépendances réseau et quotas | tests avec transport simulé ; exécution réelle tracée dans le rapport |
| Charge / performance | hors périmètre académique | mesure ponctuelle : 27 159 scores/s (moteur), 1,48 IOC/s (lot complet) |
| Reprise après coupure brutale | difficile à scripter proprement | testé manuellement (crash Docker Desktop du 07/11, données intactes) |
| Sécurité offensive (pentest) | hors périmètre | modèle de menace + checklist dans `SECURITY.md` |

Ces absences sont **assumées et documentées**, pas dissimulées.

---

## 6. Reproductibilité

| Élément | Valeur |
|---|---|
| Base de test | `soar_ioc_test` (créée automatiquement si absente) |
| Migration appliquée | `dadb423768cb` (head) |
| Isolation | `TRUNCATE` de 12 tables avant chaque test |
| Durée | ≈ 42 s sur un ThinkPad T480s |
| Dépendances | `backend/requirements-dev.txt` |
| Déterminisme | aucune dépendance à l'heure murale dans les assertions sensibles |

`conftest.py` crée la base et applique Alembic **une fois par session** ; si
PostgreSQL est injoignable, les tests sont **skippés explicitement** (jamais
faussement verts).

---

## 7. Convention d'écriture d'un nouveau test

1. Une propriété par test, nom explicite en anglais.
2. Pas de mock de la base : utiliser la fixture `db`.
3. Pour un service externe : injecter un faux transport, jamais `requests` réel.
4. Vérifier l'**effet en base** (et pas seulement la valeur de retour).
5. Si le test dépend de l'heure, passer `now=` explicitement.

Exemple minimal :

```python
def test_new_ioc_is_normalized_on_ingest(db, registered_source):
    outcome = ingest_raw(db, raw("203.0.113.9", declared="IP"))
    db.commit()
    ioc = db.get(Ioc, outcome.ioc_id)
    assert outcome.action == "created"
    assert ioc.status == IocStatus.NORMALIZED
```

---

## 8. Intégration continue

Il n'y a **pas** de pipeline CI dans ce dépôt (contrainte du laboratoire).

Pour l'ajouter, un job suffit :

```yaml
- run: docker compose up -d db
- run: cd backend && pip install -r requirements-dev.txt
- run: pytest tests -q
  env:
    POSTGRES_HOST: 127.0.0.1
    POSTGRES_USER: soar
    POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
```
