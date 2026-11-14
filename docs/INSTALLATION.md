# Installation et configuration

> Procédure reproductible, validée sur Windows 11 + Docker Desktop (backend WSL2)
> et sur Ubuntu 24.04 (EC2). Toutes les commandes sont idempotentes.

---

## 1. Prérequis

| Outil | Version testée | Vérification |
|---|---|---|
| Docker Desktop | 29.9.2 | `docker version` |
| Python | 3.11 | `py -3.11 -V` |
| Node.js / npm | 25.x / 11.x | `node -v`, `npm -v` |
| Git | 2.4x | `git --version` |
| (optionnel) AWS CLI | 2.x | `aws --version` |

Ressources : ≈ 4 Go de RAM libres, ≈ 8 Go d'espace disque.
Les images nécessaires pèsent ≈ 5,3 Go (API, PostgreSQL, n8n, Suricata, Wazuh).

---

## 2. Récupérer le code

```powershell
cd "C:\Users\T480s\Desktop"
git clone <url-du-depot> "SOAR project"
cd "SOAR project"
```

> Le binaire `soar-ioc-key.pem` (clé SSH EC2) **n'est pas** dans le dépôt :
> il est ignoré par git et doit être fourni séparément.

---

## 3. Configurer les secrets

```powershell
Copy-Item .env.example .env
```

Puis renseigner **au minimum** :

```ini
POSTGRES_PASSWORD=<mot de passe long>
SECRET_KEY=<48 caractères aléatoires>
N8N_ENCRYPTION_KEY=<32 caractères aléatoires>
```

Génération des valeurs :

```powershell
py -3.11 -c "import secrets; print(secrets.token_urlsafe(48))"
py -3.11 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Clés API facultatives (les collecteurs fonctionnent sans, sauf abuse.ch) :

| Variable | Usage | Sans clé |
|---|---|---|
| `OTX_API_KEY` | pulses OTX abonnés | OTX public limité |
| `ABUSEIPDB_API_KEY` | réputation IP | AbuseIPDB ignoré |
| `ABUSECH_AUTH_KEY` | URLhaus / ThreatFox / MalwareBazaar | collecteurs en échec explicite (aucune donnée simulée) |
| `MISP_URL` + `MISP_KEY` | publication MISP | endpoint répond `skipped` |

> ⚠️ `.env` est ignoré par git. Ne jamais le copier dans un rendu, une capture
> ou un dépôt public.

---

## 4. Démarrer le socle

```powershell
# PostgreSQL + API (obligatoire)
docker compose up -d

# + n8n (orchestration)
docker compose --profile n8n up -d
```

Le volume `soar_wazuh_alerts` est déclaré `external`. S'il n'existe pas encore :

```powershell
docker volume create soar_wazuh_alerts
```

Vérifications :

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
# {"status":"ok"}

Invoke-RestMethod http://127.0.0.1:8000/ready
# {"status":"ready","database":{"status":"ok","detail":"ok"}}

Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health
# status = healthy
```

| Service | Port | Exposition |
|---|---|---|
| API | 8000 | `127.0.0.1` uniquement |
| PostgreSQL | 5432 | `127.0.0.1` uniquement |
| n8n | 5678 | `127.0.0.1` uniquement |

---

## 5. Base de données et migrations

Deux mécanismes complémentaires :

1. **Création des bases** au premier démarrage PostgreSQL :
   `infrastructure/docker/postgres-init/01-init-databases.sql`
   (crée `soar_ioc` et la base d'orchestration `soar_n8n`).
2. **Schéma applicatif** via Alembic :

```powershell
cd backend
$env:PYTHONPATH="$PWD"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD=(Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Migration initiale : `dadb423768cb` (IOC, sources, cycle de vie, audit,
publications, détections, politiques, rapports).

> Le mot de passe contient parfois `%` : `database/migrations/env.py` double
> déjà les `%` avant `set_main_option`, aucune action manuelle n'est requise.

---

## 6. Environnement Python (tests et scripts)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` ajoute pytest, ruff, matplotlib et python-docx
(scripts d'évaluation et de rapport uniquement — jamais dans l'image runtime).

---

## 7. Frontend

```powershell
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173/
```

Le proxy Vite redirige `/api` et `/health` vers `http://127.0.0.1:8000`.
Pour un build de production :

```powershell
npm run build      # tsc -b && vite build -> frontend/dist
```

---

## 8. Profils optionnels

### Suricata (rejeu de PCAP de laboratoire)

```powershell
docker compose -f docker-compose.yml -f infrastructure/docker/docker-compose.suricata.yml `
  --profile detection up --abort-on-container-exit --exit-code-from suricata suricata
```

Le conteneur **sort avec le code 0** : c'est un traitement par lot (rejeu),
pas un démon. Les règles sont générées depuis les IOC publiés :

```powershell
.\backend\.venv\Scripts\python.exe scripts\generate_detection_lists.py
```

### Wazuh

```powershell
docker run -d --name soar-wazuh --network soar-ioc-factory_soar-net `
  -v soar_wazuh_alerts:/var/ossec/logs/alerts wazuh/wazuh-manager:4.12.0
```

Les règles personnalisées sont dans `integrations/wazuh/`.

### MISP

Renseigner `MISP_URL` / `MISP_KEY` dans `.env`, puis :

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/iocs/publish/misp/run
```

Sans configuration, la réponse est explicite :

```json
{ "status": "skipped", "detail": "MISP_URL / MISP_KEY absents" }
```

---

## 9. Déploiement AWS (résumé)

Procédure complète : [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).

```powershell
# Sur l'instance (Ubuntu 24.04), depuis ~/soar-ioc-factory
sudo bash infrastructure/aws/install_docker.sh
sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build
sudo bash infrastructure/aws/run_migrations.sh
```

Accès **uniquement** par tunnel SSH :

```powershell
ssh -i soar-ioc-key.pem -N -L 8091:127.0.0.1:80 ubuntu@<IP_PUBLIQUE>
# -> http://127.0.0.1:8091/
```

Aucun port n'est ouvert dans le security group pour l'application.

---

## 10. Dépannage

| Symptôme | Cause | Correction |
|---|---|---|
| `network ... not found` au `up` | réseau Docker orphelin après nettoyage | `docker compose down` puis `docker network prune -f` puis `up` |
| API « healthy » mais injoignable depuis Windows | proxy Docker Desktop périmé | `docker restart soar-postgres soar-api soar-n8n` |
| `server closed the connection unexpectedly` | même cause | idem |
| `POSTGRES_PASSWORD requis` | `.env` absent ou vide | recopier `.env.example` |
| n8n ne démarre pas | base `soar_n8n` absente | vérifier `01-init-databases.sql` puis recréer le conteneur |
| URLhaus/ThreatFox → 401 | clé abuse.ch inconnue | régénérer sur <https://auth.abuse.ch/> |
| `docker compose down -v` | **destruction des volumes** | ne jamais l'utiliser ; utiliser `stop` |
| Port 80 semble ouvert de l'extérieur | faux positif de scan | voir preuves dans `AWS_DEPLOYMENT.md` |

---

## 11. Réinitialiser les données de démonstration

⚠️ Opération destructive, protégée par confirmation explicite :

```powershell
$env:CONFIRM_PURGE="YES-I-APPROVE"
.\backend\.venv\Scripts\python.exe scripts\purge_lab_data.py
```

Le script utilise `TRUNCATE` (qui ne déclenche pas le trigger ligne par ligne)
et **vérifie ensuite que le trigger `trg_audit_immutable` est toujours actif**.

---

## 12. Fermer proprement

```powershell
docker compose --profile n8n stop      # volumes conservés
docker stop soar-wazuh                 # si lancé
# Ctrl+C sur npm run dev et sur le tunnel SSH
aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]   # AWS
```

Ne **jamais** : `docker compose down -v`, `docker volume rm`, `docker system prune --volumes`.
