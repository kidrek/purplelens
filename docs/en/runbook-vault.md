# Runbook — HashiCorp Vault (evidence KEKs)

🇫🇷 [Version française](../runbook-vault.md)

Vault holds the **master keys (KEK)**, one per client, via the *transit* engine. These
keys wrap the data keys (DEK) that encrypt the evidence. Vault is the system's
cryptographic boundary: compromising the database or the object storage is not enough
to read an item of evidence without the matching KEK.

This runbook covers the sensitive operations. All assume controlled access and, for
the most critical ones, an operator **quorum**.

## 1. Initialization and unsealing

At first initialization, Vault generates a root key split into *shares* (Shamir's
algorithm). Unsealing requires gathering a **threshold** of shares held by distinct
operators — no single person unseals Vault.

```bash
# Initialization (once): 5 shares, threshold of 3.
make init-vault        # wraps the flow below; keep the output offline
# equivalent to:
vault operator init -key-shares=5 -key-threshold=3
```

(`make unseal` only performs the **unsealing** — `vault operator unseal`, to run after
every restart; initialization and transit-engine activation go through
`make init-vault`.)

The shares and the *root token* must **never** be stored in the same place as the
database or the encrypted objects. Distribute the shares among operators; record their
custody in the security register.

After every Vault restart, it must be unsealed:

```bash
vault operator unseal   # repeated by 3 distinct operators (threshold reached)
```

While Vault is sealed, **no evidence can be deposited or read**: the ingestion sandbox
and downloads fail cleanly (and the denial is traced).

## 2. Enabling the transit engine and creating the KEKs

```bash
make init-vault         # enables transit + creates the KEK of every existing client
```

Internally, for a client with code `ACME`:

```bash
vault secrets enable transit                       # once
vault write -f transit/keys/kek-acme type=aes256-gcm96
```

KEK creation is idempotent. Every new client triggers the creation of its KEK at
provisioning time (or via `make init-vault`).

## 3. Rotating a KEK

Rotation creates a new version of the KEK without exposing the previous ones. Existing
DEKs are re-wrapped (*rewrap*) with the new version — the evidence is never decrypted
during the operation.

```bash
vault write -f transit/keys/kek-acme/rotate
# then re-wrap the client's active DEKs (dedicated application task)
```

Schedule it periodically and after any suspicion of compromise.

## 4. Crypto-shredding (controlled destruction)

Definitively deleting an item of evidence (retention expiry, contractual request) does
not mean erasing the encrypted object — impossible under WORM *Object Lock* — but
**destroying the DEK** that allows reading it. Without the DEK, the ciphertext is
noise.

- Retention expired: the (scheduled) `retention_sweep` task destroys the DEKs whose
  deadline has passed and marks `audit_dek.status = destroyed`.
- The journal keeps the trace of the destruction (sealed event), but **not** the key.

Destruction is **irreversible**: check the legal backup and the authorization before
any manual operation.

## 5. Backing up Vault

Back up Vault's state **separately** from the database and objects (never gather KEKs
and DEKs/data in the same place) and protect the medium at the highest classification
level of the hosted clients. The deployment uses the **file** storage backend
(`deploy/vault/` — no Raft cluster: `raft snapshot` does not apply); the backup
consists of archiving Vault's data volume with the service stopped or sealed:

```bash
docker compose stop vault
docker run --rm --volumes-from $(docker compose ps -aq vault) -v "$PWD/backups:/backup" \
  alpine tar czf /backup/vault-$(date -u +%Y%m%dT%H%M%SZ).tar.gz /vault/file
docker compose start vault   # then unseal (make unseal)
```

This backup is **deliberately separate** from `make backup` (database + objects) — the
manifest of `scripts/backup.sh` reminds you: never gather the KEKs and the encrypted
data in the same place. The copied data remains sealed (encrypted by Vault).

Restoring the data (database + objects) without the matching Vault backup is
**unusable by design**. That is the very guarantee of crypto-shredding.

## 6. In case of incident

1. Seal Vault if compromise is suspected: `vault operator seal` (cuts all access to
   evidence immediately).
2. Rotate the affected KEKs after remediation (section 3).
3. Verify journal integrity (`/api/journal/verify` or `make test-security`).
4. Record the incident; keep the `evidence_access` traces (accesses and denials).
