"""
Router FastAPI pour les référentiels de sécurité.

GET  /api/referentials/status          → statut de tous les référentiels
GET  /api/referentials/{name}/entries  → recherche dans un référentiel
POST /api/referentials/{name}/sync     → synchronise un référentiel depuis sa source
POST /api/referentials/sync-all        → synchronise tous les référentiels
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.referentials import get_status, search_entries, sync_referential

router = APIRouter(prefix="/referentials", tags=["referentials"])

VALID_NAMES = {"owasp", "cwe", "capec"}


@router.get("/status")
def referentials_status(db: Session = Depends(get_db)):
    """Retourne les métadonnées de chaque référentiel stocké en base."""
    return get_status(db)


@router.get("/{name}/entries")
def referential_entries(
    name: str,
    q: str = Query("", min_length=0),
    limit: int = Query(15, le=50),
    db: Session = Depends(get_db),
):
    """
    Recherche dans les entrées d'un référentiel.
    Retourne au plus `limit` résultats correspondant à `q`.
    """
    if name not in VALID_NAMES:
        raise HTTPException(400, f"Référentiel inconnu : {name}. Valeurs : {sorted(VALID_NAMES)}")
    if not q or len(q.strip()) < 1:
        return []
    return search_entries(name, q.strip(), db, limit)


@router.post("/{name}/sync")
def sync_one(name: str, db: Session = Depends(get_db)):
    """
    Télécharge et importe la dernière version d'un référentiel.
    Remplace toutes les entrées existantes du référentiel concerné.
    """
    if name not in VALID_NAMES:
        raise HTTPException(400, f"Référentiel inconnu : {name}. Valeurs : {sorted(VALID_NAMES)}")
    try:
        result = sync_referential(name, db)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(502, f"Erreur lors de la synchronisation de {name} : {exc}") from exc


@router.post("/sync-all")
def sync_all(db: Session = Depends(get_db)):
    """Synchronise tous les référentiels en séquence."""
    results = []
    errors = []
    for name in ("owasp", "cwe", "capec"):
        try:
            results.append(sync_referential(name, db))
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})
    return {"results": results, "errors": errors}
