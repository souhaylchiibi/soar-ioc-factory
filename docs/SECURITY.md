# Sécurité — contrôles, preuves et limites

> Ce document décrit ce qui est **réellement implémenté et testé**, ce qui ne
> l'est pas, et les risques résiduels assumés. Il ne revendique aucune
> certification.

---

## 1. Principes directeurs

1. **Rien n'est exposé publiquement** : tous les services applicatifs écoutent
   sur `127.0.0.1` ; l'accès distant passe par un tunnel SSH.
2. **Aucun secret dans le dépôt** : `.env`, `*.pem`, identifiants AWS sont
   ignorés et un test le vérifie à chaque exécution.
3. **Aucune donnée inventée** : un échec de fournisseur est conservé comme
   échec ; une publication n'est « vérifiée » qu'après relecture.
4. **Le journal d'audit est immuable** : UPDATE et DELETE sont refusés par
   trigger PostgreSQL.
5. **Aucune action destructive automatique** : l'expiration et le retrait sont
   des transitions d'état vérifiées, jamais des suppressions de lignes.

---

## 2. Actifs protégés

| Actif | Pourquoi | Où |
|---|---|---|
| Inventaire IOC + historique de scores | valeur analytique, preuve du travail | PostgreSQL (`pgdata`) |
| Journal d'audit | traçabilité, non-répudiation | table `audit_logs` (append-only) |
| Clés API (OTX, AbuseIPDB, abuse.ch) | quota et réputation | `.env` (hors git) |
| Clé SSH EC2 + identifiants AWS temporaires | accès infrastructure | hors dépôt (`%TEMP%\opencode\`) |
| Workflows n8n | automatisation | volume `n8n_data` |

---

## 3. Modèle de menace

| Menace | Vecteur | Impact | Contrôle | Résiduel |
|---|---|---|---|---|
| Injection SQL via un IOC | flux externe malveillant | fuite / destruction | validation stricte + requêtes paramétrées SQLAlchemy | faible |
| Empoisonnement de l'inventaire | source qui ment ou se répète | faux positif publié | anti-collusion par groupe de provenance + seuil 80 + détections requises | moyen (assumé) |
| Falsification de l'audit | accès base | perte de preuve | trigger append-only + test | faible |
| Fuite de secrets | commit accidentel | compromission de clés | `.gitignore` + test de non-suivi + test de motifs en dur | faible |
| Exposition réseau | port publié par erreur | accès non autorisé | publications `127.0.0.1` + test + tunnel SSH | faible |
| Publication non vérifiée | bug applicatif | faux sentiment de sécurité | relecture obligatoire avant `verified` | faible |
| Retrait non confirmé | panne distante | IOC encore actif ailleurs | `REMOVED` refusé tant que la révocation n'est pas confirmée | faible |
| Déni de service sur l'API | appels répétés | indisponibilité locale | API non exposée ; pas de rate-limiting (voir §7) | moyen |

---

## 4. Contrôles implémentés

### 4.1 Réseau

- `docker-compose.yml` : **toutes** les publications sont `127.0.0.1:<port>`.
  PostgreSQL n'est jamais joignable depuis le réseau Docker d'un autre projet.
- `docker-compose.aws.yml` : `db` sans publication (`ports: !override []`),
  frontend sur `127.0.0.1:80`, n8n sur `127.0.0.1:5678`.
- Sur EC2, **aucune règle de security group** n'a été ajoutée pour l'application.
  Preuves (4 méthodes) dans [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) :
  auto-test depuis l'instance, inspection DNAT, règles du security group,
  scan externe.
- Test automatisé : `test_published_ports_are_loopback_only`
  (analyse les deux fichiers compose, refuse aussi la syntaxe longue).

### 4.2 Secrets

- `.gitignore` couvre `*.pem`, `*.key`, `.env`, `.env.*`, `credentials.json`,
  `aws-credentials`.
- Test automatisé : `test_no_secret_file_is_tracked` (via `git ls-files`)
  et `test_gitignore_covers_secrets`.
- Test automatisé : `test_no_hardcoded_credential_pattern_in_source`
  (motifs `AKIA…`, `-----BEGIN … PRIVATE KEY-----`, jetons Slack).
- Identifiants AWS temporaires écrits **hors du dépôt**
  (`%TEMP%\opencode\aws_lab_credentials.txt`), expiration ≈ 4 h.
- `SECRET_KEY` et `N8N_ENCRYPTION_KEY` obligatoires : le compose refuse de
  démarrer s'ils manquent (`${VAR:?message}`).

### 4.3 Validation des entrées

`backend/app/services/normalization.py` :

- types stricts : IP (v4/v6), domaine (RFC 1035 + TLD alphabétique), URL
  (`http`/`https` uniquement), MD5/SHA1/SHA256 (hexadécimal exact) ;
- rejet explicite de `0.0.0.0`, `::`, **loopback**, **link-local** (dont
  `169.254.169.254`), multicast — valeurs non routables sans intérêt ;
- **les plages privées RFC1918 sont conservées volontairement** : un flux de
  réponse à incident interne peut légitimement les référencer ;
- aucune « réparation » silencieuse : une valeur invalide lève une erreur et
  n'est jamais stockée ;
- la valeur brute est conservée séparément (`raw_value`) pour l'analyse.

Tests : `TestHostileInput` (11 valeurs hostiles, tentative `DROP TABLE`,
dépassement de taille, incohérence de type).

### 4.4 Intégrité du journal d'audit

Trigger `trg_audit_immutable` :

```sql
CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
```

Tests : `test_audit_rows_cannot_be_updated`, `test_audit_rows_cannot_be_deleted`,
`test_trigger_is_present_in_schema`.

> `TRUNCATE` (utilisé uniquement par le script de purge explicite) ne déclenche
> pas un trigger ligne par ligne : c'est documenté et le script **revérifie
> ensuite** que le trigger est toujours en place.

### 4.5 Anti-collusion

Deux flux qui recopient la même source ne comptent que pour **une** organisation :

```python
# app/services/pipeline.py
select(func.count(func.distinct(IntelSource.provenance_group))) ...
```

Test : `test_same_organisation_does_not_multiply_independent_sources`
(2 flux du même groupe → 1 source indépendante ; +1 organisation → 2).

### 4.6 Vérification avant affirmation

| Opération | Preuve exigée |
|---|---|
| Publication | relecture de la ligne `publications` avant `verified` |
| Retrait | `SELECT count(*) … revoked_at IS NULL` = 0 avant `REMOVED` |
| Révocation MISP | confirmation distante par relecture |
| Rapport | toutes les valeurs relues en base, jamais estimées |
| Échec | conservé (`success=false`, `error=…`) et affiché |

### 4.7 Machine à états

`backend/app/lifecycle/machine.py` : table `TRANSITIONS` explicite.
Sauter une étape (`NEW → PUBLISHED`) ou ressusciter un `REMOVED` lève
`LifecycleError`. Tests : `TestLifecycleGuards`.

### 4.8 Moindre privilège (conteneurs)

- Image backend multi-stage : pas de compilateur dans l'image finale,
  utilisateur non-root `soar` (UID 10001).
- Volumes sondes montés en **lecture seule** (`:ro`).
- Limites mémoire par service (`deploy.resources.limits`).
- `restart: unless-stopped` : pas de redémarrage après arrêt volontaire.
- Image backend : mises à jour de sécurité Debian appliquées au build et
  outils d'empaquetage (pip, setuptools, wheel) **supprimés** de l'image finale
  (Trivy : 0 vulnérabilité HIGH/CRITICAL corrigeable).
- Image frontend : `nginx-unprivileged` (UID 101, port interne 8080) — Trivy
  DS-0002 corrigé.

### 4.9 Authentification et autorisations (v0.2)

| Contrôle | Implémentation | Preuve |
|---|---|---|
| Mots de passe | Argon2id (`argon2-cffi`), politique ≥ 12 caractères / 3 classes | `app/core/security.py`, `test_auth_api.py::test_password_policy` |
| Jetons | JWT HS256 signé par `SECRET_KEY`, expiration 60 min, `exp`/`sub` obligatoires | `test_tampered_token_rejected` |
| Révocation immédiate | le compte est relu à chaque requête : désactivation / changement de rôle effectifs sans attendre l'expiration | `test_disabled_account_token_is_rejected_immediately` |
| Rôles | `viewer` < `analyst` < `admin` ; lectures = viewer, opérations = analyst, comptes = admin | `TestAuthorization` |
| Identité tracée | l'acteur d'audit vient du jeton, jamais du corps de requête (l'ancien champ `actor` est ignoré) | `test_analyst_transition_uses_token_identity_not_body` |
| Automatisation | n8n s'authentifie par `X-API-Key` (comparaison à temps constant) ; libellé `X-Actor` filtré et préfixé (`service/…` sauf `workflow-N`) | `TestServiceKey` |
| Énumération | message unique « Identifiants invalides », coût Argon2 identique pour un compte inexistant | `test_bad_password_is_generic_and_audited` |
| Force brute | verrouillage du compte après 5 échecs (15 min) + 10 tentatives/min/IP sur `/auth/login` | `test_lockout_after_repeated_failures`, `test_login_rate_limited` |
| Dernier admin | impossible de se rétrograder/désactiver soi-même ou de retirer le dernier admin actif | `test_last_admin_cannot_demote_itself` |
| Erreurs | 422 sans écho des valeurs soumises (aucun mot de passe renvoyé) ; 500 sans pile | `test_validation_errors_never_echo_password` |
| Démarrage sûr | en `production`, refus de démarrer si `SECRET_KEY` faible, `AUTH_ENABLED=false`, `DEBUG=true` ou CORS `*` ; Swagger désactivé | `test_production_config_guard` |

### 4.10 Durcissement HTTP (v0.2)

- **Rate limiting** applicatif : 600 req/min/IP sur `/api`, 10/min sur le login
  (`app/core/middleware.py`, limiteur par processus — à porter dans le reverse
  proxy si plusieurs workers).
- **En-têtes** API : `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, `Cache-Control: no-store`.
- **nginx** (production) : CSP stricte (`default-src 'self'`, `frame-ancestors
  'none'`, `object-src 'none'`), `server_tokens off`, fichiers cachés refusés.
  Polices embarquées et jamais inlinées en `data:` pour respecter `font-src 'self'`.
- **CORS** : origines explicites, méthodes `GET/POST/PATCH`, en-têtes listés,
  pas de cookies (`allow_credentials=False`).
- **Traversée de chemin** corrigée : `POST /iocs/detections/ingest?path=` ne lit
  plus qu'à l'intérieur de `SENSOR_ROOT` (`test_sensor_path_traversal_refused`).
- **MISP** : vérification TLS activée par défaut (`MISP_VERIFY_CERT=true`).

---

## 5. Matrice de preuves

| Propriété | Test | Fichier |
|---|---|---|
| Audit immuable | 3 tests | `backend/tests/test_security.py` |
| Entrées hostiles rejetées | 12 tests | idem |
| Pas de saut d'état | 2 tests | idem |
| Anti-collusion | 1 test | idem |
| Aucun secret suivi | 3 tests | idem |
| Ports loopback | 2 tests (2 fichiers compose) | idem |
| Validation de normalisation | 35 tests | `test_normalization.py` |
| Cycle de vie | 23 tests | `test_lifecycle.py` |
| Notation / seuils | 19 tests | `test_scoring.py` |
| Pipeline de bout en bout | 11 tests | `test_pipeline.py` |
| MISP (client REST) | 18 tests mockés | `test_misp.py` |
| Collecteurs abuse.ch | 14 tests hors ligne | `test_abusech.py` |

Total : **191 tests**, exécutés contre un **vrai PostgreSQL**
(`soar_ioc_test`, migré par Alembic) — pas de SQLite de substitution.

---

## 6. Sécurité du déploiement AWS

| Élément | État |
|---|---|
| Security group de l'instance | `launch-wizard-1` — SSH restreint à `[masqué : IP administrateur]/32` depuis le **14/11/2026** (règle `[masqué : ID règle SG]`) ; `0.0.0.0/0` retirée. IP administrateur **dynamique** : à mettre à jour si elle change |
| Ports applicatifs | **aucun** ouvert dans le security group |
| Accès dashboard | tunnel SSH `-L 8091:127.0.0.1:80` |
| Bases de données | jamais publiées sur l'hôte EC2 |
| Coût | instance `stopped` hors session |

✅ **Durci le 14/11/2026.** SSH n'accepte plus que `[masqué : IP administrateur]/32` sur
`[masqué : ID security group]` (`[masqué : ID règle SG]`) ; la règle `0.0.0.0/0` a été
retirée après vérification. Preuves (commandes, relecture, tests) :
[`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) §2.2.

⚠️ **Risque résiduel** : l'IP de l'administrateur est dynamique. Si elle change,
l'SSH est refusé jusqu'à mise à jour de la règle — c'est le comportement attendu
d'un filtrage par IP. La console EC2 (Instance Connect / Session Manager) reste
un recours indépendant.

Autres recommandations non appliquées : `fail2ban`, désactivation de
`PasswordAuthentication`, MFA sur le compte AWS Academy.

---

## 7. Limites et risques assumés

| Limite | Impact | Décision |
|---|---|---|
| ~~API sans authentification~~ | — | **corrigé en v0.2** (§ 4.9) |
| ~~Pas de rate-limiting~~ | — | **corrigé en v0.2** (§ 4.10), limiteur par processus |
| **Jeton en `sessionStorage`** | un XSS pourrait lire le jeton de l'onglet | CSP stricte + échappement React ; durée 60 min ; pas de jeton de rafraîchissement |
| **Pas de révocation de jeton individuelle** | un jeton volé reste valable jusqu'à expiration | désactiver le compte le neutralise immédiatement |
| **`style-src 'unsafe-inline'`** | requis par les styles inline React/Recharts | signalé par ZAP (WARN), aucun script inline autorisé |
| **Compte PostgreSQL unique** | l'API utilise le propriétaire du schéma | trigger d'audit indépendant du rôle ; rôles séparés (migration vs runtime) recommandés en production |
| **Pas de TLS entre conteneurs** | trafic en clair sur le réseau Docker local | réseau bridge privé, mono-hôte |
| **Pas de vérité terrain** | précision/rappel non calculables | proxies mesurés uniquement, jamais présentés comme précision |
| **Plages privées acceptées** | un IOC interne peut entrer dans l'inventaire | choix fonctionnel documenté (réponse à incident) |
| **Clé abuse.ch absente ou révoquée** | 3 collecteurs indisponibles | échec explicite, aucune donnée simulée pour compenser |
| **MISP non déployé** | publication distante non exercée en réel | client + tests mockés, endpoint honnête (`skipped`) |

---

## 7 bis. Analyses de sécurité exécutées (16/11/2026)

| Outil | Cible | Résultat |
|---|---|---|
| Bandit 1.8.0 | `backend/app` (4 980 lignes) | 1 faux positif (B105, libellé d'audit) annoté `# nosec` → **0 problème** |
| pip-audit 2.7.3 | `backend/requirements.txt` | 24 avis : Starlette 0.41.3 (7, préexistant) + PyJWT 2.10.1 (17, version d'abord épinglée pour l'authentification) → FastAPI 0.163.1 / Starlette 1.10.0 / PyJWT 2.15.1 → **0** |
| npm audit | frontend (runtime) | **0** ; outillage de test : 3 (Vitest 3) → Vitest 4 → **0** |
| Trivy (image) | `soar-ioc-factory-api` | 3 HIGH (zlib1g, wheel, jaraco.context) → Dockerfile durci → **0 HIGH/CRITICAL corrigeable** |
| Trivy (config + secrets) | Dockerfiles, compose, workflows n8n, `.env.example` | 1 HIGH (nginx root) → image non-root → **0** ; aucun secret détecté |
| OWASP ZAP baseline | frontend nginx + API (image de production) | **0 FAIL, 60 PASS**, 2 WARN (CSP `unsafe-inline` pour les styles ; « Modern Web App » informatif) — rapport `reports/security/zap-baseline.html` |

## 8. Checklist opérationnelle

Avant une démonstration :

- [ ] `.env` présent, non versionné, permissions restreintes
- [ ] `git status` ne montre aucun fichier `.env` / `.pem`
- [ ] `docker compose config` ne publie que des ports `127.0.0.1`
- [ ] `pytest tests -q` → **191 passed**
- [ ] `GET /api/v1/system/health` → `healthy`
- [ ] Journal d'audit : aucune action `success=false` inexpliquée
- [ ] Aucun IOC `is_synthetic=true` présenté comme réel
- [ ] Instance EC2 arrêtée après la session

Après une session :

- [ ] `docker compose --profile n8n stop` (jamais `down -v`)
- [ ] tunnel SSH et serveur de dev arrêtés
- [ ] `aws ec2 stop-instances` exécuté
- [ ] identifiants temporaires AWS supprimés du poste

---

## 9. Signaler un problème

Ce projet est académique. En cas de faille constatée, ouvrir un ticket dans le
dépôt avec : version du commit (`git rev-parse --short HEAD`), étapes de
reproduction, impact estimé. Ne pas joindre de secret réel.
