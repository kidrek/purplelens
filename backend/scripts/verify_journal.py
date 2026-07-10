"""Vérifie l'intégrité de la chaîne du journal d'audit (CLI d'exploitation).

Recalcule chaque empreinte : sortie 0 si la chaîne est intacte, 1 sinon (en indiquant le
rang de la première rupture). À intégrer à la supervision (exécution quotidienne).
"""
from __future__ import annotations

import asyncio

from app.db.session import service_session
from app.journal.chain import verify_chain


async def main() -> int:
    async with service_session("admin_service") as s:
        intact, break_at = await verify_chain(s)
    if intact:
        print("[journal] chaîne intacte")
        return 0
    print(f"[journal] RUPTURE détectée au rang {break_at}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
