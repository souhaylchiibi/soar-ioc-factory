# Design system — SOAR IOC Factory Console

Direction établie avec la skill **ui-ux-pro-max** (recherche `--design-system`,
densité 8 / mouvement 3 / variance 3) puis adaptée au brief :

- 1re proposition de la skill : style « Cyberpunk UI » (vert matrice, néons,
  glitch) — **écartée** : le brief exclut couleurs fluorescentes et effets
  lumineux.
- 2e recherche (« enterprise security operations analytics minimal ») :
  **Minimalism & Swiss Style**, recommandé pour dashboards d'entreprise —
  **retenu** pour la structure, la typographie et les règles d'accessibilité.
- La palette proposée (bleu/ambre sur fond clair) ne convenait pas au mode
  sombre exigé : palette **graphite + sarcelle** définie pour le projet.

Source de vérité des valeurs : `frontend/src/index.css` (`@theme`).

## Principes

1. **La donnée d'abord** : chiffres blancs, tabulaires ; la couleur porte un
   sens (risque, statut, santé), jamais la décoration.
2. **Élévation par la luminosité**, pas par les ombres : `bg` < `surface` <
   `surface-2` < `surface-3`.
3. **Un seul accent d'identité** (sarcelle) pour l'état actif, le focus et
   l'action principale.
4. **Honnêteté visuelle** : toute absence de donnée a un libellé explicite.
5. **Densité maîtrisée** : 13–14 px pour les tableaux, 8–24 px d'espacement,
   grille de cartes 12–16 px de gouttière.

## Couleurs

| Rôle | Jeton | Valeur |
|---|---|---|
| Fond | `--color-bg` | `#0b0f14` |
| Surface | `--color-surface` | `#10151c` |
| Surface surélevée | `--color-surface-2` / `-3` | `#151b24` / `#1b2330` |
| Bordures | `--color-line` / `-strong` | `#222b38` / `#2e3948` |
| Texte | `--color-fg` | `#e7ecf2` |
| Texte secondaire | `--color-fg-muted` | `#9aa6b6` (≥ 4,5:1 sur toutes les surfaces) |
| Texte tertiaire | `--color-fg-subtle` | `#7a8698` (libellés, méta) |
| Accent identité | `--color-accent` | `#2cc2a6` |
| Succès / alerte / danger / info | `ok` `warn` `danger` `info` | `#4cc38a` `#e0a43b` `#f0605d` `#5aa2f5` |
| Risque critique → faible | `risk-critical/high/medium/low` | `#f0605d` `#ee8a3c` `#e0b33b` `#7d8ba0` |

Types d'IOC (graphiques catégoriels) : IP `#5aa2f5`, domaine `#2cc2a6`,
URL `#a48af5`, MD5 `#e0a43b`, SHA-1 `#ee7aa8`, SHA-256 `#7fc8e8`.

## Typographie

- **Inter Variable** (interface) et **JetBrains Mono Variable** (valeurs
  d'IOC, identifiants, JSON) — embarquées via `@fontsource`, aucun CDN.
- Corps 14 px / 1,5 ; tableaux 12,5–13 px ; titres de page 20 px / 600 ;
  KPI 26 px / 600 ; libellés de section 11 px capitales espacées.
- Chiffres tabulaires (`tnum`) partout où l'on compare des nombres.

## Composants (`frontend/src/components`)

| Composant | Rôle |
|---|---|
| `layout/AppShell`, `Sidebar`, `Topbar`, `GlobalSearch` | coque : barre latérale rétractable (tiroir mobile), fil d'Ariane, recherche `Ctrl K`, notifications, profil |
| `ui/Card`, `Kpi`, `PageHeader` | surfaces, tuiles KPI à barre sémantique, en-tête avec fraîcheur des données |
| `ui/Badge` | statut, risque, sévérité, type, connexion, LAB |
| `ui/Table` | tableau à en-tête collant, tri accessible (`aria-sort`), pagination |
| `ui/Controls` | champs étiquetés, sélecteurs, interrupteur, onglets clavier, popover |
| `ui/States` | squelettes (sans décalage de mise en page), état vide, erreur explicite |
| `ui/Feedback` | toasts (`aria-live`), dialogue de confirmation natif `<dialog>` |
| `charts/Charts` | chronologie, anneau, histogramme, barres HTML, courbe de score |
| `domain/*` | pipeline 10 étapes, justification du score, intégrations, flux d'audit, bouton d'opération |

## Mouvement

Apparition des cartes 180 ms (opacité + 4 px), transitions de survol
150–200 ms, rotation de l'icône d'actualisation pendant le chargement. Aucun
effet en boucle hormis le squelette. `prefers-reduced-motion` neutralise tout.

## Accessibilité (contrôlée)

Lien d'évitement, focus visible 2 px sarcelle, `aria-label` sur tous les
boutons-icônes, landmark `nav` étiqueté, onglets ARIA aux flèches, tableaux
avec `scope` et `caption`, graphiques avec `role="img"` + description
textuelle, risque et sévérité toujours écrits (jamais la couleur seule),
cibles ≥ 36 px sur bureau.
