# PHASE 0 — RAPPORT D'AUDIT

> Date : 2026-11-06 — Méthode : lecture uniquement, aucun système modifié (tests réseau en GET/HEAD).

## 1. Machine principale

| Élément | Constat |
|---|---|
| OS | Windows 10 Professionnel 19045 (64-bit) |
| CPU | Intel Core i7-8550U — 4 cœurs / 8 threads |
| RAM | 24,0 Go physiques — **11,4 Go libres** à l'audit |
| Disque C: | **76,6 Go libres** |
| Hyperviseur | Présent, WSL2 actif ✅ |

## 2. Outils installés (Windows)

| Outil | Version | État |
|---|---|---|
| Python | 3.11.9 (`py`, pip 26.1.2, venv OK) | ✅ — `python` absent du PATH, utiliser `py` |
| Git | 2.51.0.windows.2 | ✅ — identité configurée : Souhayl Chouaibi |
| Node.js / npm | v25.9.0 / 11.14.1 | ✅ |
| Docker Desktop | **4.98.0** (client 29.9.2, Compose v5.6.1) | ✅ installé et vérifié : démon actif, 8 CPU, 12,4 Go RAM |
| AWS CLI | — | ❌ (Phase 8) |
| psql | — | ❌ (PostgreSQL exécuté en conteneur) |

## 3. WSL 2

| Élément | Constat |
|---|---|
| Distro | Ubuntu 24.04.3 LTS (WSL 3.0.1.0, noyau 6.18.40.1) |
| Utilisateur | `souhayl` — `sudo` protégé par mot de passe |
| Python | 3.12.3, venv OK, pip système absent |
| Docker | intégration WSL à vérifier (client Windows utilisable) |
| RAM / disque | ~11,9 Go (50 %) — 954 Go « virtuels » (VHD creux sur C:) |
| systemd | présent, état *degraded* à surveiller |
| Réseau sortant | ✅ |

## 4. Accès externes testés (non intrusifs)

| Cible | Résultat |
|---|---|
| PyPI / Docker Hub / GitHub / npm | ✅ joignables |
| AWS STS | ✅ joignable (aucun profil `~/.aws` configuré) |
| AlienVault OTX | ✅ joignable |
| ThreatFox (abuse.ch) | ✅ joignable |
| **URLhaus (abuse.ch)** | ⚠️ **401 — authentification exigée** |
| AbuseIPDB | ⚠️ 401 sans clé (attendu) |

**Conséquence de conception** : les collecteurs prévoient une **clé API optionnelle**, un backoff et un rate-limit. Jamais de données inventées si une source échoue.

## 5. Dossier de travail

- `C:\Users\T480s\Desktop\SOAR project` — ** dépôt Git initialisé** (commit `f01003f`).
- Contenait uniquement `soar-ioc-key.pem` (clé privée RSA).
  - ⚠️ **Exclue du versionnement par `.gitignore` (vérifié via `git check-ignore`).**
  - Suggère un *key pair* EC2 AWS Academy ; aucune instance EC2 vérifiable depuis ici.

## 6. Composants manquants

| Composant | Statut |
|---|---|
| Docker + Compose | ✅ résolu (4.98.0) |
| Identité Git | ✅ résolue |
| Clés API gratuites (OTX, AbuseIPDB) | Facultatif — collecteurs conçus sans clé quand la source le permet |
| AWS Academy (services autorisés, crédits, EC2 existante) | ⏳ à vérifier en console, Phase 8, **sans créer de ressource** |

## 7. Risques identifiés

| Risque | Niveau | Mitigation |
|---|---|---|
| RAM : stack complète ≈ 10–12 Go | 🔴 | Profils Docker, jamais MISP + Wazuh + Suricata ensemble |
| URLhaus/abuse.ch exige une auth (401) | 🟠 | Clé optionnelle, repli sur sources sans clé, aucun repli fictif |
| Clé privée dans le dossier projet | 🟠 | `.gitignore` vérifié ; déplacement hors repo recommandé |
| `sudo` protégé / systemd *degraded* en WSL | 🟡 | Docker Desktop (choisi) évite ce chemin |
| Coûts AWS | 🔴 | **0 € tant que rien n'est créé** ; validation écrite obligatoire |
| Exposition PostgreSQL / secrets | 🔴 | Réseau Docker interne, `.env` ignoré, audit Phase 7 |
| Intégrité académique | 🔴 | IOC synthétiques marqués `is_synthetic`, résultats uniquement mesurés |

## 8. Décisions arrêtées

1. **Docker Desktop** (WSL2 backend) — validé par l'utilisateur.
2. **Python 3.11** comme cible backend (image `python:3.11-slim`).
3. **Documentation en français**, code et commentaires en anglais.
4. Identité Git : Souhayl Chouaibi <[masqué : e-mail]>.
5. Toutes les captures d'écran → `capture/`.
