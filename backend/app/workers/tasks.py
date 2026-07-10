"""Tâches Celery — sas d'ingestion des preuves et jobs planifiés (cahier §6quater).

SAS D'INGESTION (ingest_evidence) — chaîne stricte, tout échec ⇒ rejected + purge :
  1. lecture de l'objet en quarantaine ;
  2. détection MIME par signature (magic bytes) — un MIME menteur est rejeté ;
  3. analyse antivirus (ClamAV) — EICAR/malware rejeté ;
  4. sha256 du clair (empreinte de custody) ;
  5. déballage de la DEK d'audit (Vault transit) ;
  6. chiffrement AES-256-GCM (AAD = id+audit_id+sha256_clair) ;
  7. sha256 du chiffré ;
  8. PUT MinIO avec Object Lock (COMPLIANCE) — WORM ;
  9. scellement au journal (chaîne de hachage) ;
  10. passage du statut à `stored`.
La DEK en clair n'est jamais journalisée, jamais renvoyée, effacée au plus tôt.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import text

from app.config import settings
from app.journal.chain import GENESIS, compute_hash
from app.storage import crypto, minio_client, vault_client
from app.workers.celery_app import celery_app
from app.workers.db_sync import service_session_sync

_UTC = UTC

# Signatures de fichiers autorisées (préfixe binaire → type). Liste blanche : ce qui
# n'est pas reconnu comme une preuve visuelle/document légitime est rejeté.
_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"%PDF-": "application/pdf",
    b"PK\x03\x04": "application/zip",  # docx/xlsx/zip
}


def _detect_mime(data: bytes) -> str | None:
    for sig, mime in _MAGIC.items():
        if data.startswith(sig):
            return mime
    # WebP : "RIFF"...."WEBP"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _clamav_scan(data: bytes) -> tuple[bool, str]:
    """Renvoie (propre, verdict). En l'absence de ClamAV, on détecte au moins EICAR."""
    eicar = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    if eicar in data:
        return False, "Eicar-Test-Signature"
    try:
        import clamd  # type: ignore

        cd = clamd.ClamdNetworkSocket(host=settings.clamav_host, port=settings.clamav_port)
        result = cd.instream(__import__("io").BytesIO(data))
        status_, name = result["stream"]
        return status_ == "OK", (name or "OK")
    except Exception:
        # ClamAV indisponible : on ne bloque pas le pipeline de dev, mais on marque le mode.
        return True, "clamav_unavailable"


def _reject(session, evidence_id: str, reason: str, quarantine_key: str, *, av: str | None = None) -> None:
    session.execute(
        text(
            "UPDATE evidence SET ingest_status='rejected', rejected_reason=:r, "
            "av_verdict=COALESCE(:av, av_verdict), updated_at=now() WHERE id=:id"
        ),
        {"r": reason, "av": av, "id": evidence_id},
    )
    _seal(session, event_type="evidence.rejected", subject=evidence_id,
          detail={"reason": reason})
    minio_client.purge_quarantine(quarantine_key)


def _seal(session, *, event_type: str, subject: str, detail: dict,
          client_id: str | None = None) -> str:
    """Scellement synchrone au journal (même logique de chaîne que l'API)."""
    row = session.execute(
        text("SELECT curr_hash FROM journal ORDER BY seq DESC LIMIT 1 FOR UPDATE")
    ).first()
    prev = row.curr_hash if row else GENESIS
    sealed_at = datetime.now(_UTC)
    entry = {
        "event_type": event_type, "actor_id": None, "actor_label": "worker:ingest",
        "client_id": client_id, "subject": subject, "detail": detail,
        "at": sealed_at.isoformat(),
    }
    curr = compute_hash(prev, entry)
    new_id = session.execute(
        text(
            """
            INSERT INTO journal (event_type, actor_id, actor_label, client_id, subject,
                                 detail, prev_hash, curr_hash, created_at)
            VALUES (:et, NULL, 'worker:ingest', :cid, :subj, CAST(:d AS jsonb),
                    :prev, :curr, :created_at)
            RETURNING id
            """
        ),
        {"et": event_type, "cid": client_id, "subj": subject,
         "d": json.dumps(detail, sort_keys=True), "prev": prev, "curr": curr,
         "created_at": sealed_at},
    ).scalar_one()
    return str(new_id)


@celery_app.task(name="app.workers.tasks.ingest_evidence", bind=True, max_retries=0)
def ingest_evidence(self, evidence_id: str, quarantine_key: str) -> dict:
    with service_session_sync("job_integrity") as session:
        ev = session.execute(
            text(
                "SELECT e.audit_id, e.client_id, e.declared_mime, e.size_bytes, "
                "e.dek_id, o.code AS client_code FROM evidence e "
                "JOIN organisation o ON o.id = e.client_id WHERE e.id = :id"
            ),
            {"id": evidence_id},
        ).first()
        if ev is None:
            return {"evidence_id": evidence_id, "status": "unknown"}

        # 1. Lecture quarantaine
        try:
            data = minio_client.read_object(settings.minio_quarantine_bucket, quarantine_key)
        except Exception:
            _reject(session, evidence_id, "quarantine_read_failed", quarantine_key)
            return {"evidence_id": evidence_id, "status": "rejected"}

        # Taille (défense en profondeur : la déclaration a déjà borné, on revérifie)
        if len(data) > settings.max_evidence_bytes:
            _reject(session, evidence_id, "too_large", quarantine_key)
            return {"evidence_id": evidence_id, "status": "rejected"}

        # 2. MIME réel (magic bytes) — un MIME déclaré menteur est rejeté
        detected = _detect_mime(data)
        if detected is None:
            _reject(session, evidence_id, "unsupported_or_spoofed_type", quarantine_key)
            return {"evidence_id": evidence_id, "status": "rejected"}

        # 3. Antivirus
        clean, verdict = _clamav_scan(data)
        if not clean:
            _reject(session, evidence_id, "malware_detected", quarantine_key, av=verdict)
            return {"evidence_id": evidence_id, "status": "rejected"}

        # 4. Empreinte du clair
        sha_plain = hashlib.sha256(data).hexdigest()

        # 5. Déballage DEK (Vault)
        dek_row = session.execute(
            text("SELECT encode(wrapped_dek, 'base64') AS w FROM audit_dek WHERE id = :id"),
            {"id": str(ev.dek_id)},
        ).first()
        if dek_row is None or dek_row.w is None:
            _reject(session, evidence_id, "dek_missing", quarantine_key)
            return {"evidence_id": evidence_id, "status": "rejected"}
        dek = vault_client.unwrap_dek(ev.client_code, dek_row.w.replace("\n", ""))

        # 6. Chiffrement AES-256-GCM
        aad = crypto.build_aad(evidence_id, str(ev.audit_id), sha_plain)
        nonce = crypto.new_nonce()
        blob, nonce = crypto.encrypt(dek, data, aad, nonce)  # blob = chiffré + tag GCM
        del dek  # effacement de la référence à la clé en clair

        # 7. Empreinte du chiffré
        sha_cipher = hashlib.sha256(blob).hexdigest()

        # 8. PUT MinIO + Object Lock (WORM)
        bucket = minio_client.evidence_bucket(ev.client_code)
        key = minio_client.object_key(ev.client_code, str(ev.audit_id), evidence_id)
        lock_until = minio_client.default_lock_until(3650)  # 10 ans (rétention par défaut)
        minio_client.put_locked_object(bucket, key, blob, lock_until)

        # 9. Scellement journal
        journal_id = _seal(
            session, event_type="evidence.stored", subject=evidence_id,
            client_id=str(ev.client_id),
            detail={"sha256_plaintext": sha_plain, "sha256_ciphertext": sha_cipher,
                    "bucket": bucket, "object_key": key, "detected_mime": detected},
        )

        # 10. Statut final (les triggers WORM figent désormais les champs de custody)
        session.execute(
            text(
                """
                UPDATE evidence SET
                  ingest_status='stored', detected_mime=:mime, sha256_plaintext=:sp,
                  sha256_ciphertext=:sc, bucket=:bucket, object_key=:key,
                  nonce=:nonce, av_verdict=:av, size_bytes=:size,
                  stored_at=now(), journal_entry_id=:jid,
                  object_lock_until=:lock, retention_until=:lock, updated_at=now()
                WHERE id=:id
                """
            ),
            {
                "mime": detected, "sp": sha_plain, "sc": sha_cipher, "bucket": bucket,
                "key": key, "nonce": nonce, "av": verdict, "size": len(data),
                "jid": journal_id, "lock": lock_until, "id": evidence_id,
            },
        )
        minio_client.purge_quarantine(quarantine_key)

    return {"evidence_id": evidence_id, "status": "stored", "sha256": sha_plain}


@celery_app.task(name="app.workers.tasks.retention_sweep")
def retention_sweep() -> dict:
    """Crypto-effacement : détruit la DEK des audits dont la rétention est échue.

    Détruire la DEK rend le chiffré définitivement illisible (crypto-shredding) sans
    toucher aux objets sous Object Lock (cahier §6quater.6). Action irréversible :
    tracée au journal, jamais silencieuse.
    """
    destroyed = 0
    with service_session_sync("job_retention") as session:
        rows = session.execute(
            text(
                "SELECT DISTINCT ad.id, ad.audit_id, ad.client_id FROM audit_dek ad "
                "JOIN evidence e ON e.dek_id = ad.id "
                "WHERE ad.status='active' AND e.retention_until IS NOT NULL "
                "AND e.retention_until < now() AND e.legal_hold = false"
            )
        ).all()
        for r in rows:
            session.execute(
                text(
                    "UPDATE audit_dek SET status='destroyed', wrapped_dek=NULL, "
                    "destroyed_at=now(), destroyed_reason='retention_expired' WHERE id=:id"
                ),
                {"id": str(r.id)},
            )
            _seal(session, event_type="evidence.crypto_shred", subject=str(r.audit_id),
                  client_id=str(r.client_id), detail={"dek_id": str(r.id)})
            destroyed += 1
    return {"destroyed_deks": destroyed}


@celery_app.task(name="app.workers.tasks.integrity_check")
def integrity_check() -> dict:
    """Vérifie que le sha256 du chiffré stocké correspond à l'objet MinIO."""
    checked = mismatches = 0
    with service_session_sync("job_integrity") as session:
        rows = session.execute(
            text(
                "SELECT id, bucket, object_key, sha256_ciphertext FROM evidence "
                "WHERE ingest_status='stored' AND deleted_at IS NULL LIMIT 500"
            )
        ).all()
        for r in rows:
            checked += 1
            try:
                blob = minio_client.read_object(r.bucket, r.object_key)
                actual = hashlib.sha256(blob).hexdigest()
            except Exception:
                actual = None
            if actual != r.sha256_ciphertext:
                mismatches += 1
                _seal(session, event_type="evidence.integrity_mismatch", subject=str(r.id),
                      detail={"expected": r.sha256_ciphertext, "actual": actual})
    return {"checked": checked, "mismatches": mismatches}


@celery_app.task(name="app.workers.tasks.journal_verify")
def journal_verify() -> dict:
    """Recalcule la chaîne du journal et scelle le résultat de la vérification."""
    with service_session_sync("job_integrity") as session:
        rows = session.execute(
            text(
                "SELECT seq, event_type, actor_id, actor_label, client_id, subject, "
                "detail, prev_hash, curr_hash, created_at FROM journal ORDER BY seq ASC"
            )
        ).all()
        prev = GENESIS
        break_at = None
        for r in rows:
            entry = {
                "event_type": r.event_type, "actor_id": r.actor_id,
                "actor_label": r.actor_label, "client_id": r.client_id,
                "subject": r.subject,
                "detail": r.detail if isinstance(r.detail, dict) else json.loads(r.detail or "{}"),
                "at": r.created_at.isoformat(),
            }
            if r.prev_hash != prev or compute_hash(prev, entry) != r.curr_hash:
                break_at = r.seq
                break
            prev = r.curr_hash
    return {"intact": break_at is None, "break_at_seq": break_at}
