"""
Router FastAPI pour les référentiels de sécurité.

GET  /api/referentials/status          → statut de tous les référentiels
GET  /api/referentials/mitre/status    → statut du catalogue ATT&CK
POST /api/referentials/mitre/sync      → synchronise le catalogue ATT&CK
GET  /api/referentials/{name}/entries  → recherche dans un référentiel
POST /api/referentials/{name}/sync     → synchronise un référentiel
POST /api/referentials/sync-all        → synchronise tous les référentiels
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.referentials import get_status, search_entries, sync_referential
from app.services.mitre_catalog import sync_mitre_catalog, get_mitre_status
from app.services.d3fend import import_d3fend, sync_d3fend, get_d3fend_status, get_d3fend_for_technique

router = APIRouter(prefix="/referentials", tags=["referentials"])

VALID_NAMES = {"owasp", "cwe", "capec", "cpe"}


@router.get("/status")
def referentials_status(db: Session = Depends(get_db)):
    return get_status(db)


@router.get("/mitre/status")
def mitre_status(db: Session = Depends(get_db)):
    """Statut du catalogue ATT&CK Enterprise."""
    return get_mitre_status(db)


@router.get("/mitre/search")
def mitre_search(
    q: str = Query("", min_length=0),
    limit: int = Query(12, le=50),
    subtechniques: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Recherche plein-texte dans le catalogue ATT&CK Enterprise.
    Retourne les techniques correspondant à q (mitre_id, name, tactic, description).
    Si le catalogue n'est pas synchronisé, retourne une liste vide.
    """
    from app.models.mitre_catalog import MitreTechnique
    from sqlalchemy import or_
    if not q or len(q.strip()) < 1:
        return []
    sq = f"%{q.strip().lower()}%"
    query = db.query(MitreTechnique).filter(
        or_(
            MitreTechnique.mitre_id.ilike(sq),
            MitreTechnique.name.ilike(sq),
            MitreTechnique.tactic.ilike(sq),
            MitreTechnique.description.ilike(sq),
        )
    )
    if not subtechniques:
        query = query.filter(MitreTechnique.is_subtechnique == False)  # noqa: E712
    rows = query.order_by(MitreTechnique.mitre_id).limit(limit).all()
    return [
        {
            "mitre_id":    r.mitre_id,
            "name":        r.name,
            "tactic":      r.tactic,
            "description": r.description[:200] if r.description else "",
            "is_subtechnique": r.is_subtechnique,
        }
        for r in rows
    ]


@router.post("/mitre/sync")
def mitre_sync(db: Session = Depends(get_db)):
    """Télécharge et importe le catalogue ATT&CK Enterprise depuis MITRE/CTI (GitHub)."""
    try:
        result = sync_mitre_catalog(db)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(502, f"Erreur lors de la synchronisation ATT&CK : {exc}") from exc


# ── D3FEND ────────────────────────────────────────────────────────────────────

@router.get("/d3fend/status")
def d3fend_status(db: Session = Depends(get_db)):
    """Statut du mapping D3FEND en base."""
    return get_d3fend_status(db)


@router.post("/d3fend/sync")
def d3fend_sync(db: Session = Depends(get_db)):
    """
    Télécharge et importe le catalogue D3FEND directement depuis d3fend.mitre.org/ontologies/d3fend.json.
    """
    try:
        result = sync_d3fend(db)
        return {"ok": True, **result}
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de la synchronisation D3FEND : {e}")


@router.post("/d3fend/import")
async def d3fend_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Importe le mapping D3FEND depuis un fichier JSON uploadé.
    Fichier attendu : d3fend-full-mappings.json téléchargé depuis d3fend.mitre.org.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Le fichier doit être au format JSON (.json).")
    try:
        raw = await file.read()
        result = import_d3fend(raw, db, filename=file.filename)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de l'import : {e}")


@router.get("/d3fend/{mitre_id}")
def d3fend_for_technique(mitre_id: str, db: Session = Depends(get_db)):
    """Retourne les contre-mesures D3FEND pour un T-code ATT&CK depuis la base."""
    return get_d3fend_for_technique(mitre_id, db)


# ── Référentiels génériques ───────────────────────────────────────────────────

@router.get("/{name}/entries")
def referential_entries(
    name: str,
    q: str = Query("", min_length=0),
    limit: int = Query(15, le=50),
    db: Session = Depends(get_db),
):
    if name not in VALID_NAMES:
        raise HTTPException(400, f"Référentiel inconnu : {name}.")
    if not q or len(q.strip()) < 1:
        return []
    return search_entries(name, q.strip(), db, limit)


@router.post("/{name}/sync")
def sync_one(name: str, db: Session = Depends(get_db)):
    if name not in VALID_NAMES:
        raise HTTPException(400, f"Référentiel inconnu : {name}.")
    try:
        result = sync_referential(name, db)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(502, f"Erreur lors de la synchronisation de {name} : {exc}") from exc


@router.post("/sync-all")
def sync_all(db: Session = Depends(get_db)):
    """
    Synchronise OWASP, CWE, CAPEC, CPE, ATT&CK et D3FEND automatiquement.
    """
    results = []
    errors  = []
    for name in ("owasp", "cwe", "capec", "cpe"):
        try:
            results.append(sync_referential(name, db))
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})
    # Catalogue ATT&CK
    try:
        results.append(sync_mitre_catalog(db))
    except Exception as exc:
        errors.append({"name": "mitre_attack", "error": str(exc)})
    # D3FEND — téléchargement automatique
    try:
        results.append(sync_d3fend(db))
    except Exception as exc:
        errors.append({"name": "d3fend", "error": str(exc)})
    return {
        "results": results,
        "errors":  errors,
    }
