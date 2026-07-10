"""Journal tamper-evident — chaînage de hachage côté serveur (spec backend v2 §6).

Chaque entrée scelle son contenu ET le hash de l'entrée précédente : altérer une
entrée passée casse la chaîne à partir d'elle. Immuable : aucun rôle n'a C/E/S
applicatif (INSERT only, garanti par trigger base). Alimenté par toutes les
décisions sensibles (auth, changements de rôle/scope, dépôt de preuve, legal hold,
crypto-shredding, exports).

Rappel doctrinal : tamper-EVIDENT n'est pas tamper-PROOF — la chaîne DÉTECTE ;
l'Object Lock et les triggers EMPÊCHENT (cahier §6quater.6).
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GENESIS = "0" * 64


def _canonical(payload: dict) -> str:
    """Sérialisation déterministe (clés triées, séparateurs compacts) — reproductible."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, entry: dict) -> str:
    material = f"{prev_hash}|{_canonical(entry)}".encode()
    return hashlib.sha256(material).hexdigest()


async def append(
    session: AsyncSession,
    *,
    event_type: str,
    actor_id: str | None,
    actor_label: str | None = None,
    client_id: str | None = None,
    subject: str | None = None,
    detail: dict | None = None,
) -> str:
    """Ajoute une entrée chaînée et renvoie son id. INSERT only.

    Récupère le dernier hash sous verrou pour éviter les courses (une chaîne unique
    par serveur en v1 ; partitionnement par client possible plus tard).
    """
    row = (
        await session.execute(
            text("SELECT id, curr_hash FROM journal ORDER BY seq DESC LIMIT 1 FOR UPDATE")
        )
    ).first()
    prev_hash = row.curr_hash if row else GENESIS

    sealed_at = datetime.now(UTC)
    entry = {
        "event_type": event_type,
        "actor_id": actor_id,
        "actor_label": actor_label,
        "client_id": client_id,
        "subject": subject,
        "detail": detail or {},
        "at": sealed_at.isoformat(),
    }
    curr_hash = compute_hash(prev_hash, entry)

    result = await session.execute(
        text(
            """
            INSERT INTO journal
              (event_type, actor_id, actor_label, client_id, subject, detail,
               prev_hash, curr_hash, created_at)
            VALUES
              (:event_type, :actor_id, :actor_label, :client_id, :subject,
               CAST(:detail AS jsonb), :prev_hash, :curr_hash, :created_at)
            RETURNING id
            """
        ),
        {
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_label": actor_label,
            "client_id": client_id,
            "subject": subject,
            "detail": _canonical(entry["detail"]),
            "prev_hash": prev_hash,
            "curr_hash": curr_hash,
            "created_at": sealed_at,
        },
    )
    return str(result.scalar_one())


async def verify_chain(session: AsyncSession) -> tuple[bool, int | None]:
    """Recalcule la chaîne. Renvoie (intacte, seq_du_premier_défaut)."""
    rows = (
        await session.execute(
            text(
                "SELECT seq, event_type, actor_id, actor_label, client_id, subject, "
                "detail, prev_hash, curr_hash, created_at FROM journal ORDER BY seq ASC"
            )
        )
    ).all()
    prev = GENESIS
    for r in rows:
        entry = {
            "event_type": r.event_type,
            "actor_id": r.actor_id,
            "actor_label": r.actor_label,
            "client_id": r.client_id,
            "subject": r.subject,
            "detail": r.detail if isinstance(r.detail, dict) else json.loads(r.detail or "{}"),
            "at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else r.created_at,
        }
        # Double contrôle : (1) le chaînage (prev_hash) — détecte suppression/réordonnancement ;
        # (2) le recalcul de l'empreinte — détecte l'altération du CONTENU d'une entrée.
        if r.prev_hash != prev:
            return False, r.seq
        if compute_hash(prev, entry) != r.curr_hash:
            return False, r.seq
        prev = r.curr_hash
    return True, None
