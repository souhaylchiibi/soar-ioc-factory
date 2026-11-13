# AWS DEPLOYMENT — SOAR IOC Factory

> **Phase 8** · AWS Academy Learner Lab · Compte `[masqué : ID compte AWS]` (rôle `voclabs`)
> Date du déploiement : 2026-11-07 · **Aucune nouvelle ressource créée, aucun changement de sécurité réseau.**

---

## 1. Résumé exécutif

| Élément | Valeur |
|---|---|
| Instance | `[masqué : ID instance EC2]` — nom **SOAR-IOC-SERVER** (existante, réutilisée) |
| Type / OS | **t2.large** (2 vCPU, 8 Go) · Ubuntu 24.04.5 LTS · us-east-1 |
| IP publique | `13.217.103.186` (SSH uniquement) |
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

Règles security group en place au 07/11/2026 (**état historique, à corriger — voir §2.2**) :

| SG | Règles |
|---|---|
| `[masqué : ID security group]` (launch-wizard-1, **attaché à l'instance**) | tcp/22 depuis `0.0.0.0/0` |
| `[masqué : ID security group par défaut]` (default) | tcp/22 depuis `[masqué : ancienne IP administrateur]/32` (= IP publique de l'étudiant) |

- **Ports 80/8000/5432/5678 : aucune règle → impossible d'y accéder de l'extérieur.**
- ⚠️ Relevé : `Test-NetConnection` local a signalé un faux « port80 ouvert » ; le test
  TCP brut depuis le poste et le self-test depuis l'instance prouvent le filtrage
  (méthode de vérification : `infrastructure/aws/`, scripts `tcp_scan` + `check_exposure`).

### 2.2 Durcissement SSH — décision prise, application en attente

**Décision (14/11/2026)** : restreindre l'SSH à l'IP de l'administrateur, puis retirer
l'ouverture mondiale. Le SG `launch-wizard-1` (`[masqué : ID security group]`) est celui attaché
à l'instance ; c'est lui qu'il faut corriger.

> ⚠️ **Non appliqué à ce jour** : les identifiants AWS Academy enregistrés le 07/11 ont
> expiré (`InvalidClientTokenId`, jetons valables ~4 h). Aucune commande AWS n'a été
> exécutée depuis. La procédure ci-dessous est prête et rejouable.

IP publique constatée le 14/11/2026 : `[masqué : IP administrateur]` (adresse **dynamique** — la
revérifier avant d'appliquer : <https://api.ipify.org>).

```bash
SG=[masqué : ID security group]
IP=[masqué : IP administrateur]/32          # <-- verifier votre IP publique AVANT

# 1. Ajouter la regle /32 (idempotent : ignorer InvalidPermission.Duplicate)
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr $IP

# 2. Verifier que la regle /32 existe bien, puis seulement retirer 0.0.0.0/0
aws ec2 describe-security-groups --group-ids $SG \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\`]"

aws ec2 revoke-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr 0.0.0.0/0
```

Vérification finale (doit ne plus retourner que le `/32`) :

```bash
aws ec2 describe-security-groups --group-ids $SG \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\`].IpRanges[].CidrIp" --output text
```

Retour arrière (si l'accès est perdu à cause d'un changement d'IP) :

```bash
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr 0.0.0.0/0
```

> L'instance peut rester **arrêtée** pendant l'opération : une règle de SG ne nécessite
> pas d'instance en cours d'exécution. En cas de verrouillage, la console EC2
> (Instance Connect / session manager) reste un recours indépendant de la règle SSH.

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
    -N -L 8091:127.0.0.1:80 ubuntu@13.217.103.186
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
| 12 | Dashboard via tunnel | capture `capture/11-aws-dashboard-ec2.jpg` ✅ |

---

## 7. Interdits respectés (cahier des charges §8)

- ✅ Aucune création de ressource sans validation écrite
- ✅ Aucune suppression / aucun arrêt imposé d'une ressource existante
- ✅ PostgreSQL jamais exposé (aucun port publié)
- ✅ Aucune clé dans Git (`.env`/`*.pem` ignorés, vérifié par `git check-ignore`)
- ✅ Identifiants AWS temporaires hors dépôt, jamais écrits dans les sources
- ✅ Aucun NAT Gateway / ALB / RDS (pas de coûts récurrents cachés)
- ✅ Coûts estimés **avant** tout déploiement (§3)
