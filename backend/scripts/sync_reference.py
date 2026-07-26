"""Synchronise les référentiels depuis les sources amont (CLI ops).

Catalogues couverts : ATT&CK multi-domaines, D3FEND, dictionnaires complets CWE/CAPEC,
groupes ATT&CK et acteurs MISP Galaxy. Recommandé pour la synchronisation initiale : le
téléchargement cumulé fait ~50 Mo, ce qui est plus sain en tâche d'administration qu'en
requête web. Idempotent (upsert par ext_id).

Usage :
    python -m scripts.sync_reference            # tous les catalogues synchronisables
    python -m scripts.sync_reference attack     # un seul catalogue
"""
from __future__ import annotations

import asyncio
import sys

from app.db.session import service_session
from app.reference.sync import SYNCABLE, SyncUnavailable, sync_catalog


async def main(catalogs: list[str]) -> int:
    targets = catalogs or list(SYNCABLE)
    rc = 0
    async with service_session("admin_service") as s:
        for cid in targets:
            if cid not in SYNCABLE:
                print(f"[sync] catalogue non synchronisable : {cid}")
                rc = 2
                continue
            try:
                n = await sync_catalog(s, cid)
                print(f"[sync] {cid} : {n} entrées depuis MITRE")
            except SyncUnavailable as exc:
                print(f"[sync] {cid} : source injoignable ({exc}) — inchangé")
                rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
