"""Route de génération de livrables (cahier §5).

Génère un PDF (lettre d'engagement, NDA, rapport PTES), le stocke dans le bucket
livrables du client et crée la ligne `deliverable`. La création exige la permission
de matrice (C sur `deliverables`) ; le rendu masque les preuves secrètes (porte 5).
"""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.db.session import rls_session, service_session
from app.deliverables import service as deliverable_service
from app.journal.chain import append as journal_append
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import require
from app.storage import crypto, minio_client, vault_client

router = APIRouter(prefix="/api/deliverables", tags=["deliverables"])
_UTC = UTC
_log = logging.getLogger(__name__)


def _build_previews(client_code: str, wrapped_by_dek: dict[str, str], items: list[dict]) -> dict[str, str]:
    """Déchiffre les preuves image candidates → data URI base64 (bloquant, threadpool).

    La DEK d'audit est déballée une fois par `dek_id` (cache) puis réutilisée. Une
    preuve qui échoue (objet manquant, tag GCM invalide) est simplement ignorée."""
    dek_cache: dict[str, bytes] = {}
    out: dict[str, str] = {}
    for e in items:
        did = str(e["dek_id"])
        wrapped = wrapped_by_dek.get(did)
        if not wrapped:
            continue
        if did not in dek_cache:
            dek_cache[did] = vault_client.unwrap_dek(client_code, wrapped)
        try:
            blob = minio_client.read_object(e["bucket"], e["object_key"])
            aad = crypto.build_aad(str(e["id"]), str(e["audit_id"]), e["sha256_plaintext"])
            plain = crypto.decrypt(dek_cache[did], blob, aad, bytes(e["nonce"]))
        except Exception:  # pragma: no cover
            _log.warning("aperçu preuve %s indisponible", e.get("id"), exc_info=True)
            continue
        b64 = base64.b64encode(plain).decode("ascii")
        out[str(e["id"])] = f"data:{e['detected_mime']};base64,{b64}"
    return out


class DeliverableRequest(BaseModel):
    client_id: uuid.UUID
    audit_id: uuid.UUID | None = None
    type: str  # engagement | nda | rapport
    langue: str = "fr"
    tlp: str = "AMBER"


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate(
    payload: DeliverableRequest,
    request: Request,
    ctx: SecurityContext = Depends(require("deliverables", Action.C)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        org = (
            await session.execute(
                text(
                    "SELECT nom, code, siren, secteur, referent_interne "
                    "FROM organisation WHERE id = :id"
                ),
                {"id": str(payload.client_id)},
            )
        ).mappings().first()
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client_unknown")
        client = dict(org)

        # Prestataire : l'organisation de rôle 'prestataire' (celle des auditeurs).
        # Sous RLS, elle peut être hors du périmètre de l'appelant : les gabarits
        # tolèrent None (nom générique en repli).
        presta_row = (
            await session.execute(
                text(
                    "SELECT nom, siren, secteur, referent_interne FROM organisation "
                    "WHERE role = 'prestataire' AND deleted_at IS NULL "
                    "ORDER BY created_at LIMIT 1"
                )
            )
        ).mappings().first()
        prestataire = dict(presta_row) if presta_row else None

        audit: dict = {}
        engagement: dict = {}
        scenario: dict | None = None
        applications: list[dict] = []
        auditeurs: list[dict] = []
        actions: list[dict] = []
        findings: list[dict] = []
        evidence: list[dict] = []

        if payload.audit_id:
            audit_row = (
                await session.execute(
                    text(
                        "SELECT nom, categorie, type_test, scenario_id, applications, "
                        "auditeurs, environnement, date_debut, date_fin, statut, tlp, "
                        "engagement, referentiels_methodo "
                        "FROM audit WHERE id = :id AND deleted_at IS NULL"
                    ),
                    {"id": str(payload.audit_id)},
                )
            ).mappings().first()
            if audit_row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="audit_unknown")
            audit = dict(audit_row)
            engagement = audit.get("engagement") or {}

            # Scénario émulé (catalogue CTI) — métadonnées de menace.
            if audit.get("scenario_id"):
                scn = (
                    await session.execute(
                        text(
                            "SELECT nom, objectif, acteur_emule, type_engagement, "
                            "sophistication, techniques FROM scenario "
                            "WHERE id = :id AND deleted_at IS NULL"
                        ),
                        {"id": str(audit["scenario_id"])},
                    )
                ).mappings().first()
                scenario = dict(scn) if scn else None

            # Applications ciblées (UUID[] de l'audit).
            if audit.get("applications"):
                applications = [
                    dict(r)
                    for r in (
                        await session.execute(
                            text(
                                "SELECT nom, version, criticite, exposition, stack "
                                "FROM application WHERE id = ANY(:ids) AND deleted_at IS NULL "
                                "ORDER BY nom"
                            ),
                            {"ids": [str(i) for i in audit["applications"]]},
                        )
                    ).mappings().all()
                ]

            # Équipe d'audit assignée (ressources humaines → cahier §5.A).
            if audit.get("auditeurs"):
                auditeurs = [
                    dict(r)
                    for r in (
                        await session.execute(
                            text(
                                "SELECT nom, role, competences, contact FROM ressource "
                                "WHERE id = ANY(:ids) AND deleted_at IS NULL ORDER BY nom"
                            ),
                            {"ids": [str(i) for i in audit["auditeurs"]]},
                        )
                    ).mappings().all()
                ]

            # Actions d'audit par phase PTES (traçabilité de la mission).
            actions = [
                dict(r)
                for r in (
                    await session.execute(
                        text(
                            "SELECT ptes_phase, titre, technique_attack, outil, resultat "
                            "FROM audit_action WHERE audit_id = :a AND deleted_at IS NULL "
                            "ORDER BY horodatage_debut NULLS LAST, created_at"
                        ),
                        {"a": str(payload.audit_id)},
                    )
                ).mappings().all()
            ]

            # Vulnérabilités de la mission (celles rattachées à l'audit + celles du
            # client non rattachées), enrichies EPSS/KEV quand disponible.
            findings = [
                dict(r)
                for r in (
                    await session.execute(
                        text(
                            "SELECT v.id, v.titre, v.cve, v.cwe, v.severite, v.cvss_score, "
                            "v.cvss_vector, v.sla_niveau, v.sla_echeance, v.statut, "
                            "v.description, v.recommandation, v.impact_metier, "
                            "v.exploitabilite, v.owasp_top10, v.phase_decouverte, "
                            "v.preuve_exploitation, v.techniques, v.d3fend, v.tlp, "
                            "round(e.epss_score, 3) AS epss, e.epss_percentile, e.kev, "
                            "e.kev_ransomware, e.ssvc_decision, e.vex_status, "
                            "r.nom AS decouvreur_nom "
                            "FROM vulnerability v "
                            "LEFT JOIN vulnerability_enrichment e ON e.vulnerability_id = v.id "
                            "LEFT JOIN ressource r ON r.id = v.decouvreur_id "
                            "WHERE v.client_id = :c AND v.deleted_at IS NULL "
                            "AND (v.audit_id = :a OR v.audit_id IS NULL) "
                            "ORDER BY v.cvss_score DESC NULLS LAST"
                        ),
                        {"c": str(payload.client_id), "a": str(payload.audit_id)},
                    )
                ).mappings().all()
            ]
            evidence = [
                dict(r)
                for r in (
                    await session.execute(
                        text(
                            "SELECT e.id, e.finding_id, e.audit_id, e.original_filename, "
                            "e.caption, e.contains_secrets, e.detected_mime, "
                            "e.sha256_plaintext, e.size_bytes, e.uploaded_at, e.bucket, "
                            "e.object_key, e.nonce, e.dek_id, "
                            "COALESCE(u.display_name, u.email) AS uploaded_by_name "
                            "FROM evidence e LEFT JOIN app_user u ON u.id = e.uploaded_by "
                            "WHERE e.audit_id = :a AND e.ingest_status = 'stored' "
                            "AND e.deleted_at IS NULL ORDER BY e.uploaded_at"
                        ),
                        {"a": str(payload.audit_id)},
                    )
                ).mappings().all()
            ]

            # Aperçus d'images inline (preuves déchiffrées dans le rapport — DAT §2.6 :
            # « preuves inline déchiffrées », accès tracés). Preuves NON secrètes, de
            # type image, sous la limite de taille. La DEK (audit_dek) est lue sous rôle
            # de service (frontière crypto interdite aux rôles interactifs).
            previews: dict[str, str] = {}
            img_candidates = [
                e for e in evidence
                if not e.get("contains_secrets")
                and str(e.get("detected_mime") or "").startswith("image/")
                and e.get("size_bytes") and e["size_bytes"] <= settings.evidence_preview_max_bytes
                and e.get("dek_id") and e.get("bucket") and e.get("object_key")
                and e.get("nonce") and e.get("sha256_plaintext")
            ]
            if img_candidates:
                dek_ids = {str(e["dek_id"]) for e in img_candidates}
                wrapped_by_dek: dict[str, str] = {}
                async with service_session("admin_service") as svc:
                    for did in dek_ids:
                        drow = (
                            await svc.execute(
                                text("SELECT wrapped_dek FROM audit_dek WHERE id = :id"),
                                {"id": did},
                            )
                        ).first()
                        if drow is not None and drow.wrapped_dek is not None:
                            wrapped_by_dek[did] = (
                                drow.wrapped_dek.decode("utf-8")
                                if isinstance(drow.wrapped_dek, (bytes, bytearray))
                                else str(drow.wrapped_dek)
                            )
                previews = await run_in_threadpool(
                    _build_previews, client["code"], wrapped_by_dek, img_candidates
                )
                # Traçabilité custody : chaque preuve effectivement inlinée est un accès
                # déchiffré, journalisé nominativement (evidence_access, purpose report_render).
                ip = request.client.host if request.client else None
                for e in img_candidates:
                    if str(e["id"]) not in previews:
                        continue
                    await session.execute(
                        text(
                            "INSERT INTO evidence_access (id, evidence_id, client_id, "
                            "actor_user_id, actor_label, purpose, granted, ip, created_at) "
                            "VALUES (gen_random_uuid(), :ev, :cl, :actor, :label, "
                            "'report_render', true, :ip, now())"
                        ),
                        {"ev": str(e["id"]), "cl": str(payload.client_id),
                         "actor": ctx.user_id, "label": ctx.email, "ip": ip},
                    )
                    await journal_append(
                        session, event_type="evidence.access.granted", actor_id=ctx.user_id,
                        client_id=str(payload.client_id), subject=str(e["id"]),
                        detail={"purpose": "report_render", "delivery": "inline"},
                    )

        if payload.type == "engagement":
            content = deliverable_service.render_engagement_letter(
                client=client, prestataire=prestataire, audit=audit,
                engagement=engagement, scenario=scenario,
                applications=applications, auditeurs=auditeurs, tlp=payload.tlp,
                langue=payload.langue,
            )
        elif payload.type == "nda":
            content = deliverable_service.render_nda(
                client=client, prestataire=prestataire, engagement=engagement,
                audit=audit or None, tlp=payload.tlp, langue=payload.langue,
            )
        elif payload.type == "rapport":
            content = deliverable_service.render_ptes_report(
                client=client, prestataire=prestataire, audit=audit,
                scenario=scenario, applications=applications, auditeurs=auditeurs,
                actions=actions, findings=findings, evidence=evidence, tlp=payload.tlp,
                langue=payload.langue, previews=previews,
                preview_max_bytes=settings.evidence_preview_max_bytes,
            )
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unknown_type")

        try:
            pdf_bytes = await deliverable_service.html_to_pdf(content)
        except Exception as exc:
            # Rendu indisponible (Chromium absent, renderer HS) : on n'écrit NI en
            # base NI dans MinIO — mieux vaut pas de livrable qu'un faux PDF.
            _log.error("pdf-renderer indisponible: %s", exc, exc_info=True)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, detail="pdf_renderer_unavailable"
            ) from None

        deliverable_id = uuid.uuid4()
        bucket = minio_client.evidence_bucket(client["code"])
        key = f"client/{client['code']}/deliverables/{deliverable_id}.pdf"
        lock_until = minio_client.default_lock_until(365)
        minio_client.put_locked_object(bucket, key, pdf_bytes, lock_until)

        await session.execute(
            text(
                """
                INSERT INTO deliverable
                  (id, client_id, audit_id, type, titre, langue, tlp, statut,
                   storage_key, meta, created_at, updated_at)
                VALUES
                  (:id, :client, :audit, :type, :titre, :langue, :tlp, 'genere',
                   :key, CAST(:meta AS jsonb), now(), now())
                """
            ),
            {
                "id": str(deliverable_id), "client": str(payload.client_id),
                "audit": str(payload.audit_id) if payload.audit_id else None,
                "type": payload.type, "titre": f"{payload.type} — {client['nom']}",
                "langue": payload.langue, "tlp": payload.tlp, "key": key,
                "meta": f'{{"findings": {len(findings)}}}',
            },
        )
        await journal_append(
            session, event_type="deliverable.generated", actor_id=ctx.user_id,
            client_id=str(payload.client_id), subject=str(deliverable_id),
            detail={"type": payload.type, "tlp": payload.tlp},
        )

    return {"id": str(deliverable_id), "type": payload.type, "storage_key": key}


@router.get("/{deliverable_id}/download")
async def download_deliverable(
    deliverable_id: uuid.UUID,
    request: Request,
    ctx: SecurityContext = Depends(require("deliverables", Action.L)),
):
    """Renvoie une URL présignée COURTE vers le PDF (jamais le binaire via l'API).

    Le livrable est déjà rendu (secrets masqués à la génération — porte 5). L'accès
    est cloisonné par la RLS et journalisé. L'URL expire selon presign_download_ttl.
    """
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text(
                    "SELECT d.client_id, d.storage_key, d.statut, d.titre, o.code "
                    "FROM deliverable d JOIN organisation o ON o.id = d.client_id "
                    "WHERE d.id = :id AND d.deleted_at IS NULL"
                ),
                {"id": str(deliverable_id)},
            )
        ).first()
        # RLS a pu masquer la ligne (hors périmètre) → 404 net, sans divulgation.
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        if row.statut != "genere" or not row.storage_key:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="not_ready")

        bucket = minio_client.evidence_bucket(row.code)
        await journal_append(
            session, event_type="deliverable.downloaded", actor_id=ctx.user_id,
            client_id=str(row.client_id), subject=str(deliverable_id), detail={},
        )

    url = minio_client.presign_download(bucket, row.storage_key, origin=minio_client.public_origin(request))
    return {
        "url": url,
        "expires_in": settings.presign_download_ttl_seconds,
        "filename": f"{row.titre}.pdf",
    }
