# Runbook — HashiCorp Vault (KEK des preuves)

Vault détient les **clés maîtres (KEK)**, une par client, via le moteur *transit*.
Ces clés enveloppent les clés de données (DEK) qui chiffrent les preuves. Vault est
la frontière cryptographique du système : la compromission de la base ou du stockage
d'objets ne suffit pas à lire une preuve sans la KEK correspondante.

Ce runbook couvre les opérations sensibles. Toutes supposent un accès contrôlé et,
pour les plus critiques, un **quorum** d'opérateurs.

## 1. Initialisation et descellement (unseal)

À la première initialisation, Vault génère une clé racine scindée en *parts*
(algorithme de Shamir). Le descellement exige de réunir un **seuil** de parts détenues
par des opérateurs distincts — aucune personne seule ne descelle Vault.

```bash
# Initialisation (une seule fois) : 5 parts, seuil de 3.
make unseal            # enveloppe le flux ci-dessous ; sortie à conserver hors-ligne
# équivaut à :
vault operator init -key-shares=5 -key-threshold=3
```

Les parts et le jeton racine (*root token*) **ne doivent jamais** être stockés au même
endroit que la base ou les objets chiffrés. Répartir les parts entre opérateurs ;
consigner leur détention dans le registre de sécurité.

À chaque redémarrage de Vault, il faut le desceller :

```bash
vault operator unseal   # à répéter par 3 opérateurs distincts (seuil atteint)
```

Tant que Vault est scellé, **aucune preuve ne peut être déposée ni lue** : le sas
d'ingestion et les téléchargements échouent proprement (et le refus est tracé).

## 2. Activation du moteur transit et création des KEK

```bash
make init-vault         # active transit + crée la KEK de chaque client existant
```

En interne, pour un client de code `ACME` :

```bash
vault secrets enable transit                       # une fois
vault write -f transit/keys/kek-acme type=aes256-gcm96
```

La création d'une KEK est idempotente. Chaque nouveau client déclenche la création de
sa KEK au provisionnement (ou via `make init-vault`).

## 3. Rotation d'une KEK

La rotation crée une nouvelle version de la KEK sans exposer les précédentes. Les DEK
existantes sont ré-enveloppées (*rewrap*) avec la nouvelle version — les preuves ne
sont jamais déchiffrées pendant l'opération.

```bash
vault write -f transit/keys/kek-acme/rotate
# puis re-enveloppement des DEK actives du client (tâche applicative dédiée)
```

À planifier périodiquement et après tout soupçon de compromission.

## 4. Crypto-shredding (destruction contrôlée)

La suppression définitive d'une preuve (fin de rétention, demande contractuelle) ne
consiste pas à effacer l'objet chiffré — impossible sous *Object Lock* WORM — mais à
**détruire la DEK** qui permet de le lire. Sans DEK, le ciphertext est du bruit.

- Rétention échue : la tâche `retention_sweep` (planifiée) détruit les DEK dont
  l'échéance est dépassée et marque `audit_dek.status = destroyed`.
- Le journal conserve la trace de la destruction (événement scellé), mais **pas** la clé.

La destruction est **irréversible** : vérifier la sauvegarde légale et l'autorisation
avant toute opération manuelle.

## 5. Sauvegarde de Vault

Sauvegarder l'état de Vault **séparément** de la base et des objets (ne jamais réunir
KEK et DEK/données au même endroit). Suivre la procédure officielle de *snapshot* et
protéger le média au niveau de classification le plus élevé des clients hébergés.

```bash
vault operator raft snapshot save vault-$(date -u +%Y%m%dT%H%M%SZ).snap
```

Une restauration des données (base + objets) sans la sauvegarde Vault correspondante est
**inexploitable par conception**. C'est la garantie même du crypto-shredding.

## 6. En cas d'incident

1. Sceller Vault si compromission suspectée : `vault operator seal` (coupe tout accès
   aux preuves immédiatement).
2. Faire tourner les KEK concernées après remédiation (section 3).
3. Vérifier l'intégrité du journal (`/api/journal/verify` ou `make test-security`).
4. Consigner l'incident ; conserver les traces `evidence_access` (consultations et refus).
