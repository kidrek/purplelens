# Guide de déploiement — Cockpit de Pilotage Purple Team

Ce guide décrit un déploiement de production **from scratch**. Il complète le `README.md`
(vue d'ensemble) et les runbooks d'exploitation (`exploitation.md`, `runbook-vault.md`).

Public visé : l'équipe qui installe et exploite la plateforme. Prérequis : Docker Engine
24+, Docker Compose v2, un nom de domaine, et un certificat TLS (ou l'auto-signé de dev).

---

## 1. Topologie et principe de moindre exposition

Un seul service publie des ports vers l'extérieur : le reverse proxy **`edge`** (nginx),
qui termine le TLS et route vers le frontend et le BFF. Tous les services de données
(PostgreSQL, MinIO, Vault, Redis, ClamAV, Keycloak) vivent sur un réseau Docker
**interne** sans port publié. Cet invariant est vérifié automatiquement
(`test_network_exposure.py`, cible `make config`) : un déploiement qui exposerait une base
de données échoue la recette.

```
Internet ──443──▶ edge (nginx, TLS) ──▶ frontend (SPA)
                                    └──▶ api (FastAPI/BFF) ──▶ postgres · minio · vault · redis · clamav
                                                          └──▶ keycloak (OIDC)
```

Conséquence : ne publiez jamais un port de base de données « pour déboguer ». Passez par
`docker compose exec` sur le réseau interne.

---

## 2. Secrets — à générer avant tout

Le fichier `.env` (copié depuis `.env.example`) porte la configuration. **Aucune valeur
`change-me-*` ne doit subsister en production.** Générez des secrets forts :

```bash
cp .env.example .env
# Clé de signature des jetons (≥ 32 octets) et mots de passe de service :
python -c "import secrets; print('JWT_SIGNING_KEY=' + secrets.token_urlsafe(48))"
for k in POSTGRES_SUPERPASSWORD APP_MIGRATOR_PASSWORD APP_API_PASSWORD \
         MINIO_ROOT_PASSWORD KC_ADMIN_PASSWORD OIDC_CLIENT_SECRET; do
  echo "$k=$(python -c 'import secrets;print(secrets.token_urlsafe(24))')"
done
```

Points d'attention :

- **`APP_MIGRATOR_PASSWORD` vs `APP_API_PASSWORD`.** Deux rôles SQL distincts. `app_migrator`
  est *owner* du schéma et n'est utilisé que par Alembic. `app_api` est le rôle de service,
  **`NOBYPASSRLS`** : c'est la clé de voûte du cloisonnement (couche 2). Ne les confondez jamais.
- **`JWT_SIGNING_KEY`.** Sa rotation invalide toutes les sessions actives — planifiez-la.
- **`VAULT_TOKEN`.** À restreindre à une politique *wrap/unwrap only* (cf. `runbook-vault.md`).
  Il ne doit pas pouvoir lire les clés en clair.
- **Ports exposés (`EDGE_HTTPS_PORT`, etc.).** Librement personnalisables : l'hôte public
  intégré dans les URL présignées de téléchargement (livrables/preuves) est dérivé de la
  requête entrante (en-tête `X-Forwarded-Host`, posé par nginx sur `/api/`), jamais figé
  dans une variable — rien à resynchroniser si vous changez un port. Seul
  `MINIO_PUBLIC_PATH_PREFIX` (défaut `/storage`) doit rester cohérent avec la
  `location` correspondante de `nginx.conf`.
- **`LOCAL_ACCOUNTS_ENABLED`.** Laissez `false` en production : l'authentification passe par
  l'IdP (Keycloak/OIDC). Les comptes locaux (mot de passe) ne servent qu'au dev et à la recette.

---

## 3. Ordre d'installation

L'ordre importe : les données avant l'application, les secrets avant les données chiffrées.

```bash
make bootstrap      # (1) démarre la stack + (2) init réseaux/buckets/realm/rôles SQL
                    #     + (3) migrate (alembic upgrade head) + (4) comptes de démo
make init-vault     # (5) init Vault, unseal, moteur transit, politique wrap/unwrap
make seed           # (6) référentiels + données de démonstration (optionnel en prod)
```

Détail des étapes clés :

1. **`make init`** crée les réseaux Docker, les buckets MinIO **avec Object Lock**
   (mode COMPLIANCE — le WORM ne peut pas être désactivé après coup), importe le realm
   Keycloak (`deploy/keycloak/realm-purple.json`) et crée les rôles SQL `app_migrator`/`app_api`.
2. **`make init-vault`** est **interactif** (descellement à seuil : 5 parts, 3 requises).
   Conservez les parts de descellement hors ligne, réparties entre plusieurs porteurs.
   Sans Vault descellé, aucune preuve ne peut être chiffrée ni lue.
3. **`make migrate`** applique le schéma sous `app_migrator`. À rejouer à chaque montée de version.

Vérifiez ensuite l'exposition réseau :

```bash
make config         # affiche la config résolue ET refuse si plus d'un service publie des ports
```

---

## 4. Configuration des intégrations externes

La plateforme s'appuie sur trois intégrations amont, toutes selon le même schéma :
**URL configurable + repli gracieux + cloisonnement**. Aucune n'est bloquante au démarrage.

### 4.1 Enrichissement des vulnérabilités (CIRCL Vulnerability-Lookup)

- `ENRICHMENT_BASE_URL` (défaut `https://vulnerability.circl.lu`), `ENRICHMENT_TIMEOUT_SECONDS`.
- Fournit CVSS (priorité 4.0 > 3.1 > 3.0 > 2.0), CWE, description, produits, CPE, et — quand
  la source les agrège — **EPSS et statut KEV**, dont on dérive la décision SSVC.
- Hors-ligne : l'enrichissement passe au statut « différé », l'application reste fonctionnelle.
  Un miroir interne peut être pointé via `ENRICHMENT_BASE_URL`.

### 4.2 Référentiels ATT&CK / D3FEND (MITRE)

- `ATTACK_STIX_URL`, `D3FEND_ONTOLOGY_URL`, `REFERENCE_SYNC_TIMEOUT_SECONDS` (défaut 90 s).
- La synchronisation en ligne récupère le catalogue **complet** (~700 techniques ATT&CK,
  ~270 D3FEND). Le bundle ATT&CK pèse ~50 Mo : préférez la **synchro initiale en CLI**
  (`python -m scripts.sync_reference`) plutôt qu'en requête web.
- Repli : si la source est injoignable, le socle embarqué (catalogue curé) est chargé et
  l'événement est journalisé (statut `fallback`). Pour un environnement air-gap, pointez les
  deux URLs vers un miroir interne.

### 4.3 Identité (Keycloak / OIDC)

- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`.
- Client *confidential* avec PKCE S256. L'IdP **authentifie** ; le produit **autorise**
  (la matrice RBAC est interne, jamais déléguée à l'IdP). Le realm de référence est fourni.

---

## 5. TLS et reverse proxy

En développement, `make tls` génère un certificat auto-signé. En production :

- Terminez le TLS sur `edge` (nginx) avec un certificat valide (Let's Encrypt ou PKI interne),
  déposé dans `deploy/nginx/tls/`.
- `MINIO_SECURE=false` est correct **si** le TLS est terminé au proxy amont ; MinIO reste en
  clair sur le réseau interne. Si MinIO doit servir en TLS direct, passez `MINIO_SECURE=true`.
- `EDGE_BIND_ADDRESS=127.0.0.1` si un pare-feu / load-balancer amont termine déjà le TLS.
- `EXPOSE_ADMIN_CONSOLES=false` : les consoles MinIO/Keycloak ne sont pas routées par défaut.

---

## 6. Vérification post-déploiement (smoke test)

```bash
make test-security     # familles de sécurité bloquantes (rapide) — à passer avant ouverture
curl -kfsS https://$PUBLIC_HOST/api/health   # le BFF répond
```

Contrôles manuels recommandés une fois la stack ouverte :

1. **Connexion** via l'IdP avec un compte de test, MFA exigée pour les rôles sensibles.
2. **Cloisonnement.** Un compte scopé sur un client ne voit que ce client (listes ET agrégats).
3. **Preuves.** Déposer une preuve → vérifier qu'elle transite par le sas (ClamAV), qu'elle est
   chiffrée (Vault descellé) et déposée en MinIO avec Object Lock.
4. **Journal.** `make verify-journal` (ou l'action d'admin) recalcule la chaîne : aucune rupture.
5. **Référentiels.** Lancer une synchro ATT&CK ; confirmer ~700 techniques et l'entrée au journal.

---

## 7. Montée de version

```bash
make down
git pull && docker compose build
make migrate        # applique les nouvelles migrations sous app_migrator
make up
make test-security  # re-vérifie les invariants avant réouverture
```

Les migrations sont additives et idempotentes ; sauvegardez avant (`make backup` — cf.
`exploitation.md`). En cas de rollback, restaurez le snapshot pg + MinIO + l'export scellé Vault.

---

## 8. Erreurs de déploiement fréquentes

| Symptôme | Cause probable | Correctif |
|---|---|---|
| `make config` échoue (ports) | un service de données publie un port | retirer le `ports:` — passer par le réseau interne |
| Aucune ligne visible en base | contexte applicatif non établi / `app_api` mal configuré | c'est le comportement *fail-closed* attendu ; l'accès passe par l'API |
| Preuve : échec de chiffrement | Vault scellé ou politique trop restrictive | desceller Vault (`runbook-vault.md`) ; vérifier la politique wrap/unwrap |
| Téléchargement de livrable cassé | `X-Forwarded-Host` non transmis par un proxy amont, ou `MINIO_PUBLIC_PATH_PREFIX` désaligné avec nginx.conf | vérifier que `/api/` transmet bien `X-Forwarded-Host` (voir nginx.conf) |
| Login `.local` renvoie 422 | validation d'e-mail trop stricte | déjà couvert par la recette e2e ; vérifier la version déployée |
| Sync ATT&CK toujours en `fallback` | sortie réseau bloquée vers GitHub | ouvrir la sortie ou pointer un miroir interne |
