from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import applications, audits, cti, dashboard

# Crée les tables (en MVP ; en prod : Alembic migrations)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=f"{settings.app_name} API",
    description="Source de vérité des exercices Purple Team — "
    "CTI → Scénario → Audit → Vulnérabilité → Détection → Réaction → Couverture ATT&CK.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (applications.router, cti.router, audits.router, dashboard.router):
    app.include_router(r, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"app": settings.app_name, "docs": "/docs", "status": "ok"}
