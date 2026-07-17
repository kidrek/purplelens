# Captures d'écran

Images référencées par le [README](../../README.md) (section « Visite guidée ») et le
[guide utilisateur](../guide-utilisateur.md). Captures en **thème SOC sombre**,
1600×900 @2x, prises sur le jeu de démonstration.

| Fichier | Écran | Groupe |
|---|---|---|
| `login.png` | Connexion `/login` — SSO OIDC + repli local TOTP | Connexion & compte |
| `account.png` | Mon compte `/account` — enrôlement TOTP, fiche auditeur | Connexion & compte |
| `cockpit.png` | Cockpit `/` — KPIs, couverture par tactique, posture | Pilotage |
| `exercices.png` | Exercices Purple `/exercices` — boucle Red→Blue→Détection | Pilotage |
| `audit-drawer.png` | Fiche d'audit (drawer sur `/audits`) — PTES, scénario CTI, TTPs | Pilotage |
| `vulnerabilities.png` | Vulnérabilités `/vulnerabilities` — sévérité, CVSS, SLA | Pilotage |
| `vuln-drawer.png` | Fiche vulnérabilité (drawer) — OWASP/CWE, enrichissement CIRCL | Pilotage |
| `tickets.png` | Tickets de détection `/tickets` — ATT&CK, D3FEND, Sigma | Pilotage |
| `ticket-drawer.png` | Fiche ticket (drawer) — technique, contre-mesure, statut | Pilotage |
| `attack-matrix.png` | Matrice ATT&CK `/attack-matrix` — couverture par tactique | Connaissance |
| `scenarios.png` | Scénarios `/scenarios` — CTI, émulation, STIX 2.1 | Connaissance |
| `scenario-drawer.png` | Fiche scénario (drawer) — FIN7, TTPs, couverture, D3FEND | Connaissance |
| `organisations.png` | Organisations `/organisations` — clients, cloisonnement | Connaissance |
| `organisation-drawer.png` | Fiche organisation (drawer) — référent, TLP, rattachements | Connaissance |
| `applications.png` | Applications `/applications` — inventaire testé | Connaissance |
| `application-drawer.png` | Fiche application (drawer) — criticité, liens audits/vulns | Connaissance |
| `ressources.png` | Ressources `/ressources` — auditeurs et moyens | Connaissance |
| `deliverables.png` | Livrables `/deliverables` — générateur PDF + bandeau TLP | Livrables & traçabilité |
| `deliverable-drawer.png` | Fiche livrable (drawer) — type, TLP, téléchargement tracé | Livrables & traçabilité |
| `evidence.png` | Coffre de preuves `/evidence` — sas, WORM, TLP | Livrables & traçabilité |
| `journal.png` | Journal `/journal` — chaîne de hachage inviolable | Livrables & traçabilité |
| `bibliotheque.png` | Bibliothèque `/bibliotheque` — corpus méthodologique | Système |
| `bibliotheque-article.png` | Article corpus (drawer) — processus pas à pas, ISO 27002 | Système |
| `parametres.png` | Référentiels `/parametres` — ATT&CK, D3FEND, OWASP, CWE… | Système |
| `admin.png` | Administration `/admin` — comptes, rôles, périmètres | Système |

Régénération : pile lancée (`make up`, front reconstruit), puis exécuter le script de
capture Playwright dans le conteneur `pdf-renderer` (connexion avec un compte de démo —
`operateur` pour la plupart des pages, `admin` pour `/admin` ; `/login` se capture hors
session), navigation sur les routes ci-dessus, `page.screenshot`. Pour les fiches (drawers) :
cliquer la ligne (`tr.row-clickable`), le bouton « Voir » (livrables) ou l'article
(`button.corp-row`) avant la capture.
