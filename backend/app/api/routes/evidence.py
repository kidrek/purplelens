"""Routes du sous-système de preuves (cahier §6quater — le cœur sécurité).

Invariants appliqués ici :
  - Aucun binaire ne transite par l'API : POST /evidence renvoie une URL présignée
    d'upload (≤ presign_upload_ttl) vers le bucket de QUARANTAINE. Le sas (worker)
    valide/chiffre/scelle ensuite (route /ingest déclenche la tâche Celery).
  - Le download exige le triple contrôle (RBAC matrice + cloisonnement + TLP/PAP),
    puis renvoie une URL présignée courte. CHAQUE tentative (accord OU refus) est
    tracée dans evidence_access (§6quater.7).
  - La DEK d'audit est provisionnée à la volée (enveloppe DEK←KEK/Vault) ; la DEK
    en clair n'est jamais journalisée ni renvoyée au client.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

import hvac.exceptions
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.config import settings
from app.db.session import rls_session, service_session
from app.journal.chain import append as journal_append
from app.schemas.evidence import (
    AccessEntry,
    CustodyChain,
    EvidenceInitRequest,
    EvidenceOut,
    PresignedDownload,
    PresignedUpload,
)
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import can, require, requires_fresh_stepup_for_clear
from app.storage import crypto, minio_client, vault_client

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
_UTC = UTC
_log = logging.getLogger(__name__)


async def _client_code(session, client_id: str) -> str:
    row = (
        await session.execute(
            text("SELECT code FROM organisation WHERE id = :id"), {"id": client_id}
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client_unknown")
    return row.code


async def _ensure_audit_dek(session, *, audit_id: str, client_id: str, client_code: str) -> str:
    """Renvoie l'id de la DEK active de l'audit, en la provisionnant si absente."""
    row = (
        await session.execute(
            text(
                "SELECT id FROM audit_dek WHERE audit_id = :a AND status = 'active' LIMIT 1"
            ),
            {"a": audit_id},
        )
    ).first()
    if row is not None:
        return str(row.id)

    # Provision : KEK client (Vault transit) puis DEK enveloppée. DEK claire jamais stockée.
    vault_client.ensure_client_kek(client_code)
    dek = vault_client.generate_dek()
    wrapped, version = vault_client.wrap_dek(client_code, dek)
    del dek  # effacement de la référence en clair au plus tôt
    new_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO audit_dek (id, audit_id, client_id, wrapped_dek, kek_ref,
                                   kek_version, status, created_at)
            VALUES (:id, :a, :c, :w, :ref, :ver, 'active', now())
            """
        ),
        {
            # Le ciphertext Vault transit est un jeton texte opaque « vault:vN:<b64> » :
            # on stocke ses octets UTF-8 tels quels (pas de decode base64 — le préfixe
            # « vault:vN: » n'est pas du base64), relus et décodés à l'unwrap.
            "id": new_id, "a": audit_id, "c": client_id, "w": wrapped.encode("utf-8"),
            "ref": vault_client.kek_name(client_code), "ver": version,
        },
    )
    await journal_append(
        session, event_type="evidence.dek.provisioned", actor_id=None,
        client_id=client_id, subject=audit_id, detail={"dek_id": new_id, "kek_version": version},
    )
    return new_id


@router.post("", response_model=PresignedUpload, status_code=status.HTTP_201_CREATED)
async def init_evidence(
    payload: EvidenceInitRequest,
    request: Request,
    ctx: SecurityContext = Depends(require("evidence", Action.C)),
):
    """Déclare une preuve et renvoie une URL présignée d'upload vers la quarantaine."""
    # can() applique ici : porte 2 (une preuve TLP:RED/AMBER exige une session MFA — on
    # transmet donc le TLP/PAP déclarés, pour BLOQUER dès le dépôt ce qui ne pourrait de
    # toute façon pas être relu sans MFA — cohérence upload/download) ET porte 4 (le
    # client de la preuve doit être dans le périmètre de l'appelant).
    decision = can(
        ctx, Action.C, "evidence",
        {"client_id": str(payload.client_id), "tlp": payload.tlp, "pap": payload.pap},
    )
    if not decision.allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    if payload.size_bytes > settings.max_evidence_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too_large")

    evidence_id = uuid.uuid4()
    quarantine_key = f"incoming/{payload.client_id}/{evidence_id}"

    # Provisionnement de la DEK d'audit sous un rôle de SERVICE : la table audit_dek est
    # la frontière crypto (spec v2 §3.1 note ³) — sa RLS interdit tout accès aux rôles
    # interactifs (auditeur inclus). Le BFF, point unique de décision, réalise ce
    # sous-traitement privilégié après avoir validé la porte 4 ci-dessus. La preuve
    # elle-même reste écrite sous le rôle de l'appelant (cloisonnement RLS standard).
    try:
        async with service_session("admin_service") as dek_session:
            client_code = await _client_code(dek_session, str(payload.client_id))
            dek_id = await _ensure_audit_dek(
                dek_session, audit_id=str(payload.audit_id), client_id=str(payload.client_id),
                client_code=client_code,
            )
    except hvac.exceptions.VaultError as e:
        _log.error("Vault indisponible lors du provisionnement DEK (audit %s): %s", payload.audit_id, e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="vault_unavailable"
        ) from e

    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        await session.execute(
            text(
                """
                INSERT INTO evidence
                  (id, audit_id, client_id, finding_id, audit_action_id, attack_step_id,
                   original_filename, declared_mime, size_bytes, dek_id, tlp, pap,
                   contains_pii, contains_secrets, caption, ingest_status,
                   uploaded_by, uploaded_at, created_at, updated_at)
                VALUES
                  (:id, :audit, :client, :finding, :action, :step,
                   :fname, :mime, :size, :dek, :tlp, :pap,
                   :pii, :secrets, :caption, 'quarantined',
                   :uploader, now(), now(), now())
                """
            ),
            {
                "id": str(evidence_id), "audit": str(payload.audit_id),
                "client": str(payload.client_id),
                "finding": str(payload.finding_id) if payload.finding_id else None,
                "action": str(payload.audit_action_id) if payload.audit_action_id else None,
                "step": str(payload.attack_step_id) if payload.attack_step_id else None,
                "fname": payload.original_filename, "mime": payload.declared_mime,
                "size": payload.size_bytes, "dek": dek_id, "tlp": payload.tlp, "pap": payload.pap,
                "pii": payload.contains_pii, "secrets": payload.contains_secrets,
                "caption": payload.caption, "uploader": ctx.user_id,
            },
        )
        await journal_append(
            session, event_type="evidence.declared", actor_id=ctx.user_id,
            client_id=str(payload.client_id), subject=str(evidence_id),
            detail={"filename": payload.original_filename, "size": payload.size_bytes},
        )

    upload_url = minio_client.presign_upload(
        settings.minio_quarantine_bucket, quarantine_key, origin=minio_client.public_origin(request)
    )
    return PresignedUpload(
        evidence_id=evidence_id, upload_url=upload_url, object_key=quarantine_key,
        bucket=settings.minio_quarantine_bucket,
        expires_in=settings.presign_upload_ttl_seconds,
    )


@router.post("/{evidence_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    evidence_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("evidence", Action.C)),
):
    """Signale la fin de l'upload client → enclenche le sas d'ingestion (Celery)."""
    from app.workers.tasks import ingest_evidence

    quarantine_key = None
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text("SELECT client_id, ingest_status FROM evidence WHERE id = :id"),
                {"id": str(evidence_id)},
            )
        ).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        if row.ingest_status != "quarantined":
            raise HTTPException(status.HTTP_409_CONFLICT, detail="already_processed")
        quarantine_key = f"incoming/{row.client_id}/{evidence_id}"

    ingest_evidence.delay(str(evidence_id), quarantine_key)
    return {"evidence_id": str(evidence_id), "status": "queued"}


@router.get("", response_model=list[EvidenceOut])
async def list_evidence(
    audit_id: uuid.UUID | None = None,
    finding_id: uuid.UUID | None = None,
    ctx: SecurityContext = Depends(require("evidence", Action.L)),
):
    """Preuves visibles (cloisonnement RLS), filtrables par audit et/ou vulnérabilité
    (finding_id). Un seul point d'entrée gardé — pas de route dérivée par entité."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        # Enrichissement d'affichage (coffre → tableau) : on résout par jointure
        # l'organisation, l'audit, l'application et l'auditeur ayant déposé la preuve.
        #  - organisation/audit/application sont cloisonnées RLS mais du MÊME client que
        #    la preuve → visibles ici (app_user est hors RLS, lisible en SELECT).
        #  - application : pas de lien direct sur `evidence`. On la déduit de l'action
        #    d'audit rattachée (audit_action.application_id) ; à défaut, de l'unique
        #    application de l'audit (sinon on laisse vide plutôt que d'en choisir une).
        base = """
            SELECT e.*,
                   o.nom AS organisation_nom,
                   a.nom AS audit_nom,
                   COALESCE(app_action.nom, app_solo.nom) AS application_nom,
                   COALESCE(u.display_name, u.email) AS uploader_nom
            FROM evidence e
            LEFT JOIN organisation o ON o.id = e.client_id
            LEFT JOIN audit a ON a.id = e.audit_id
            LEFT JOIN audit_action aa ON aa.id = e.audit_action_id
            LEFT JOIN application app_action ON app_action.id = aa.application_id
            LEFT JOIN application app_solo
                   ON cardinality(a.applications) = 1 AND app_solo.id = (a.applications)[1]
            LEFT JOIN app_user u ON u.id = e.uploaded_by
            WHERE e.deleted_at IS NULL
        """
        params: dict = {}
        if audit_id:
            base += " AND e.audit_id = :a"
            params["a"] = str(audit_id)
        if finding_id:
            base += " AND e.finding_id = :f"
            params["f"] = str(finding_id)
        base += " ORDER BY e.uploaded_at DESC LIMIT 200"
        rows = (await session.execute(text(base), params)).mappings().all()
    return [EvidenceOut(**dict(r)) for r in rows]


@router.get("/{evidence_id}", response_model=EvidenceOut)
async def get_evidence(
    evidence_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("evidence", Action.L)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text("SELECT * FROM evidence WHERE id = :id AND deleted_at IS NULL"),
                {"id": str(evidence_id)},
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    return EvidenceOut(**dict(row))


async def _record_access(
    session, *, evidence_id: str, client_id: str, ctx: SecurityContext,
    purpose: str, granted: bool, denial_reason: str | None, ip: str | None,
    expires_at: datetime | None,
) -> None:
    """Trace TOUTE consultation dans evidence_access — accord comme refus (§6quater.7)."""
    await session.execute(
        text(
            """
            INSERT INTO evidence_access
              (id, evidence_id, client_id, actor_user_id, actor_label, purpose,
               granted, denial_reason, presigned_expires_at, ip, created_at)
            VALUES
              (gen_random_uuid(), :ev, :cl, :actor, :label, :purpose,
               :granted, :reason, :exp, :ip, now())
            """
        ),
        {
            "ev": evidence_id, "cl": client_id, "actor": ctx.user_id,
            "label": ctx.email, "purpose": purpose, "granted": granted,
            "reason": denial_reason, "exp": expires_at, "ip": ip,
        },
    )


@router.get("/{evidence_id}/download", response_model=PresignedDownload)
async def download_evidence(
    evidence_id: uuid.UUID,
    request: Request,
    purpose: str = "view",
    ctx: SecurityContext = Depends(require("evidence", Action.L)),
):
    """Triple contrôle → URL présignée courte. Chaque tentative est tracée."""
    ip = request.client.host if request.client else None
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text(
                    "SELECT client_id, bucket, object_key, tlp, pap, contains_secrets, "
                    "ingest_status FROM evidence WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": str(evidence_id)},
            )
        ).first()
        if row is None:
            # RLS a pu masquer la ligne : refus tracé impossible sans client_id → 404 net.
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")

        record = {
            "client_id": str(row.client_id), "tlp": row.tlp, "pap": row.pap,
            "contains_secrets": row.contains_secrets,
        }
        decision = can(ctx, Action.L, "evidence", record, purpose=purpose)
        if not decision.allowed or row.ingest_status != "stored":
            reason = decision.reason if not decision.allowed else "not_stored"
            await _record_access(
                session, evidence_id=str(evidence_id), client_id=str(row.client_id),
                ctx=ctx, purpose=purpose, granted=False, denial_reason=reason,
                ip=ip, expires_at=None,
            )
            await journal_append(
                session, event_type="evidence.access.denied", actor_id=ctx.user_id,
                client_id=str(row.client_id), subject=str(evidence_id),
                detail={"purpose": purpose, "reason": reason},
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")

        expires_at = datetime.now(_UTC)
        await _record_access(
            session, evidence_id=str(evidence_id), client_id=str(row.client_id),
            ctx=ctx, purpose=purpose, granted=True, denial_reason=None, ip=ip,
            expires_at=expires_at,
        )
        await journal_append(
            session, event_type="evidence.access.granted", actor_id=ctx.user_id,
            client_id=str(row.client_id), subject=str(evidence_id),
            detail={"purpose": purpose},
        )
        bucket, key = row.bucket, row.object_key

    url = minio_client.presign_download(bucket, key, origin=minio_client.public_origin(request))
    return PresignedDownload(
        evidence_id=evidence_id, download_url=url,
        expires_in=settings.presign_download_ttl_seconds,
        tlp=row.tlp, pap=row.pap, masked=False,
    )


def _decrypt_blob(bucket: str, key: str, *, client_code: str, wrapped: str,
                  evidence_id: str, audit_id: str, sha_plain: str, nonce: bytes) -> bytes:
    """Lecture WORM + unwrap DEK (Vault) + déchiffrement AES-256-GCM. Bloquant (IO/CPU) :
    appelé via run_in_threadpool pour ne pas figer la boucle d'événements."""
    blob = minio_client.read_object(bucket, key)
    dek = vault_client.unwrap_dek(client_code, wrapped)
    try:
        aad = crypto.build_aad(evidence_id, audit_id, sha_plain)
        return crypto.decrypt(dek, blob, aad, bytes(nonce))
    finally:
        del dek  # efface la référence à la clé en clair au plus tôt


@router.get("/{evidence_id}/content")
async def download_evidence_content(
    evidence_id: uuid.UUID,
    request: Request,
    purpose: str = "view",
    ctx: SecurityContext = Depends(require("evidence", Action.L)),
):
    """Renvoie le CONTENU DÉCHIFFRÉ de la preuve (streaming via l'API).

    Déviation ASSUMÉE de la DAT §4.1 (« aucun binaire via l'API ») : c'est la seule
    façon de servir le clair sans écrire de plaintext au repos ni exposer une URL
    présignée capable de fuiter. Le clair ne vit qu'en mémoire, le contrôle d'accès
    est appliqué sur la MÊME requête qui délivre les octets, et chaque tentative est
    tracée dans evidence_access. Les preuves `contains_secrets` ne sont JAMAIS servies
    en clair par cette voie (masquage réservé au rendu de livrable — DAT §2.6).
    """
    ip = request.client.host if request.client else None
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text(
                    "SELECT client_id, audit_id, bucket, object_key, nonce, sha256_plaintext, "
                    "dek_id, original_filename, detected_mime, declared_mime, tlp, pap, "
                    "contains_secrets, ingest_status FROM evidence "
                    "WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": str(evidence_id)},
            )
        ).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")

        record = {
            "client_id": str(row.client_id), "tlp": row.tlp, "pap": row.pap,
            "contains_secrets": row.contains_secrets,
        }
        decision = can(ctx, Action.L, "evidence", record, purpose=purpose)
        # Blocage explicite du clair pour une preuve marquée « secrets » (jamais servie
        # en clair hors livrable masqué), en plus du triple contrôle et de l'état 'stored'.
        if not decision.allowed or row.ingest_status != "stored" or row.contains_secrets:
            if row.contains_secrets and decision.allowed and row.ingest_status == "stored":
                reason = "secrets_masked"
            elif not decision.allowed:
                reason = decision.reason
            else:
                reason = "not_stored"
            await _record_access(
                session, evidence_id=str(evidence_id), client_id=str(row.client_id),
                ctx=ctx, purpose=purpose, granted=False, denial_reason=reason,
                ip=ip, expires_at=None,
            )
            await journal_append(
                session, event_type="evidence.access.denied", actor_id=ctx.user_id,
                client_id=str(row.client_id), subject=str(evidence_id),
                detail={"purpose": purpose, "reason": reason},
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")

        # Durcissement P1 : servir le CLAIR d'une preuve TLP:RED exige une réauth MFA
        # récente (step-up), au-delà de la simple session MFA (porte 2). Refus 401 qui
        # invite le client à repasser par /auth/step-up.
        if requires_fresh_stepup_for_clear(record) and not ctx.step_up_fresh(
            settings.step_up_max_age_seconds
        ):
            await _record_access(
                session, evidence_id=str(evidence_id), client_id=str(row.client_id),
                ctx=ctx, purpose=purpose, granted=False, denial_reason="stepup_required",
                ip=ip, expires_at=None,
            )
            await journal_append(
                session, event_type="evidence.access.denied", actor_id=ctx.user_id,
                client_id=str(row.client_id), subject=str(evidence_id),
                detail={"purpose": purpose, "reason": "stepup_required"},
            )
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail="step_up_required",
                headers={"WWW-Authenticate": 'MFA realm="step-up"'},
            )

        await _record_access(
            session, evidence_id=str(evidence_id), client_id=str(row.client_id),
            ctx=ctx, purpose=purpose, granted=True, denial_reason=None, ip=ip,
            expires_at=datetime.now(_UTC),
        )
        await journal_append(
            session, event_type="evidence.access.granted", actor_id=ctx.user_id,
            client_id=str(row.client_id), subject=str(evidence_id),
            detail={"purpose": purpose, "delivery": "stream"},
        )
        client_id, audit_id = str(row.client_id), str(row.audit_id)
        bucket, key, nonce = row.bucket, row.object_key, row.nonce
        sha_plain, dek_id = row.sha256_plaintext, str(row.dek_id)
        filename = row.original_filename or "evidence"
        mime = row.detected_mime or row.declared_mime or "application/octet-stream"

    # DEK sous rôle de service (audit_dek = frontière crypto, interdit aux rôles interactifs).
    async with service_session("admin_service") as svc:
        client_code = await _client_code(svc, client_id)
        # Filtre client EXPLICITE (défense en profondeur) : la DEK servie doit appartenir
        # au même client que la preuve, en plus du lien par dek_id. Empêche qu'un dek_id
        # mal apparié (bug/altération) déballe une DEK d'un autre client.
        dek_row = (
            await svc.execute(
                text(
                    "SELECT wrapped_dek FROM audit_dek WHERE id = :id AND client_id = :cid"
                ),
                {"id": dek_id, "cid": client_id},
            )
        ).first()
    if dek_row is None or dek_row.wrapped_dek is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="dek_unavailable")
    wrapped = (
        dek_row.wrapped_dek.decode("utf-8")
        if isinstance(dek_row.wrapped_dek, (bytes, bytearray))
        else str(dek_row.wrapped_dek)
    )

    try:
        plain = await run_in_threadpool(
            _decrypt_blob, bucket, key, client_code=client_code, wrapped=wrapped,
            evidence_id=str(evidence_id), audit_id=audit_id, sha_plain=sha_plain, nonce=nonce,
        )
    except hvac.exceptions.VaultError as e:
        _log.error("Vault indisponible au déchiffrement (evidence %s): %s", evidence_id, e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="vault_unavailable") from e

    # Nom de fichier assaini (anti-injection d'en-tête) via RFC 5987 filename*.
    safe = filename.replace("\r", "").replace("\n", "").replace('"', "")
    disposition = f"attachment; filename*=UTF-8''{quote(safe, safe='')}"
    return Response(content=plain, media_type=mime, headers={"Content-Disposition": disposition})


@router.get("/{evidence_id}/custody", response_model=CustodyChain)
async def custody(
    evidence_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("evidence", Action.L)),
):
    """Chaîne de possession : métadonnées custody + historique des accès."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        ev = (
            await session.execute(
                text(
                    "SELECT id, original_filename, sha256_plaintext, sha256_ciphertext, "
                    "ingest_status, uploaded_by, uploaded_at, stored_at, journal_entry_id, "
                    "encryption_alg, object_lock_until FROM evidence WHERE id = :id"
                ),
                {"id": str(evidence_id)},
            )
        ).first()
        if ev is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        accesses = (
            await session.execute(
                text(
                    "SELECT purpose, granted, denial_reason, actor_user_id, created_at "
                    "FROM evidence_access WHERE evidence_id = :id ORDER BY created_at"
                ),
                {"id": str(evidence_id)},
            )
        ).mappings().all()

    return CustodyChain(
        evidence_id=ev.id, original_filename=ev.original_filename,
        sha256_plaintext=ev.sha256_plaintext, sha256_ciphertext=ev.sha256_ciphertext,
        ingest_status=ev.ingest_status, uploaded_by=ev.uploaded_by,
        uploaded_at=ev.uploaded_at, stored_at=ev.stored_at,
        journal_entry_id=ev.journal_entry_id, encryption_alg=ev.encryption_alg,
        object_lock_until=ev.object_lock_until,
        accesses=[AccessEntry(**dict(a)) for a in accesses],
    )
