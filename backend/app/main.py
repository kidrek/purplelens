"""Point d'entrée de l'API (DAT §2.1).

Assemble l'application : middleware de contexte de sécurité (décode l'access token
et pose request.state.security_context), routeurs métier/preuves/auth/admin, et
sondes de santé. Aucune logique d'autorisation ici — tout passe par les dépendances
`require()` des routeurs et la RLS PostgreSQL.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import SecurityContextMiddleware
from app.api.routes import (
    admin,
    analytics,
    auth,
    deliverables,
    entities,
    evidence,
    exercises,
    reference,
    stix,
    vulnerabilities,
)
from app.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage : on se contente de vérifier la connectivité base (les migrations
    # sont appliquées hors-ligne par app_migrator, jamais par l'API).
    yield
    await engine.dispose()


app = FastAPI(
    title="Cockpit de Pilotage Purple Team — API",
    version="1.0.0",
    description=(
        "API multi-clients de pilotage Purple Team. Défense en profondeur : "
        "can() (matrice) → RLS PostgreSQL → chiffrement enveloppe → Object Lock + "
        "journal tamper-evident. Aucune décision d'autorisation côté client."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Le middleware décode le jeton et pose le contexte ; il n'autorise rien par lui-même.
app.add_middleware(SecurityContextMiddleware)

app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(evidence.router)
app.include_router(deliverables.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(stix.router)
app.include_router(reference.router)
app.include_router(vulnerabilities.router)
app.include_router(exercises.router)


@app.get("/api/health/live", tags=["health"])
async def live():
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
async def ready():
    """Prêt si la base répond. (MinIO/Vault/Redis sont vérifiés par leurs propres sondes.)"""
    checks = {"database": "unknown"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # pragma: no cover
        checks["database"] = "error"
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ok", "checks": checks}


@app.get("/api", tags=["health"])
async def root():
    return {
        "name": "purple-cockpit-api",
        "environment": settings.environment,
        "docs": "/api/docs",
    }
