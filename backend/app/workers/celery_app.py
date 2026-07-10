"""Application Celery (DAT §2.1 — traitements asynchrones).

Deux files :
  - `ingest` : sas d'ingestion des preuves (une preuve = une tâche, isolée) ;
  - `jobs`   : tâches planifiées (rétention/crypto-shredding, intégrité, chaîne).

Le worker tourne sous des rôles de service à périmètre minimal (job_retention,
job_integrity, report_render) — jamais un rôle interactif.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "purple_cockpit",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_default_queue="jobs",
    task_routes={
        "app.workers.tasks.ingest_evidence": {"queue": "ingest"},
        "app.workers.tasks.*": {"queue": "jobs"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # une preuve à la fois par worker ingest
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)

# Planification (beat) — cahier §6quater.5/.6.
celery_app.conf.beat_schedule = {
    "retention-sweep": {
        "task": "app.workers.tasks.retention_sweep",
        "schedule": crontab(hour=2, minute=0),  # nuit
    },
    "integrity-check": {
        "task": "app.workers.tasks.integrity_check",
        "schedule": crontab(hour=3, minute=0),
    },
    "journal-verify": {
        "task": "app.workers.tasks.journal_verify",
        "schedule": crontab(hour=3, minute=30),
    },
}

# Alias attendu par la ligne de commande du compose (`-A app.workers.celery_app.celery`).
celery = celery_app

# Import des tâches pour enregistrement.
from app.workers import tasks  # noqa: E402,F401
