# AWS DEPLOYMENT — SOAR IOC Factory

> **Phase 8** · AWS Academy Learner Lab · Compte `[masqué : ID compte AWS]` (rôle `voclabs`)
> Date du déploiement : 2026-11-07 · **Aucune nouvelle ressource créée, aucun changement de sécurité réseau.**

---

## 1. Résumé exécutif

| Élément | Valeur |
|---|---|
| Instance | `[masqué : ID instance EC2]` — nom **SOAR-IOC-SERVER** (existante, réutilisée) |
| Type / OS | **t2.large** (2 vCPU, 8 Go) · Ubuntu 24.04.5 LTS · us-east-1 |
| IP publique | `[masqué : IP publique EC2]` au 14/11/2026 (change à chaque `start` — SSH uniquement) |
| Clé | `soar-ioc-key.pem` (locale, **jamais copiée sur le serveur**) |
| Disque | 40 Go gp3 (`[masqué : ID volume EBS]`) |
| Stack | Docker 29.9.3 + Compose v5.7 → `postgres`, `api`, `n8n`, `frontend` |
| État | **`/api/v1/system/health` = `healthy`** · 94 IOC réels collectés |
| Accès démo | **Tunnel SSH** (aucun port exposé, aucun SG modifié) |
| Ressources créées | **0** (aucun run-instances, aucun create-bucket) |
| Coût supplémentaire créé par le déploiement | **0 $** — seule l'instance déjà lancée facture |

---

## 2. Posture de sécurité vérifiée (preuves)

### 2.1 Aucune exposition publique

```
Listeners EC2 :   127.0.0.1:80 · 127.0.0.1:8000 · 127.0.0.1:5678   (loopback seulement)
                  5432/tcp : NON publié (réseau Docker interne uniquement)
iptables DOCKER : -A DOCKER -d 127.0.0.1/32 --dport 80 -j DNAT ...  (ne matche QUE le loopback)
Self-test EC2 → son IP publique:80 = TIMEOUT (SG filtre)
```

Règles security group (état **après durcissement du 14/11/2026**) :

| SG | Règles |
|---|---|
| `[masqué : ID security group]` (launch-wizard-1, **attaché à l'instance**) | tcp/22 depuis `[masqué : IP administrateur]/32` uniquement — règle `[masqué : ID règle SG]` ; `0.0.0.0/0` **retirée** (`[masqué : ID règle SG]`) |
| `[masqué : ID security group par défaut]` (default) | tcp/22 depuis `[masqué : ancienne IP administrateur]/32` (ancienne IP de l'étudiant, 07/11) |

- **Ports 80/8000/5432/5678 : aucune règle → impossible d'y accéder de l'extérieur.**
- ⚠️ Relevé : `Test-NetConnection` local a signalé un faux « port80 ouvert » ; le test
  TCP brut depuis le poste et le self-test depuis l'instance prouvent le filtrage
  (méthode de vérification : `infrastructure/aws/`, scripts `tcp_scan` + `check_exposure`).

### 2.2 Durcissement SSH — appliqué le 14/11/2026

**Décision** : restreindre l'SSH à l'IP de l'administrateur, puis retirer l'ouverture
mondiale. SG concerné : `launch-wizard-1` (`[masqué : ID security group]`).

**Exécution (preuves AWS CLI)** :

| Étape | Résultat |
|---|---|
| `authorize-security-group-ingress --cidr [masqué : IP administrateur]/32` | règle `[masqué : ID règle SG]` créée |
| Relecture du SG avant retrait | `0.0.0.0/0` **et** `[masqué : IP administrateur]/32` présents (garde-fou) |
| `revoke-security-group-ingress --cidr 0.0.0.0/0` | règle `[masqué : ID règle SG]` supprimée |
| Relecture finale | `tcp/22` → **uniquement** `[masqué : IP administrateur]/32` |
| Test SSH depuis le poste | `SSH_OK` (hôte `ip-172-31-35-188`) |
| Test TCP 80 depuis Internet | timeout (aucun port applicatif exposé) |

> L'IP publique de l'étudiant est **dynamique** : elle était `[masqué : ancienne IP administrateur]` le 07/11,
> `[masqué : IP administrateur]` le 14/11. Si elle change, l'SSH est refusé — il faut mettre à jour
> la règle (commandes ci-dessous). C'est le prix du durcissement ; le retour arrière
> reste possible.

IP publique de l'**instance** au 14/11/2026 : `[masqué : IP publique EC2]` (elle change à chaque
`start`, aucune Elastic IP — mettre à jour la commande `ssh` à chaque session).

```bash
SG=[masqué : ID security group]
IP=$(curl -s https://api.ipify.org)/32     # votre IP publique du moment

# Mettre a jour la regle (ajouter la nouvelle IP)
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr $IP

# Verifier, puis retirer l'ancienne IP si elle n'est plus utilisee
aws ec2 describe-security-groups --group-ids $SG \
  --query "SecurityGroups[0].IpPermissions[].IpRanges[].CidrIp" --output text
```

Retour arrière d'urgence (si vous perdez l'accès) :

```bash
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr 0.0.0.0/0
```

### 2.3 Secrets

| Secret | Emplacement | Transit |
|---|---|---|
| `soar-ioc-key.pem` | poste local uniquement (exclue Git **et** exclue de l'archive de déploiement — vérifié `tar -tzf`) | SCP/SSH chiffrés |
| `.env` (clés OTX/AbuseIPDB/abuse.ch + mots de passe) | serveur `~/soar-ioc-factory/.env`, `chmod 600`, LF | SCP sur SSH chiffré |
| Identifiants AWS temporaires | **hors dépôt** : `%TEMP%\opencode\aws_lab_credentials.txt` | expirent seuls (~4 h) |

---

## 3. Coûts (ordres de grandeur — à confronter au calculateur AWS)

| Ressource | Tarif us-east-1 (indicatif) | Consommation ici |
|---|---|---|
| EC2 t2.large (Linux) | ≈ **0,093 $/h** | **en cours** tant que l'instance tourne (≈ 2,23 $/j) |
| EBS gp3 40 Go | ≈ 0,08 $/Go-mois | ≈ 0,11 $/j (facturé même à l'arrêt) |
| S3 | 0,023 $/Go-mois | **0 bucket** (0 $) |
| Données sortantes | 0,09 $/Go | négligeable (démo) |
| NAT Gateway / ALB / RDS | — | **jamais utilisés** (interdits par le plan) |

- **Coût du déploiement lui-même : 0 $** (réutilisation intégrale de l'instance existante).
- ⚠️ **Crédits Learner Lab quotidiens** : une instance t2.large allumée 24 h/24 les consomme.
  **Vérifiez votre solde dans la console** (bannière de crédits du lab).

> **État à la livraison (14/11/2026, 02:00 UTC+1)** : instance `[masqué : ID instance EC2]`
> **stopped** (`describe-instances` : `State.Name = stopped`, adresse publique libérée),
> tunnel SSH fermé, port local 8091 refusé. Seul le volume EBS reste facturé (≈ 0,11 $/j).
> La démonstration AWS de la Figure 22 a été capturée avant l'arrêt.

### Cycle de vie (choix validés par l'utilisateur)

```bash
# ARRÊTER en fin de session (disque conservé, coût ≈ 0, données intactes)
aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]
# ou dans la console : Actions → Instance State → Stop

# REDÉMARRER (IP publique NEW à chaque start → maj du tunnel !)
aws ec2 start-instances --instance-ids [masqué : ID instance EC2]

# FIN DE LAB uniquement (supprime l'instance + EBS — demande explicitement !)
# aws ec2 terminate-instances ...
```

---

## 4. Déploiement reproductible (5 scripts, aucun setw)

```bash
# 0. (poste) identifiants temporaires du lab dans un fichier HORS dépôt
#    %TEMP%\opencode\aws_lab_credentials.txt

# 1. Vérification lecture seule — 0 USD
python infrastructure/aws/verify_lab.py

# 2. Transfert du projet (exclut .pem, .venv, node_modules)
tar -czf soar-deploy.tar.gz --exclude='backend/.venv' \
    --exclude='frontend/node_modules' --exclude='*.pem' .
scp -i soar-ioc-key.pem soar-deploy.tar.gz ubuntu@<IP>:/tmp/

# 3. Docker Engine (repo officiel, idempotent)
ssh -i soar-ioc-key.pem ubuntu@<IP> /tmp/install_docker.sh

# 4. Stack (override aws = ports loopback only) + migration + données réelles
ssh -i soar-ioc-key.pem ubuntu@<IP> /tmp/deploy_stack.sh
ssh -i soar-ioc-key.pem ubuntu@<IP> /tmp/run_migrations.sh
ssh -i soar-ioc-key.pem ubuntu@<IP> /tmp/seed_real_data.sh
```

Détail des scripts : `infrastructure/aws/`

| Script | Rôle | Idempotent |
|---|---|---|
| `verify_lab.py` | inventaire lecture seule (EC2/VPC/S3/SG) | ✅ |
| `install_docker.sh` | Docker Engine + Compose (skip si présent) | ✅ |
| `deploy_stack.sh` | `compose up` profil `n8n` + vérifications | ✅ |
| `run_migrations.sh` | Alembic head dans conteneur (CRLF-safe) | ✅ |
| `seed_real_data.sh` | sources + collecte/enrichissement/scoring **réels** | ✅ |

Éléments clés du déploiement :
- `docker-compose.aws.yml` — **override** : frontend `127.0.0.1:80`, API `127.0.0.1:8000`,
  **PostgreSQL sans aucun port publié**, n8n en `127.0.0.1:5678`
- `Dockerfile.frontend` + `nginx.conf` — SPA statique + proxy `/api`→`api:8000`
- `.env` : `chmod 600`, converti en LF au déploiement (CRLF Windows)

---

## 5. Accès / démonstration (tunnel SSH)

```powershell
# Poste étudiant — un seul tunnel local, aucun port public
ssh -i "C:\Users\T480s\Desktop\SOAR project\soar-ioc-key.pem" `
    -N -L 8091:127.0.0.1:80 ubuntu@[masqué : IP publique EC2]
```

Puis : **http://127.0.0.1:8091/** → dashboard SOC complet (13 pages).

> ⚠️ L'IP publique change à chaque **start** d'instance : mettre à jour la commande du tunnel.

---

## 6. Vérifications effectuées (jour du déploiement)

| # | Vérification | Résultat |
|---|---|---|
| 1 | `sts get-caller-identity` | compte [masqué : ID compte AWS], rôle voclabs ✅ |
| 2 | Inventaire des ressources existantes | 1 instance t2.large (réutilisée) ✅ |
| 3 | Ports écoutés sur l'instance | loopback uniquement ✅ |
| 4 | DNAT iptables | condition `-d 127.0.0.1/32` ✅ |
| 5 | Self-test IP publique:80 depuis l'instance | timeout (SG filtre) ✅ |
| 6 | Scan TCP externe (22/80/8000/5432/5678) | seul 22 joignable ✅ |
| 7 | Migrations Alembic | `dadb423768cb (head)` ✅ |
| 8 | Health | `healthy` ✅ |
| 9 | Collecte réelle depuis EC2 | 94 IOC (OTX+feodo+blocklist+urlscan) ✅ |
| 10 | Enrichissement (OTX+AbuseIPDB) | 25/25, 0 erreur ✅ |
| 11 | Scoring | 73 monitor / 21 reject, moyenne 54,7 ✅ |
| 12 | Dashboard via tunnel | capture `capture/2026-11-17/aws-02-overview.png` ✅ |

---

## 7. Interdits respectés (cahier des charges §8)

- ✅ Aucune création de ressource sans validation écrite
- ✅ Aucune suppression / aucun arrêt imposé d'une ressource existante
- ✅ PostgreSQL jamais exposé (aucun port publié)
- ✅ Aucune clé dans Git (`.env`/`*.pem` ignorés, vérifié par `git check-ignore`)
- ✅ Identifiants AWS temporaires hors dépôt, jamais écrits dans les sources
- ✅ Aucun NAT Gateway / ALB / RDS (pas de coûts récurrents cachés)
- ✅ Coûts estimés **avant** tout déploiement (§3)
