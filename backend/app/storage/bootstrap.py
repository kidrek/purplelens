"""Amorçage de l'infrastructure de stockage/chiffrement (à lancer après `make up`).

Idempotent : crée le bucket de quarantaine, active le moteur transit Vault et les
politiques minimales, et provisionne un bucket par organisation existante (avec
Object Lock — impératif à la création, ne s'active pas a posteriori). Peut être
relancé à tout moment pour rattraper les organisations créées avant ce script
(bucket manquant → erreurs NoSuchBucket sur les livrables/preuves de ce client).
"""
from __future__ import annotations

import asyncio
import sys

from app.config import settings
from app.storage import minio_client


def ensure_vault_transit() -> None:
    """Active le moteur transit s'il ne l'est pas déjà (KEK par client ensuite)."""
    import hvac

    client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
    mounts = client.sys.list_mounted_secrets_engines()["data"]
    mount_path = f"{settings.vault_transit_mount}/"
    if mount_path not in mounts:
        client.sys.enable_secrets_engine(
            backend_type="transit", path=settings.vault_transit_mount
        )
        print(f"[vault] moteur transit activé sur {settings.vault_transit_mount}")
    else:
        print("[vault] moteur transit déjà présent")


async def _existing_org_codes() -> list[str]:
    """Codes de toutes les organisations déjà en base (schéma peut ne pas encore
    exister lors du tout premier `make init`, avant `make migrate` : on l'ignore
    silencieusement dans ce cas, `make bootstrap`/un ré-appel suffira ensuite)."""
    from sqlalchemy import text

    from app.db.session import service_session

    try:
        async with service_session("admin_service") as session:
            rows = await session.execute(text("SELECT code FROM organisation"))
            return [r[0] for r in rows if r[0]]
    except Exception as exc:
        print(f"[minio] organisations non lues ({exc}) — schéma pas encore migré ? "
              f"seul le bucket de quarantaine sera créé.")
        return []


def ensure_minio(client_codes: list[str] | None = None) -> None:
    codes = client_codes if client_codes is not None else asyncio.run(_existing_org_codes())
    minio_client.ensure_buckets(codes)
    print(f"[minio] quarantaine + {len(codes)} bucket(s) client prêts"
          + (f" ({', '.join(codes)})" if codes else ""))


def main() -> int:
    try:
        ensure_vault_transit()
    except Exception as exc:  # pragma: no cover
        print(f"[vault] AVERTISSEMENT : {exc}", file=sys.stderr)
    try:
        ensure_minio()
    except Exception as exc:  # pragma: no cover
        print(f"[minio] AVERTISSEMENT : {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
