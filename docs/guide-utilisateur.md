# Guide utilisateur — Cockpit Purple Team

🇬🇧 [English version](en/user-guide.md)

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
| `admin`    | Administration, gestion des comptes, CRUD large (journal en **lecture seule**, jamais les clés de chiffrement) |
| `manager`  | Pilotage et validation ; lecture seule sur Ressources/Applications/Actions (D6) |
| `ciso`     | Validation des vulnérabilités et tickets, vision de son périmètre |
| `auditeur` | Conduite des audits, dépôt des preuves |
| `voc`      | Gestion des vulnérabilités (Vulnerability Operations) |
| `cert`     | Détection : observations, tickets de détection, scénarios |
| `operateur`| Prestataire multi-clients « super-utilisateur métier » : CRUD complet sur inventaire, scénarios et livrables, validation de ses audits/vulnérabilités/tickets — cloisonné à sa liste de clients |

Ce que vous voyez et pouvez faire est **décidé par le serveur**. Un bouton absent ou
grisé traduit un droit non accordé : l'interface reflète la décision, elle ne l'invente
pas et ne la contourne pas. Le **menu latéral lui-même s'adapte** : les entrées dont le
serveur ne vous accorde pas la lecture (par exemple le Journal pour les rôles non
transverses) n'apparaissent pas.

**Astuce navigation** : la **palette de commandes** (⌘K / Ctrl-K) donne accès en
recherche libre aux vues et aux articles de la bibliothèque méthodologique.

## Cockpit

Écran d'accueil : taux de détection, angles morts, dépassements de SLA P1, posture par
tactique (bande kill-chain), tendance, derniers événements — limités à votre périmètre.
Les rôles multi-clients voient l'agrégat de leurs clients ; le **sélecteur de périmètre**
de la barre supérieure restreint l'affichage (jamais ne l'élargit). La plupart des vues
de liste portent en outre leur propre **bandeau de KPI** calculé côté serveur avec les
mêmes filtres que le tableau.

## Parcours métier

- **Organisations** : clients et prestataires, secteur (taxonomie **NACE Rév. 2**),
  référent, TLP par défaut.
- **Applications** : inventaire applicatif (criticité, exposition, valeur métier) avec
  posture consolidée — vulnérabilités liées, couverture d'audit ; le panneau latéral
  d'une application est un mini-cockpit dédié.
- **Ressources** : intervenants humains (rôle auditeur/SOC/CISO…, compétences) —
  sélectionnables comme auditeurs sur les audits.
- **Audits** : engagements (référence auto `TYPE_AAAAMM-NN_CLIENT_APP`, ex.
  `PEN_202602-01_ACME_PORTAIL`), catégorie, type de test, jalons PTES, statut, priorité.
  Le **bloc engagement** (objectifs, périmètre, règles, contacts, clauses NDA — 18
  rubriques) est **pré-rempli à la création** et alimente la lettre d'engagement. Lier un
  **scénario CTI** à l'audit **dérive automatiquement les actions PTES** (une action par
  étape du scénario, dédoublonnée par technique).
- **Exercices Purple** : sessions d'émulation rattachées à un audit, équipes, *runs*
  successifs, verdicts par étape d'attaque (prévenu / alerté / journalisé / sans
  télémétrie / non testé), délais de détection (MTTD) et de réaction (MTTR) calculés à
  partir des horodatages saisis. La vue groupe les runs par audit et le panneau montre la
  progression de la détection d'un run à l'autre.
- **Vulnérabilités** : CVE/CWE, score CVSS, niveau et échéance de SLA calculés
  automatiquement, contre-mesures **D3FEND dérivées des techniques ATT&CK**, validation
  par le CISO/Manager ; enrichissement CIRCL à la demande (EPSS, KEV, SSVC).
- **Tickets de détection** : issus des **angles morts** d'un exercice (étape sans
  télémétrie) — un ticket ne se crée que depuis une étape d'attaque source ; référence
  auto `TICK_AAAAMM-NN_CLIENT_APP_TECHNIQUE`, mesure D3FEND associée, règle Sigma
  éventuelle, cycle ouvert → en cours → traité → clos avec validation. Un ticket clos
  fait passer la technique correspondante à l'état « couvert ».
- **Scénarios** : bibliothèque transverse de menaces (acteurs émulés, techniques
  ATT&CK, crédibilité échelle Admiralty, export/import STIX 2.1) — partagée, hors
  cloisonnement client. Le champ « acteur émulé » s'appuie sur les **catalogues
  d'acteurs** (groupes ATT&CK + MISP Galaxy) : sélectionnez un acteur puis **importez ses
  TTPs** comme étapes du scénario.

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

- Le **dépôt** ne transite jamais par l'application : il se fait par **URL présignée à
  durée courte**, délivrée par le serveur après un triple contrôle (droits,
  cloisonnement, TLP/PAP). Le **téléchargement déchiffré** est la seule exception
  documentée : seuls les serveurs détiennent la clé, le fichier en clair est donc servi
  par l'API, sous contrôle d'accès renforcé (step-up récent exigé pour le TLP:RED) et
  trace systématique — les preuves marquées « secrets » ne sont jamais servies en clair.
- Une preuve déposée passe par un **sas** : mise en quarantaine, analyse antivirus,
  vérification du type réel du fichier, chiffrement enveloppe, dépôt en stockage WORM,
  puis scellement dans le journal. La barre de progression reflète ces étapes.
- Le téléchargement n'est possible qu'une fois la preuve **stockée** (sas réussi).
- Toute consultation — **y compris les refus** — est tracée. Vous ne verrez jamais le
  contenu d'une preuve dont le marquage est incompatible avec votre contexte.

## Journal

Réservé aux rôles transverses (`admin`, `manager`, `ciso`), en **lecture seule** —
personne ne peut le modifier, pas même l'administrateur ; les rôles cloisonnés n'y voient
que les événements de leur périmètre. La vue offre des **filtres serveur** (recherche
libre, domaine d'événement, résultat ok/refusé, acteur, plage de dates), un panneau de
**statistiques**, et un **export JSON** (step-up exigé). Le bouton « Vérifier l'intégrité
de la chaîne » demande au serveur de recalculer le chaînage par hachage et signale toute
rupture ; en arrière-plan, la tête de chaîne est en outre **ancrée en stockage WORM**
toutes les 6 heures.

## Livrables

Quatre types sont générés en PDF : **lettre d'engagement**, **NDA**, **rapport PTES** et
**rapport d'exercice Purple** (tous les runs d'un audit : chronologie des étapes,
verdicts, couverture par tactique). Gabarits bilingues FR/EN, **bandeau de
classification TLP**, registre des preuves avec aperçus intégrés, dépôt en stockage
verrouillé. Les éléments marqués comme secrets sont masqués dans les rendus.

## Bibliothèque

Corpus méthodologique bilingue (procédures, processus, fiches métier), filtrable par
profil, consultable depuis le menu **Bibliothèque** ou via la palette ⌘K. Les articles
s'ouvrent dans un panneau latéral partout dans l'application (liens profonds `?open=`).

## Paramètres

État des **catalogues de référence** (ATT&CK multi-domaines Enterprise/Mobile/ICS,
D3FEND, OWASP, CWE, CAPEC, groupes ATT&CK, acteurs MISP) avec import hors-ligne et
**synchronisation en ligne** (« Tout synchroniser », réservé aux administrateurs).

## Administration

Gestion des comptes (création, changement de rôle, désactivation) — chaque action est
**à haut risque** : un code TOTP de step-up est demandé à la volée. Les rôles et leurs
droits sont figés dans la matrice serveur, jamais configurables à chaud.

## Mon compte — « Ma fiche »

La page **Mon compte** permet d'enrôler le MFA (TOTP) et de tenir sa **fiche auditeur**
(« Ma fiche ») : une fiche ressource liée à votre compte, par organisation de votre
périmètre. Une fois créée, vous devenez sélectionnable comme auditeur d'un audit — sans
attendre qu'un gestionnaire crée la fiche pour vous.

## Bonnes pratiques

- Renouvelez votre code TOTP quand l'interface le demande (step-up) : c'est le signe
  d'une action à fort impact.
- Respectez le marquage TLP/PAP : il conditionne la diffusion et le rendu.
- En cas de refus inattendu, c'est une décision serveur : rapprochez-vous de votre
  administrateur si le droit vous semble manquant.
