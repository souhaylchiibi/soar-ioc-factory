# Guide d'utilisation — Console SOC (v0.2)

La console est l'interface des analystes SOC sur SOAR IOC Factory. Tout ce
qu'elle affiche provient de l'API FastAPI, donc de PostgreSQL (ou d'une sonde
en direct pour les intégrations). Aucune valeur n'est simulée ; une donnée
absente est affichée comme telle (« non mesurée », « non fournie »,
« Configuration manquante »).

- Local : http://127.0.0.1:5173/ (après `npm run dev`)
- AWS : http://127.0.0.1:8091/ (via le tunnel SSH, voir `OUVRIR_LE_PROJET.md`)

---

## 1. Connexion et rôles

La page `/login` demande un identifiant et un mot de passe. Après **5 échecs
consécutifs**, le compte est verrouillé **15 minutes** ; un poste qui multiplie
les tentatives reçoit « Trop de tentatives » (limite par adresse IP). Toutes
les connexions, réussies ou non, sont inscrites au journal d'audit avec l'IP.

| Rôle | Peut |
|---|---|
| **Lecteur** (`viewer`) | consulter toutes les pages |
| **Analyste** (`analyst`) | + lancer les opérations du pipeline, qualifier les détections, prendre une décision manuelle sur un IOC, générer un rapport |
| **Administrateur** (`admin`) | + créer des comptes, changer un rôle, désactiver un compte |

Les boutons d'action n'apparaissent que pour les rôles autorisés, et l'API
refuse de toute façon (HTTP 403) une action hors rôle. Un compte désactivé ou
rétrogradé perd ses droits **immédiatement**, même avec une session ouverte.

La session dure 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`) ; le jeton est
gardé dans l'onglet (fermé = déconnecté).

---

## 2. Navigation

- **Barre latérale** : trois groupes (Opérations, Pipeline IOC, Gouvernance).
  Le bouton *Replier* la réduit aux icônes (mémorisé). Sur mobile, elle
  s'ouvre avec le bouton ☰ en haut à gauche. L'état de l'API est affiché en bas.
- **Fil d'Ariane** : en haut à gauche, il situe la page courante.
- **Recherche globale** : `Ctrl K` (ou clic). Tapez au moins 2 caractères :
  IOC (type, statut, risque, LAB) et sources. `↑ ↓` pour choisir, `Entrée`
  pour ouvrir, `Échap` pour fermer. *Voir tous les résultats* ouvre Threat
  Intelligence filtré.
- **Notifications** (cloche) : échecs d'opérations, nouvelles détections et IOC
  à revoir sur 48 h — tous issus du journal et de la base. Le badge compte
  les éléments non lus ; *Tout marquer comme lu* est mémorisé sur le poste.
- **Profil** (initiales) : identité, rôle, dernière connexion, déconnexion.
- **Actualiser** : chaque page recharge ses données ; la plupart se mettent à
  jour seules (30 à 120 s) tant que l'onglet est visible.
- Les URL des vues filtrées (filtres, tri, page) sont **partageables**.

---

## 3. Pages

### SOC Overview (`/`)
- **Indicateurs** : IOC en base (dont synthétiques), publiés, en surveillance,
  rejetés, expirés/retirés, en attente de traitement (NEW → SCORED + à
  revoir), détections, score moyen, taux de déduplication, temps
  ingestion → score. Chaque tuile mène à la vue filtrée correspondante.
- **État des intégrations** : PostgreSQL, n8n, collecteurs, enrichissement,
  MISP, Suricata, Wazuh — sondés en direct (cache 30 s).
- **Activité du pipeline** (14 / 30 / 90 jours) : IOC créés, décisions
  (publiés / surveillés / rejetés) et détections par jour.
- **Niveaux de risque**, **types d'indicateurs**, **sources les plus
  productives**, **dernière exécution de chaque workflow**, **activité
  récente** (journal d'audit).

### Detection Center (`/detections`)
Alertes Suricata, Wazuh et manuelles rapprochées d'un IOC suivi. Filtres :
capteur, qualification, recherche (IOC ou règle). Le panneau de droite montre
l'IOC associé et **l'événement brut conservé comme preuve**.
- **Sévérité** : celle déclarée par le capteur (Suricata `alert.severity`,
  niveau de règle Wazuh). Si le capteur n'en fournit pas : « non fournie ».
- **Qualification** (analyste) : *Confirmer* ou *Faux positif*, avec note
  facultative et confirmation. Un faux positif incrémente le compteur de
  l'IOC, qui sera pénalisé au prochain calcul de score ; revenir sur la
  décision corrige le compteur.
- *Ingérer Suricata / Wazuh* lit les fichiers d'alertes montés en lecture
  seule. Si le fichier n'existe pas, l'API répond `no_file` sans rien créer.

### Threat Intelligence (`/threat-intel`)
Inventaire complet : recherche, filtres (statut, type, risque), *Masquer les
données de labo*, tri par colonne (indicateur, score, vu, expiration),
pagination par 50, export CSV de la page. Le marqueur **LAB** signale un IOC
du collecteur synthétique de laboratoire.

### Dossier d'un IOC (`/iocs/:id`)
En-tête : valeur (copiable), type, statut, score, risque, sources
indépendantes, détections. Onglets :
- **Score** : justification composante par composante, décision et règle
  appliquée, historique des scores, enrichissements (erreurs fournisseur
  incluses).
- **Cycle de vie** : chaque transition, son auteur, sa raison et sa preuve
  (« vérifié » pour les publications et retraits relus).
- **Provenance** : sources, groupe de provenance, fiabilité, première et
  dernière apparition, référence externe.
- **Détections**, **Publications** (cible, référence, vérifiée / révoquée),
  **Historique** (entrées d'audit liées).

*Décision analyste* (analyste) : seules les transitions autorisées par la
machine à états sont proposées ; une justification d'au moins 3 caractères
est obligatoire et l'opération est tracée sous votre identité.

### IOC Lifecycle (`/lifecycle`)
Les dix étapes (collecte → retrait vérifié) avec leur débit mesuré ; le
survol d'une étape indique la table qui prouve le chiffre. Répartition des
décisions. Onglets : transitions récentes, publiés, expirés, retirés.
Actions (analyste) : *Expirer les IOC échus*, *Retirer (vérifié)* — le
retrait relit chaque révocation et n'écrit `REMOVED` que si elle est
confirmée.

### Scoring & Risk (`/scoring`)
Décisions par type, distribution des scores (seuils 50 / 80), barème,
classement filtrable (risque, sans lab) et justification de l'IOC
sélectionné.

### Sources (`/sources`)
Catalogue : connexion réelle (*Connecté*, *Configuration manquante* si la clé
est absente, *Indisponible* si la dernière tentative a échoué), fiabilité,
IOC rattachés, collectes et échecs sur 30 jours. Panneau de détail : clé API
présente ou non, limite de débit, dernière erreur, historique des collectes.
Actions (analyste) : collecter une source ou toutes.

### Automation Center (`/automation`)
État de n8n (sonde `/healthz`), les 8 workflows (dernière exécution, durée,
opérations sur 7 jours) et l'historique paginé des exécutions avec leur
déclencheur (**n8n** ou **manuel**). La durée n'est affichée que si l'API l'a
mesurée (« non mesurée » pour les exécutions antérieures à la v0.2). Les
étapes exposées par l'API peuvent être lancées manuellement (analyste,
confirmation obligatoire).

### Audit Center (`/audit`)
Journal append-only (trigger PostgreSQL). Filtres : acteur (préfixe), action,
résultat. Cliquer une ligne déplie le détail JSON ; les objets IOC sont des
liens vers leur dossier.

### Rapports (`/reports`)
Rapport quotidien du workflow 8 pour la date choisie ; export JSON ; pour le
jour courant, *Générer maintenant* (analyste).

### System Health (`/system-health`)
Sondes `/health` et `/ready`, contrôles internes (connexion, révision
Alembic, trigger d'audit, sources, fraîcheur de l'activité), présence des clés
API (jamais leur valeur) et une carte détaillée par intégration.

### Utilisateurs (`/users`, administrateur)
Liste des comptes (rôle, état actif / verrouillé / désactivé, dernière
connexion), création avec politique de mot de passe, changement de rôle et
désactivation avec confirmation. Un administrateur ne peut ni se rétrograder
ni se désactiver, et le dernier administrateur actif est protégé.

---

## 4. Lire les états

| Affichage | Signification |
|---|---|
| Squelette gris animé | chargement en cours |
| Cadre rouge « Erreur lors du chargement » + HTTP | l'API a répondu une erreur : le message est celui de l'API |
| « API injoignable » | le service `soar-api` ne répond pas |
| « Accès refusé » (403) | votre rôle ne permet pas cette vue ou action |
| « Configuration manquante » | variable absente du `.env` : aucune connexion n'a été tentée |
| « Aucune donnée » | service configuré / monté mais rien à lire |
| « Indisponible » | la sonde ou la dernière tentative a échoué (message conservé) |
| « non mesurée », « non fournie », « non évalué » | la donnée n'existe pas : rien n'est estimé |
| **LAB** | donnée synthétique de laboratoire |

---

## 5. Accessibilité

Navigation complète au clavier (lien d'évitement « Aller au contenu », focus
visible, onglets aux flèches, dialogues natifs avec `Échap`), contrastes AA
sur fond sombre, risque et sévérité toujours écrits en toutes lettres (jamais
la couleur seule), animations désactivées si le système le demande
(`prefers-reduced-motion`).
