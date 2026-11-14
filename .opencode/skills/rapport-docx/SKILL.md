---
name: Rapport Word (DOCX)
description: Générer ou modifier un rapport Word soigné (page de garde, sommaire, en-têtes, numéros de page, tableaux légendés, figures) avec python-docx — notamment pour le rapport de projet SOAR IOC Factory.
---

# Rapport Word

Savoir-faire de mise en forme et de production de documents `.docx` pour ce dépôt.
La capacité technique vient de `python-docx` ; ce skill fixe les conventions.

## Environnement

- Interpréteur : `backend\.venv\Scripts\python.exe` (`python` n'est pas dans le PATH).
- Bibliothèque : `python-docx` 1.1.2, déjà installée (`backend/requirements-dev.txt`).
- Générateur existant à réutiliser : `scripts/generate_report.py` (styles, `image()`,
  `figure()`, tableaux, sections 1–15). Générateur final : `scripts/build_final_report.py`.

## Règles de contenu (non négociables)

1. **Aucun chiffre inventé.** Toute valeur vient de `reports/evaluation/metrics.json`,
   de l'API (`http://127.0.0.1:8000/api/v1`) ou de `git`.
2. **Distinguer explicitement** mesuré / hypothèse / non mesurable. Le modèle manuel
   (17 min/IOC) est une **hypothèse**, jamais une mesure historique.
3. Ne jamais lire `.env`, `*.pem`, ni recopier une clé ou un jeton.
4. Ne pas écraser un livrable déjà remis : écrire dans un nouveau fichier.
5. Si une donnée manque, écrire « non mesuré » et expliquer pourquoi.

## Mise en forme imposée

- A4, marges 2 cm, Calibri 10,5 pt, titres bleu `#0E5A8A`.
- Page de garde, sommaire (champ `TOC`), en-tête, pied « Page X sur Y ».
- Tableaux et figures numérotés, légende + source sous chaque tableau.
- Captures : `capture/*.jpg` · graphiques : `reports/figures/eval_*.png`.
- Champs Word : `w:updateFields` à `true` pour que le sommaire se mette à jour.

## Vérification avant de livrer

```powershell
.\backend\.venv\Scripts\python.exe -c "from docx import Document; d=Document('reports/RAPPORT_FINAL.docx'); print(len(d.paragraphs), len(d.inline_shapes))"
```

- Poids > 1 Mo, aucune occurrence de « None », « TODO » ou « indisponible » injustifié.
- Ouvrir le fichier : F9 sur le sommaire si les numéros de page manquent.
