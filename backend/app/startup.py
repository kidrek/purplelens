"""Démarrage applicatif en conteneur.

1. Attend que la base de données réponde (utile derrière docker-compose).
2. Crée les tables.
3. Peuple les données de démo si la base est vide (seed idempotent).

Lancé par l'entrypoint avant uvicorn.
"""

import sys
import time

from sqlalchemy import inspect, text

from app.core.database import Base, SessionLocal, engine
from app.models.models import Application  # noqa: F401 — enregistre les modèles


def wait_for_db(max_tries: int = 30, delay: float = 1.5) -> None:
    for attempt in range(1, max_tries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[startup] Base accessible (tentative {attempt}).")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] Base indisponible ({attempt}/{max_tries}) : {exc}")
            time.sleep(delay)
    print("[startup] Abandon : base inaccessible.", file=sys.stderr)
    sys.exit(1)


def init_schema() -> None:
    Base.metadata.create_all(bind=engine)
    print("[startup] Schéma vérifié / créé.")
    _migrate_technologies_cpe()


def _migrate_technologies_cpe() -> None:
    """Migration additive : ajoute la colonne technologies_cpe si absente."""
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("applications")]
    if "technologies_cpe" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE applications ADD COLUMN technologies_cpe TEXT DEFAULT ''"))
            conn.commit()
        print("[startup] Migration : colonne technologies_cpe ajoutée.")
    else:
        print("[startup] Colonne technologies_cpe déjà présente.")



def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        has_apps = db.query(Application).first() is not None
    finally:
        db.close()

    if has_apps:
        print("[startup] Données déjà présentes — pas de seed.")
        return

    print("[startup] Base vide — peuplement des données de démo…")
    from app.seed import run

    run()


if __name__ == "__main__":
    wait_for_db()
    init_schema()
    if "--seed" in sys.argv:
        seed_if_empty()
