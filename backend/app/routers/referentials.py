"""
Router FastAPI pour les référentiels de sécurité.

GET  /api/referentials/status          → statut de tous les référentiels
GET  /api/referentials/mitre/status    → statut du catalogue ATT&CK
POST /api/referentials/mitre/sync      → synchronise le catalogue ATT&CK
GET  /api/referentials/{name}/entries  → recherche dans un référentiel
POST /api/referentials/{name}/sync     → synchronise un référentiel
POST /api/referentials/sync-all        → synchronise tous les référentiels
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.referentials import get_status, search_entries, sync_referential
from app.services.mitre_catalog import sync_mitre_catalog, get_mitre_status

router = APIRouter(prefix="/referentials", tags=["referentials"])

VALID_NAMES = {"owasp", "cwe", "capec", "cpe"}


@router.get("/status")
def referentials_status(db: Session = Depends(get_db)):
    return get_status(db)


@router.get("/mitre/status")
def mitre_status(db: Session = Depends(get_db)):
    """Statut du catalogue ATT&CK Enterprise."""
    return get_mitre_status(db)


@router.post("/mitre/sync")
def mitre_sync(db: Session = Depends(get_db)):
    """Télécharge et importe le catalogue ATT&CK Enterprise depuis MITRE/CTI (GitHub)."""
    try:
        result = sync_mitre_catalog(db)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(502, f"Erreur lors de la synchronisation ATT&CK : {exc}") from exc


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
    """Synchronise OWASP, CWE, CAPEC, CPE et le catalogue ATT&CK."""
    results = []
    errors = []
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
    return {"results": results, "errors": errors}
