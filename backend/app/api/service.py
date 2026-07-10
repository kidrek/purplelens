"""Service CRUD générique piloté par le registre d'entités.

Toute écriture passe par la liste blanche `spec.writable` : un champ non déclaré
est ignoré (jamais une erreur silencieuse d'assignation d'un attribut interne).
Les champs `spec.auto` sont réservés au serveur et calculés ici (noms auto-générés,
séquences annuelles, SLA dérivé). Le cloisonnement fin est garanti par la RLS
PostgreSQL (la session porte déjà le contexte) ; ce service ne fait donc pas de
filtrage client manuel — il fait confiance à la couche 2 de la défense en profondeur.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Date, DateTime, delete, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.registry import EntitySpec
from app.journal.chain import append as journal_append

_UTC = UTC


def _now() -> datetime:
    return datetime.now(tz=_UTC)




def _coerce_types(spec: EntitySpec, data: dict[str, Any]) -> dict[str, Any]:
    """Convertit les chaînes ISO vers les types Python attendus par le pilote.

    Le JSON n'a pas de type date : le frontend envoie '2026-09-01'. asyncpg exige un
    objet date/datetime pour les colonnes DATE/TIMESTAMP. On inspecte le type SQL de
    chaque colonne et on convertit ce qui doit l'être (les valeurs invalides sont
    laissées telles quelles — le serveur renverra alors une 4xx claire).
    """
    cols = sa_inspect(spec.model).columns
    out = dict(data)
    for key, value in data.items():
        if not isinstance(value, str) or key not in cols:
            continue
        coltype = cols[key].type
        try:
            if isinstance(coltype, DateTime):
                dt = datetime.fromisoformat(value)
                # Les inputs datetime-local du navigateur sont naïfs ('2026-07-05T14:30') ;
                # une colonne timestamptz exige un fuseau : on fixe UTC par convention.
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                out[key] = dt
            elif isinstance(coltype, Date):
                out[key] = date.fromisoformat(value)
        except ValueError:
            pass  # format invalide → laissé au serveur (422/400), jamais un 500 opaque
    return out


def _clean_payload(spec: EntitySpec, payload: dict[str, Any]) -> dict[str, Any]:
    """Ne garde que les champs autorisés en écriture (liste blanche stricte),
    puis convertit les types (dates ISO → objets Python)."""
    clean = {k: v for k, v in payload.items() if k in spec.writable}
    return _coerce_types(spec, clean)


async def _next_seq(
    session: AsyncSession, spec: EntitySpec, client_id: Any | None, *, ym: str | None = None
) -> tuple[str, int]:
    """Séquence mensuelle (cahier §A000.1 : NN = incrément mensuel, figé à la création).

    ``period`` = AAAAMM. Le compteur reste cloisonné par client : l'unicité du nom
    complet est de toute façon garantie par les codes client/app du suffixe."""
    period = ym or f"{_now().year}{_now().month:02d}"
    model = spec.model
    stmt = select(func.count()).select_from(model)
    if spec.client_field and client_id is not None:
        stmt = stmt.where(getattr(model, spec.client_field) == client_id)
    if hasattr(model, "period"):
        stmt = stmt.where(model.period == period)
    count = (await session.execute(stmt)).scalar_one()
    return period, int(count) + 1


def _slug_code(nom: str | None) -> str:
    """Repli du code court (cahier A000.2) : slug du premier mot du nom.
    Restreint à [a-z0-9-] car le code sert de segment de préfixe S3
    (`client/{code}/audit/…`), tronqué à 32 (contrainte colonne)."""
    import re
    import unicodedata

    words = (nom or "").strip().split()
    first = words[0] if words else ""
    ascii_ = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9-]", "", ascii_.lower())
    return (slug or "na")[:32]


def _apply_code_fallback(spec: EntitySpec, data: dict[str, Any], current_nom: str | None = None) -> None:
    """Si le code court est absent ou vide, le dérive du nom (jamais de NULL en base)."""
    if not spec.code_fallback:
        return
    if not data.get("code"):
        nom = data.get("nom") or current_nom
        data["code"] = _slug_code(nom)


# Préfixe de nom par catégorie d'audit (cahier §A000.1 / maquette auditTypeCode).
# purple_team conservé pour les audits hérités ; il n'est plus proposé à la saisie.
_AUDIT_TYPE_CODE = {"bas": "BAS", "pentest": "PEN", "purple_team": "PURPLE", "red_team": "REDTEAM"}


def _ym(value: Any) -> str:
    """AAAAMM à partir d'une date/chaîne ISO ; repli sur le mois courant (maquette _ym)."""
    s = value.isoformat() if hasattr(value, "isoformat") else str(value or "")
    if len(s) >= 7 and s[:4].isdigit() and s[5:7].isdigit():
        return s[:4] + s[5:7]
    now = _now()
    return f"{now.year}{now.month:02d}"


def _code_upper(value: str | None, *, maximum: int = 14) -> str:
    """Slug MAJUSCULE alphanumérique (maquette slugCode) : code métier lisible."""
    import re
    import unicodedata

    ascii_ = unicodedata.normalize("NFD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "", ascii_.upper())[:maximum]


async def _org_code(session: AsyncSession, org_id: Any) -> str:
    from app.models.business import Organisation

    if not org_id:
        return "—"
    row = (await session.execute(
        select(Organisation.code, Organisation.nom).where(Organisation.id == org_id)
    )).first()
    if not row:
        return "—"
    code, nom = row
    return _code_upper(code or (nom or "").split(" ")[0]) or "—"


async def _app_codes(session: AsyncSession, app_ids: Any) -> str:
    from app.models.business import Application

    ids = [a for a in (app_ids or [])]
    if not ids:
        return "—"
    rows = (await session.execute(
        select(Application.id, Application.code, Application.nom).where(Application.id.in_(ids))
    )).all()
    by_id = {r[0]: (r[1] or (r[2] or "").split(" ")[0]) for r in rows}
    parts = [_code_upper(by_id.get(i, "")) or "—" for i in ids]
    return "-".join(parts) or "—"


async def _auto_name(
    session: AsyncSession, spec: EntitySpec, data: dict[str, Any], period: str, seq: int
) -> str:
    """Identifiant métier auto-généré et figé (cahier §A000.1).

    Audit / Vulnérabilité → ``{TYPE}_{AAAAMM}-{NN}_{CLIENT}_{APP}`` ; le TYPE d'audit
    vient de la catégorie, sinon un préfixe d'entité. CLIENT/APP sont les codes courts
    (repli : premier mot du nom), en MAJUSCULES. Format aligné sur la maquette."""
    nn = f"{seq:02d}"
    client_id = data.get(spec.client_field) if spec.client_field else None
    if spec.entity == "audits":
        prefix = _AUDIT_TYPE_CODE.get(str(data.get("categorie") or "").lower(), "AUD")
    else:
        prefix = {"exercices": "PURPLE", "vulnerabilities": "VULN"}.get(
            spec.entity, spec.entity.upper()[:4]
        )
    # Audits et vulnérabilités portent le suffixe client_app ; les autres restent simples.
    if spec.entity in ("audits", "vulnerabilities"):
        cli = await _org_code(session, client_id)
        app = await _app_codes(session, data.get("applications"))
        return f"{prefix}_{period}-{nn}_{cli}_{app}"
    return f"{prefix}-{period}-{seq:03d}"


def _derive_sla(cvss: float | None) -> tuple[str | None, date | None]:
    """SLA dérivé du score CVSS (cahier §2 — VOC). Barème P1..P4 indicatif."""
    if cvss is None:
        return None, None
    from datetime import timedelta

    if cvss >= 9.0:
        niveau, jours = "P1", 7
    elif cvss >= 7.0:
        niveau, jours = "P2", 30
    elif cvss >= 4.0:
        niveau, jours = "P3", 90
    else:
        niveau, jours = "P4", 180
    return niveau, (_now().date() + timedelta(days=jours))


async def _apply_auto(session: AsyncSession, spec: EntitySpec, data: dict[str, Any]) -> None:
    """Renseigne les champs dérivés serveur avant insertion (mutation en place)."""
    if not spec.auto:
        return
    client_id = data.get(spec.client_field) if spec.client_field else None
    if {"period", "seq", "nom", "titre"} & set(spec.auto):
        # AAAAMM figé : issu de la date de début (audit) sinon du mois courant.
        ref_date = data.get("date_debut") if spec.entity == "audits" else None
        period, seq = await _next_seq(session, spec, client_id, ym=_ym(ref_date))
        if "period" in spec.auto:
            data["period"] = period
        if "seq" in spec.auto:
            data["seq"] = seq
        if "nom" in spec.auto:
            data["nom"] = await _auto_name(session, spec, data, period, seq)
        if "titre" in spec.auto:
            data["titre"] = await _auto_name(session, spec, data, period, seq)
    if "sla_niveau" in spec.auto:
        niveau, echeance = _derive_sla(data.get("cvss_score"))
        data["sla_niveau"] = niveau
        if "sla_echeance" in spec.auto:
            data["sla_echeance"] = echeance



async def list_entities(
    session: AsyncSession, spec: EntitySpec, *, limit: int, offset: int,
    filters: dict[str, Any] | None = None,
) -> tuple[list[Any], int]:
    model = spec.model
    stmt = select(model)
    if hasattr(model, "deleted_at"):
        stmt = stmt.where(model.deleted_at.is_(None))
    # Filtres : UNIQUEMENT sur les colonnes déclarées filterable (liste blanche).
    # Un filtre sur une colonne non autorisée est ignoré (jamais d'injection de critère).
    for key, value in (filters or {}).items():
        if key in spec.filterable and value is not None:
            col = getattr(model, key, None)
            if col is not None:
                stmt = stmt.where(col == value)
    order_col = getattr(model, spec.order_by, None)
    if order_col is not None:
        stmt = stmt.order_by(order_col)
    total = (await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return list(rows), int(total)


async def get_entity(session: AsyncSession, spec: EntitySpec, item_id: uuid.UUID) -> Any | None:
    obj = await session.get(spec.model, item_id)
    if obj is not None and getattr(obj, "deleted_at", None) is not None:
        return None
    return obj


async def _validate_audit_links(
    session: AsyncSession, data: dict[str, Any], *, client_id: Any | None
) -> None:
    """Règles d'intégrité de l'audit (cahier §2, entité Audits) — le serveur décide :
      - « applications ciblées ∈ client de l'audit » ;
      - auditeurs = ressources existantes de type humaine (pas de FK sur les ARRAY PG).
    Violation → 422 explicite, jamais un 500 de contrainte."""
    from app.models.business import Application, Ressource

    apps = data.get("applications")
    if apps:
        ids = [uuid.UUID(str(a)) for a in apps]
        rows = (await session.execute(
            select(Application.id, Application.client_id).where(Application.id.in_(ids))
        )).all()
        found = {r[0]: r[1] for r in rows}
        missing = [str(i) for i in ids if i not in found]
        if missing:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="unknown_application")
        if client_id is not None:
            cid = uuid.UUID(str(client_id))
            if any(owner != cid for owner in found.values()):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail="application_not_in_audit_client")

    auditeurs = data.get("auditeurs")
    if auditeurs:
        ids = [uuid.UUID(str(a)) for a in auditeurs]
        rows = (await session.execute(
            select(Ressource.id, Ressource.type).where(Ressource.id.in_(ids))
        )).all()
        found = {r[0]: r[1] for r in rows}
        if len(found) != len(set(ids)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="unknown_auditeur")
        if any(t != "humaine" for t in found.values()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="auditeur_not_human_resource")


async def _validate_vuln_audit_link(
    session: AsyncSession, data: dict[str, Any], *, client_id: Any | None
) -> None:
    """Règle d'intégrité (cahier « constats » Vulnérabilités) : l'audit lié à une
    vulnérabilité, s'il est renseigné, doit appartenir au même client qu'elle —
    même logique que « applications ∈ client de l'audit » ci-dessus, en miroir."""
    from app.models.business import Audit

    audit_id = data.get("audit_id")
    if not audit_id:
        return
    aid = uuid.UUID(str(audit_id))
    row = (await session.execute(
        select(Audit.client_id).where(Audit.id == aid)
    )).first()
    if row is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_audit")
    if client_id is not None and row[0] != uuid.UUID(str(client_id)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="audit_not_in_vulnerability_client")


def _apply_d3fend_auto(spec: EntitySpec, data: dict[str, Any]) -> None:
    """Dérive `d3fend` depuis `techniques` (cahier « constats » : les contre-mesures
    D3FEND ne sont plus choisies à la main, elles sont ajoutées automatiquement en
    lien avec les techniques ATT&CK sélectionnées — Vulnérabilités et Scénarios).
    N'agit que si `techniques` fait partie de la requête (création, ou modification
    qui touche ce champ) ; sinon on laisse la valeur existante intacte."""
    if spec.entity not in ("vulnerabilities", "scenarios"):
        return
    if "techniques" not in data:
        return
    from app.reference.attack_d3fend import suggest_d3fend

    data["d3fend"] = suggest_d3fend(data.get("techniques") or [])


def _derive_scenario_techniques_from_steps(data: dict[str, Any], payload: dict[str, Any]) -> None:
    """Dérive `techniques` (scénarios) depuis les étapes offensives du payload brut
    (`etapes`, hors liste blanche `writable` du scénario — les étapes vivent dans la
    table scenario_step, synchronisée par _sync_scenario_steps ci-dessous). Cahier
    §A00.1 : le scénario n'est plus une liste plate de techniques mais une chaîne
    d'étapes ; `techniques` (couverture ATT&CK, export STIX, D3FEND auto) en est dérivé.
    """
    steps = payload.get("etapes")
    if steps is None:
        return  # champ absent de la requête : ne touche pas à techniques/d3fend existants
    seen: list[str] = []
    for step in steps:
        tech = (step or {}).get("technique") if isinstance(step, dict) else None
        if tech and tech not in seen:
            seen.append(tech)
    data["techniques"] = seen


async def _sync_scenario_steps(
    session: AsyncSession, scenario_id: uuid.UUID, steps_payload: list | None
) -> None:
    """Remplace intégralement les étapes offensives d'un scénario (delete-then-insert —
    plus simple et sûr qu'un diff fin pour un sous-formulaire de quelques lignes
    réordonnables). `steps_payload is None` (clé absente) laisse les étapes existantes
    intactes ; `[]` les vide explicitement."""
    from app.models.business import ScenarioStep

    if steps_payload is None:
        return
    await session.execute(delete(ScenarioStep).where(ScenarioStep.scenario_id == scenario_id))
    for i, step in enumerate(steps_payload):
        if not isinstance(step, dict) or not step.get("technique"):
            continue
        session.add(ScenarioStep(
            scenario_id=scenario_id, ordre=i,
            technique=step.get("technique"),
            tactique=step.get("tactique"),
            commande=step.get("commande"),
            description=step.get("description"),
        ))
    await session.flush()


async def create_entity(
    session: AsyncSession, spec: EntitySpec, payload: dict[str, Any], *, actor_id: str | None
) -> Any:
    data = _clean_payload(spec, payload)
    await _apply_auto(session, spec, data)
    _apply_code_fallback(spec, data)  # cahier A000.2 — code optionnel, repli slug
    if spec.entity == "scenarios":
        _derive_scenario_techniques_from_steps(data, payload)
    _apply_d3fend_auto(spec, data)
    if spec.entity == "audits":
        await _validate_audit_links(session, data, client_id=data.get("client_id"))
    if spec.entity == "vulnerabilities":
        await _validate_vuln_audit_link(session, data, client_id=data.get("client_id"))
    obj = spec.model(**data)
    session.add(obj)
    await session.flush()  # obtient l'id sans clore la transaction (journal chaîné ensuite)
    if spec.entity == "scenarios":
        await _sync_scenario_steps(session, obj.id, payload.get("etapes"))
    await journal_append(
        session,
        event_type=f"{spec.entity}.create",
        actor_id=actor_id,
        detail={"entity": spec.entity, "id": str(obj.id)},
    )
    return obj


async def update_entity(
    session: AsyncSession, spec: EntitySpec, obj: Any, payload: dict[str, Any], *, actor_id: str | None
) -> Any:
    data = _clean_payload(spec, payload)
    # Un code vidé à l'édition est re-dérivé du nom (jamais de NULL en base).
    if "code" in data:
        _apply_code_fallback(spec, data, current_nom=getattr(obj, "nom", None))
    if spec.entity == "audits":
        await _validate_audit_links(
            session, data, client_id=data.get("client_id") or getattr(obj, "client_id", None)
        )
    if spec.entity == "vulnerabilities":
        await _validate_vuln_audit_link(
            session, data, client_id=data.get("client_id") or getattr(obj, "client_id", None)
        )
    if spec.entity == "scenarios":
        _derive_scenario_techniques_from_steps(data, payload)
    _apply_d3fend_auto(spec, data)
    # Les champs auto (noms figés, séquences, SLA) ne sont jamais réécrits par le client.
    for field_name, value in data.items():
        if field_name in spec.auto:
            continue
        setattr(obj, field_name, value)
    if hasattr(obj, "updated_at"):
        obj.updated_at = _now()
    if spec.entity == "scenarios":
        # _sync_scenario_steps exécute un DELETE brut sur une autre table : la session
        # autoflush avant de l'exécuter, ce qui envoie l'UPDATE du scénario et EXPIRE
        # ensuite ses attributs. updated_at doit donc déjà être posé (ci-dessus) — y
        # toucher après coup nécessiterait une relecture async impossible depuis un
        # accès synchrone (hasattr) et fait planter la session (MissingGreenlet).
        await _sync_scenario_steps(session, obj.id, payload.get("etapes"))
    await journal_append(
        session,
        event_type=f"{spec.entity}.update",
        actor_id=actor_id,
        detail={"entity": spec.entity, "id": str(obj.id), "fields": sorted(data.keys())},
    )
    return obj


async def delete_entity(
    session: AsyncSession, spec: EntitySpec, obj: Any, *, actor_id: str | None
) -> None:
    """Suppression logique quand le modèle la supporte, sinon physique."""
    if hasattr(obj, "deleted_at"):
        obj.deleted_at = _now()
    else:
        await session.delete(obj)
    await journal_append(
        session,
        event_type=f"{spec.entity}.delete",
        actor_id=actor_id,
        detail={"entity": spec.entity, "id": str(obj.id)},
    )
