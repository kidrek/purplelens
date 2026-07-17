# Guide utilisateur — Cockpit Purple Team

Ce guide présente les parcours principaux selon votre rôle. L'interface est bilingue
(FR/EN, bascule dans la barre supérieure) et propose deux thèmes conformes à la
direction artistique : **A** (clair, violet) et **B** (SOC sombre) — bascule à côté
de la langue. À droite de la barre supérieure, une **pastille de compte** affiche votre
nom (et un badge **MFA** tant que l'authentification à deux facteurs n'est pas enrôlée) ;
un clic ouvre « Mon compte ».

## Connexion

Deux modes coexistent :

- **SSO (recommandé)** : « Connexion via l'organisation » redirige vers le fournisseur
  d'identité (Keycloak, OIDC + PKCE). Après authentification, le produit détermine votre
  rôle et votre périmètre — l'identité ne porte pas le rôle.
- **Repli local** : e-mail + mot de passe + code TOTP, pour les comptes de service ou
  les situations de secours.

Les rôles opérationnels exigent le MFA. Certaines actions sensibles demandent une
**ré-authentification récente** (step-up) : l'interface vous invite alors à saisir un
nouveau code TOTP.

**Continuité de session** : tant que vous travaillez, votre session est **renouvelée
silencieusement** — vous n'êtes pas redéconnecté toutes les quelques minutes. Une
nouvelle authentification n'est demandée qu'après une **inactivité prolongée** ou si la
session est révoquée (compte désactivé, rotation des clés).

## Rôles

| Rôle       | Vocation principale |
|------------|---------------------|
| `admin`    | Administration, gestion des comptes, CRUD large (jamais le journal ni les clés) |
| `manager`  | Pilotage et validation ; lecture seule sur Ressources/Applications/Actions (D6) |
| `ciso`     | Validation des vulnérabilités et tickets, vision de son périmètre |
| `auditeur` | Conduite des audits, dépôt des preuves |
| `voc`      | Gestion des vulnérabilités (Vulnerability Operations) |
| `cert`     | Détection : observations, tickets de détection, scénarios |
| `operateur`| Prestataire multi-clients « super-utilisateur métier » : CRUD complet sur inventaire, scénarios et livrables, validation de ses audits/vulnérabilités/tickets — cloisonné à sa liste de clients |

Ce que vous voyez et pouvez faire est **décidé par le serveur**. Un bouton absent ou
grisé traduit un droit non accordé : l'interface reflète la décision, elle ne l'invente
pas et ne la contourne pas.

## Cockpit

Écran d'accueil : compteurs de haut niveau (audits, exercices, vulnérabilités, preuves)
limités à votre périmètre. Les rôles multi-clients voient l'agrégat de leurs clients.

## Parcours métier

- **Organisations** : clients et prestataires, secteur, référent, TLP par défaut.
- **Audits** : engagements (référence auto `AUD-AAAA-NNN`), catégorie, type de test,
  jalons, statut, priorité.
- **Exercices Purple** : sessions d'émulation, équipes, *runs*, verdicts par étape
  d'attaque (prévenu / alerté / journalisé / sans télémétrie / non testé).
- **Vulnérabilités** : CVE/CWE, score CVSS, niveau et échéance de SLA calculés
  automatiquement, validation par le CISO/Manager.
- **Scénarios** : bibliothèque transverse de menaces (acteurs émulés, techniques
  ATT&CK, crédibilité) — partagée, hors cloisonnement client.

## Matrice ATT&CK

La page **Matrice ATT&CK** présente la couverture sous forme de tableau : les **tactiques**
en colonnes (avec un compteur *couvertes / total*), les **techniques** en cartes teintées
selon leur **statut de couverture**. Un sélecteur de **couches** change la lecture des
couleurs :

- **Couverture** : nature de la couverture / meilleur verdict défensif ;
- **Détection** : technique détectée (réponse défensive) vs **écart** (jouée, non détectée) ;
- **Écart** : met en évidence les seuls écarts de détection ;
- **Importée** : surligne les techniques d'une couche **ATT&CK Navigator** importée (`.json`).

Chaque carte peut porter des **badges d'activité** (étapes offensives, vulnérabilités,
tickets, scénarios liés) et se **déplie** pour afficher ses sous-techniques.

![Matrice ATT&CK — couverture par tactique](img/attack-matrix.png)

## Preuves (coffre-fort)

Le coffre affiche les preuves de votre périmètre avec leur **état de scellement** et leur
marquage **TLP**. Points essentiels :

- Les fichiers **ne transitent jamais par l'application**. Le dépôt et le téléchargement
  se font par **URL présignée à durée courte**, délivrée par le serveur après un triple
  contrôle (droits, cloisonnement, TLP/PAP).
- Une preuve déposée passe par un **sas** : mise en quarantaine, analyse antivirus,
  vérification du type réel du fichier, chiffrement enveloppe, dépôt en stockage WORM,
  puis scellement dans le journal. La barre de progression reflète ces étapes.
- Le téléchargement n'est possible qu'une fois la preuve **stockée** (sas réussi).
- Toute consultation — **y compris les refus** — est tracée. Vous ne verrez jamais le
  contenu d'une preuve dont le marquage est incompatible avec votre contexte.

## Journal

Consultable par tous en **lecture seule** (personne ne peut le modifier, pas même
l'administrateur). Le bouton « Vérifier l'intégrité de la chaîne » demande au serveur de
recalculer le chaînage par hachage et signale toute rupture.

## Livrables

Lettres d'engagement, NDA et rapports (format PTES) sont générés en PDF avec un
**bandeau de classification TLP** et déposés en stockage verrouillé. Les éléments
marqués comme secrets sont masqués dans les rendus selon votre contexte.

## Bonnes pratiques

- Renouvelez votre code TOTP quand l'interface le demande (step-up) : c'est le signe
  d'une action à fort impact.
- Respectez le marquage TLP/PAP : il conditionne la diffusion et le rendu.
- En cas de refus inattendu, c'est une décision serveur : rapprochez-vous de votre
  administrateur si le droit vous semble manquant.
