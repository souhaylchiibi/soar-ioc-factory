# OUVRIR LE PROJET — Procédure complète

> État au 07/11/2026 : **tout est arrêté** (instance EC2 `stopped`, conteneurs locaux
> `Exited`, serveurs locaux coupés, onglets fermés). Les **données sont conservées**
> (volumes Docker + EBS). Suivez cette démarche pour tout relancer.

---

## A. OUVRIR LE PROJET EN LOCAL (≈ 2 minutes)

### A1. Prérequis
| Vérifier | Commande / action |
|---|---|
| Docker Desktop démarré | systray ou `docker version` |
| Node/npm | `node -v` (v25) |
| Python | `py -3.11 -v` |
| Clés API | déjà dans `SOAR project\.env` (OTX ✅, AbuseIPDB ✅, abuse.ch ❌ à régénérer) |

### A2. Démarrer le socle (PostgreSQL + API + n8n)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project"
docker compose --profile n8n up -d
```

### A3. Vérifier (tout doit répondre)
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health          # {"status":"ok"}
Invoke-RestMethod http://127.0.0.1:8000/ready            # base : ok
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health   # "healthy"
```
- **Swagger** : http://127.0.0.1:8000/docs
- **Données** : les 174 IOC locaux sont dans le volume `pgdata` (rien n'a été perdu).

### A4. Dashboard SOC (frontend)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project\frontend"
npm install          # seulement si node_modules absent
npm run dev
```
→ **http://127.0.0.1:5173/** (13 pages, données temps réel)

### A5. Tests (optionnel)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project\backend"
$env:PYTHONPATH="$PWD"; $env:POSTGRES_HOST="127.0.0.1"; $env:POSTGRES_USER="soar"
$env:POSTGRES_PASSWORD = (Select-String -Path ..\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
.\.venv\Scripts\python.exe -m pytest tests -q     # attendu : 177 passed (~42 s)
```

### A6. Services optionnels (profils)
```powershell
# Wazuh (detection) : voir docs + integrations/wazuh/*.sh
# Suricata (rejeu PCAP de labo) :
docker compose -f docker-compose.yml -f infrastructure/docker/docker-compose.suricata.yml `
  --profile detection up --abort-on-container-exit --exit-code-from suricata suricata
```

### A7. Livrables à jour (chiffres + figures)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project"

# 1. Métriques réelles + 7 graphiques + EVALUATION.md (lit PostgreSQL)
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py

# 2. Rapport Word du jury (réutilise metrics.json + captures)
.\backend\.venv\Scripts\python.exe scripts\generate_report.py
# -> reports/RAPPORT_SOAR_IOC_FACTORY.docx
```

### A8. Documentation de référence
```text
README.md                  point d'entrée du projet (chiffres, architecture, accès)
docs/INSTALLATION.md       installation reproductible + dépannage
docs/WORKFLOWS.md          les 8 workflows n8n (routes, fréquences, vérification)
docs/SECURITY.md           modèle de menace, contrôles, preuves, limites
docs/TESTING.md            stratégie et répartition des 177 tests
docs/USER_GUIDE.md         utilisation du dashboard et de l'API
reports/evaluation/        EVALUATION.md + metrics.json (Phase 7)
```

---

## B. OUVRIR LE PROJET SUR AWS (Learner Lab)

### B1. Lancer le lab
1. AWS Academy → votre cours → **Learner Lab** → **Start Lab** (statut vert).
2. ⚠️ **L'IP publique change à chaque start** — ne jamais réutiliser l'ancienne IP.

### B2. Démarrer l'instance (elle est `stopped` : données EBS intactes)
- Console lab : **EC2 → Instances → SOAR-IOC-SERVER → Instance state → Start**
- ou CLI (identifiants temporaires du lab, cf. B3) :
```powershell
aws ec2 start-instances --instance-ids [masqué : ID instance EC2]
aws ec2 wait instance-stopped ...   # inverse : wait instance-running
aws ec2 describe-instances --instance-ids [masqué : ID instance EC2] `
  --query "Reservations[].Instances[0].PublicIpAddress" --output text   # NOUVELLE IP
```
Les conteneurs repartent automatiquement (`restart: unless-stopped`).

### B3. Identifiants temporaires (nouvelle session = nouvelle clé)
- Console lab → **AWS Details → Show** → copier les 3 valeurs.
- Les écrire **hors du dépôt** : `%TEMP%\opencode\aws_lab_credentials.txt`
  (jamais dans `SOAR project/`, jamais dans Git — ils expirent seuls ~4 h).

### B4. Tunnel d'accès (aucun port exposé)
```powershell
ssh -i "C:\Users\T480s\Desktop\SOAR project\soar-ioc-key.pem" -N -L 8091:127.0.0.1:80 ubuntu@<NOUVELLE_IP>
```
→ **http://127.0.0.1:8091/** (dashboard complet hébergé sur EC2)

### B5. Si le serveur a besoin d'une remise à jour
```powershell
# transfert du code puis sur le serveur :
ssh -i soar-ioc-key.pem ubuntu@<IP> "cd ~/soar-ioc-factory && sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build"
```

### B6. ⚠️ IMPORTANT — économie des crédits
- **Arrêter l'instance en fin de session** : `aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]`
  (coût compute ramené à 0 ; seul l'EBS 40 Go reste ≈ 0,11 $/jour).
- Ne jamais laisser une `t2.large` allumée la nuit : elle consomme ~2,23 $/jour.

---

## C. FERMER TOUT (procédure utilisée le 07/11)

```powershell
# 1. AWS (économie)
aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]

# 2. Stack locale (volumes conservés !)
cd "C:\Users\T480s\Desktop\SOAR project"
docker compose --profile n8n stop
docker stop soar-wazuh        # s'il tourne

# 3. Frontend (Ctrl+C sur npm run dev) et tout tunnel SSH (Ctrl+C)
```
Ne **jamais** `docker compose down -v` ni `docker volume rm` : cela détruirait les données.

---

## D. PIÈGES CONNUS (diagnostiqués pendant le projet)

| Symptôme | Cause | Fix |
|---|---|---|
| `server closed the connection unexpectedly` (API/psql) | Proxy Docker Desktop **périmé** après un crash de Docker Desktop | `docker restart soar-postgres soar-api soar-n8n` |
| Conteneur « healthy » mais inaccessible depuis Windows | Le healthcheck tourne **dans** le conteneur (contourne le proxy) | idem + `docker ps` vérifier l'âge des conteneurs |
| `bash: syntax error near '('` en ssh Windows→Linux | PowerShell mange les guillemets | toujours `scp script.sh` + exécution |
| `.env` refusé par bash | Fins de ligne CRLF (fichier Windows) | `sed -i 's/\r$//' .env` (déjà fait sur EC2) |
| URLhaus/ThreatFox → 401 | Clé abuse.ch inconnue du serveur | régénérer sur **https://auth.abuse.ch/** puis `.env` |
| `n8n execute --id` : « Missing node to start execution » | Seul `manualTrigger` est un point d'entrée CLI valide | présent dans les JSON (généré automatiquement) |
| Port 80 paraît ouvert de l'extérieur | Faux positif de `Test-NetConnection` | preuve du blocage : self-test depuis l'instance + règles DNAT/SG (documenté) |

---

## OÙ TROUVER QUOI

| Élément | Chemin |
|---|---|
| Rapport Word | `reports/RAPPORT_SOAR_IOC_FACTORY.docx` |
| Évaluation Phase 7 | `reports/evaluation/EVALUATION.md` + `metrics.json` |
| Graphiques de l'évaluation (7) | `reports/figures/` |
| Captures (14) | `capture/` |
| Docs | `README.md` + `docs/` (installation, workflows, sécurité, tests, usage) |
| Workflows n8n | `workflows/n8n/*.json` (8) |
| Scripts AWS | `infrastructure/aws/` (5 scripts idempotents) |
| Historique | `git log` (16 commits) |
