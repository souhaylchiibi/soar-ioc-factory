# OUVRIR LE PROJET â€” ProcÃ©dure complÃ¨te

> Ã‰tat au 07/11/2026 : **tout est arrÃªtÃ©** (instance EC2 `stopped`, conteneurs locaux
> `Exited`, serveurs locaux coupÃ©s, onglets fermÃ©s). Les **donnÃ©es sont conservÃ©es**
> (volumes Docker + EBS). Suivez cette dÃ©marche pour tout relancer.

---

## A. OUVRIR LE PROJET EN LOCAL (â‰ˆ 2 minutes)

### A1. PrÃ©requis
| VÃ©rifier | Commande / action |
|---|---|
| Docker Desktop dÃ©marrÃ© | systray ou `docker version` |
| Node/npm | `node -v` (v25) |
| Python | `py -3.11 -v` |
| ClÃ©s API | dÃ©jÃ  dans `SOAR project\.env` (OTX âœ…, AbuseIPDB âœ…, abuse.ch âŒ Ã  rÃ©gÃ©nÃ©rer) |

### A2. DÃ©marrer le socle (PostgreSQL + API + n8n)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project"
docker compose --profile n8n up -d
```

### A3. VÃ©rifier (tout doit rÃ©pondre)
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health          # {"status":"ok"}
Invoke-RestMethod http://127.0.0.1:8000/ready            # base : ok
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/health   # "healthy"
```
- **Swagger** : http://127.0.0.1:8000/docs
- **DonnÃ©es** : les 174 IOC locaux sont dans le volume `pgdata` (rien n'a Ã©tÃ© perdu).

### A4. Dashboard SOC (frontend)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project\frontend"
npm install          # seulement si node_modules absent
npm run dev
```
â†’ **http://127.0.0.1:5173/** (13 pages, donnÃ©es temps rÃ©el)

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

### A7. Livrables Ã  jour (chiffres + figures)
```powershell
cd "C:\Users\T480s\Desktop\SOAR project"

# 1. MÃ©triques rÃ©elles + 7 graphiques + EVALUATION.md (lit PostgreSQL)
.\backend\.venv\Scripts\python.exe scripts\evaluate_platform.py

# 2. Rapport Word du jury (rÃ©utilise metrics.json + captures)
.\backend\.venv\Scripts\python.exe scripts\generate_report.py
# -> reports/RAPPORT_SOAR_IOC_FACTORY.docx

# 3. Rapport final complet (page de garde, sommaire, 32 tableaux, 22 figures)
.\backend\.venv\Scripts\python.exe scripts\build_final_report.py
# -> reports/RAPPORT_FINAL.docx
```

### A8. Documentation de rÃ©fÃ©rence
```text
README.md                  point d'entrÃ©e du projet (chiffres, architecture, accÃ¨s)
docs/INSTALLATION.md       installation reproductible + dÃ©pannage
docs/WORKFLOWS.md          les 8 workflows n8n (routes, frÃ©quences, vÃ©rification)
docs/SECURITY.md           modÃ¨le de menace, contrÃ´les, preuves, limites
docs/TESTING.md            stratÃ©gie et rÃ©partition des 177 tests
docs/USER_GUIDE.md         utilisation du dashboard et de l'API
reports/evaluation/        EVALUATION.md + metrics.json (Phase 7)
```

---

## B. OUVRIR LE PROJET SUR AWS (Learner Lab)

### B1. Lancer le lab
1. AWS Academy â†’ votre cours â†’ **Learner Lab** â†’ **Start Lab** (statut vert).
2. âš ï¸ **L'IP publique change Ã  chaque start** â€” ne jamais rÃ©utiliser l'ancienne IP.

### B2. DÃ©marrer l'instance (elle est `stopped` : donnÃ©es EBS intactes)
- Console lab : **EC2 â†’ Instances â†’ SOAR-IOC-SERVER â†’ Instance state â†’ Start**
- ou CLI (identifiants temporaires du lab, cf. B3) :
```powershell
aws ec2 start-instances --instance-ids [masqué : ID instance EC2]
aws ec2 wait instance-stopped ...   # inverse : wait instance-running
aws ec2 describe-instances --instance-ids [masqué : ID instance EC2] `
  --query "Reservations[].Instances[0].PublicIpAddress" --output text   # NOUVELLE IP
```
Les conteneurs repartent automatiquement (`restart: unless-stopped`).

### B3. Identifiants temporaires (nouvelle session = nouvelle clÃ©)
- Console lab â†’ **AWS Details â†’ Show** â†’ copier les 3 valeurs.
- Les Ã©crire **hors du dÃ©pÃ´t** : `%TEMP%\opencode\aws_lab_credentials.txt`
  (jamais dans `SOAR project/`, jamais dans Git â€” ils expirent seuls ~4 h).

### B4. Tunnel d'accÃ¨s (aucun port exposÃ©)
```powershell
ssh -i "C:\Users\T480s\Desktop\SOAR project\soar-ioc-key.pem" -N -L 8091:127.0.0.1:80 ubuntu@<NOUVELLE_IP>
```
â†’ **http://127.0.0.1:8091/** (dashboard complet hÃ©bergÃ© sur EC2)

### B5. Si le serveur a besoin d'une remise Ã  jour
```powershell
# transfert du code puis sur le serveur :
ssh -i soar-ioc-key.pem ubuntu@<IP> "cd ~/soar-ioc-factory && sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build"
```

### B6. âš ï¸ IMPORTANT â€” Ã©conomie des crÃ©dits
- **ArrÃªter l'instance en fin de session** : `aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]`
  (coÃ»t compute ramenÃ© Ã  0 ; seul l'EBS 40 Go reste â‰ˆ 0,11 $/jour).
- Ne jamais laisser une `t2.large` allumÃ©e la nuit : elle consomme ~2,23 $/jour.

---

## C. FERMER TOUT (procÃ©dure utilisÃ©e le 07/11)

```powershell
# 1. AWS (Ã©conomie)
aws ec2 stop-instances --instance-ids [masqué : ID instance EC2]

# 2. Stack locale (volumes conservÃ©s !)
cd "C:\Users\T480s\Desktop\SOAR project"
docker compose --profile n8n stop
docker stop soar-wazuh        # s'il tourne

# 3. Frontend (Ctrl+C sur npm run dev) et tout tunnel SSH (Ctrl+C)
```
Ne **jamais** `docker compose down -v` ni `docker volume rm` : cela dÃ©truirait les donnÃ©es.

---

## D. PIÃˆGES CONNUS (diagnostiquÃ©s pendant le projet)

| SymptÃ´me | Cause | Fix |
|---|---|---|
| `server closed the connection unexpectedly` (API/psql) | Proxy Docker Desktop **pÃ©rimÃ©** aprÃ¨s un crash de Docker Desktop | `docker restart soar-postgres soar-api soar-n8n` |
| Conteneur Â« healthy Â» mais inaccessible depuis Windows | Le healthcheck tourne **dans** le conteneur (contourne le proxy) | idem + `docker ps` vÃ©rifier l'Ã¢ge des conteneurs |
| `bash: syntax error near '('` en ssh Windowsâ†’Linux | PowerShell mange les guillemets | toujours `scp script.sh` + exÃ©cution |
| `.env` refusÃ© par bash | Fins de ligne CRLF (fichier Windows) | `sed -i 's/\r$//' .env` (dÃ©jÃ  fait sur EC2) |
| URLhaus/ThreatFox â†’ 401 | ClÃ© abuse.ch inconnue du serveur | rÃ©gÃ©nÃ©rer sur **https://auth.abuse.ch/** puis `.env` |
| `n8n execute --id` : Â« Missing node to start execution Â» | Seul `manualTrigger` est un point d'entrÃ©e CLI valide | prÃ©sent dans les JSON (gÃ©nÃ©rÃ© automatiquement) |
| Port 80 paraÃ®t ouvert de l'extÃ©rieur | Faux positif de `Test-NetConnection` | preuve du blocage : self-test depuis l'instance + rÃ¨gles DNAT/SG (documentÃ©) |

---

## OÃ™ TROUVER QUOI

| Ã‰lÃ©ment | Chemin |
|---|---|
| Rapport Word (court) | `reports/RAPPORT_SOAR_IOC_FACTORY.docx` |
| Rapport Word (final, complet) | `reports/RAPPORT_FINAL.docx` |
| Ã‰valuation Phase 7 | `reports/evaluation/EVALUATION.md` + `metrics.json` |
| Graphiques de l'Ã©valuation (7) | `reports/figures/` |
| Captures (14) | `capture/` |
| Docs | `README.md` + `docs/` (installation, workflows, sÃ©curitÃ©, tests, usage) |
| Workflows n8n | `workflows/n8n/*.json` (8) |
| Scripts AWS | `infrastructure/aws/` (5 scripts idempotents) |
| Historique | `git log` (16 commits) |
