"""Import des données de la maquette de référence (make import-maquette).

La maquette Alpine.js (audit-tracker) expose un objet `COLLECTIONS`. Ce script
consomme un export JSON de ces collections et alimente les tables métier via le
rôle de service. Il NE court-circuite PAS le sas : les preuves ne sont pas importées
ici (elles suivent le flux d'ingestion normal), seules les métadonnées structurées
le sont.

Usage :
    python -m app.import_maquette export.json
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import text

from app.db.session import service_session

# Correspondance clé de collection maquette → table cible et colonnes retenues.
# On importe le référentiel client d'abord (pour résoudre les client_id).
_ORDER = [
    "organisations",
    "applications",
    "threatScenarios",
    "audits",
    "vulnerabilities",
    "purpleExercises",
]


async def _import_organisations(session, items: list[dict]) -> dict[str, str]:
    """Renvoie une table de correspondance code/nom → id inséré."""
    mapping: dict[str, str] = {}
    for it in items:
        new_id = str(uuid.uuid4())
        code = it.get("code") or (it.get("nom", "ORG")[:8].upper())
        await session.execute(
            text(
                "INSERT INTO organisation (id, nom, code, role, tlp_defaut, statut, "
                "secteur, created_at, updated_at) VALUES (:id, :n, :c, :r, :tlp, 'actif', "
                ":sec, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {
                "id": new_id, "n": it.get("nom", "Organisation"), "c": code,
                "r": it.get("role", "client"), "tlp": it.get("tlp", "AMBER"),
                "sec": it.get("secteur"),
            },
        )
        mapping[code] = new_id
        if it.get("id"):
            mapping[str(it["id"])] = new_id
    return mapping


async def _import_applications(session, items: list[dict], orgs: dict[str, str]) -> None:
    for it in items:
        client_id = orgs.get(str(it.get("clientId"))) or next(iter(orgs.values()), None)
        if client_id is None:
            continue
        await session.execute(
            text(
                "INSERT INTO application (id, client_id, nom, code, criticite, exposition, "
                "tlp, statut, created_at, updated_at) VALUES (gen_random_uuid(), :c, :n, "
                ":code, :crit, :exp, 'AMBER', 'actif', now(), now())"
            ),
            {
                "c": client_id, "n": it.get("nom", "Application"),
                "code": it.get("code", "APP"), "crit": it.get("criticite"),
                "exp": it.get("exposition"),
            },
        )


async def _import_scenarios(session, items: list[dict]) -> None:
    import json

    for it in items:
        # Techniques ATT&CK du scénario (TTP) — indispensables au panneau TTP du drawer
        # d'audit et à l'export STIX. La maquette les porte sous `techniques`.
        techniques = it.get("techniques") or []
        await session.execute(
            text(
                "INSERT INTO scenario (id, nom, objectif, acteur_emule, credibilite, "
                "techniques, tlp, pap, created_at, updated_at) VALUES (gen_random_uuid(), "
                ":n, :o, :a, :cred, CAST(:tech AS jsonb), 'AMBER', 'AMBER', now(), now())"
            ),
            {
                "n": it.get("nom", "Scénario"), "o": it.get("objectif"),
                "a": it.get("acteurEmule") or it.get("acteur"),
                "cred": it.get("credibilite"),
                "tech": json.dumps(techniques),
            },
        )


async def _import_audits(session, items: list[dict], orgs: dict[str, str]) -> None:
    for i, it in enumerate(items, start=1):
        client_id = orgs.get(str(it.get("clientId"))) or next(iter(orgs.values()), None)
        if client_id is None:
            continue
        await session.execute(
            text(
                "INSERT INTO audit (id, client_id, nom, categorie, statut, tlp, period, seq, "
                "created_at, updated_at) VALUES (gen_random_uuid(), :c, :n, :cat, :st, 'AMBER', "
                ":p, :s, now(), now())"
            ),
            {
                "c": client_id,
                "n": it.get("nom") or f"AUD-{2026}-{i:03d}",
                "cat": it.get("categorie", "Purple"),
                "st": it.get("statut", "planifie"), "p": "2026", "s": i,
            },
        )


async def _import_vulnerabilities(session, items: list[dict], orgs: dict[str, str]) -> None:
    for i, it in enumerate(items, start=1):
        client_id = orgs.get(str(it.get("clientId"))) or next(iter(orgs.values()), None)
        if client_id is None:
            continue
        await session.execute(
            text(
                "INSERT INTO vulnerability (id, client_id, titre, cve, severite, cvss_score, "
                "statut, tlp, period, seq, created_at, updated_at) VALUES (gen_random_uuid(), "
                ":c, :t, :cve, :sev, :cvss, :st, 'RED', '2026', :s, now(), now())"
            ),
            {
                "c": client_id, "t": it.get("titre") or f"VULN-2026-{i:03d}",
                "cve": it.get("cve"), "sev": it.get("severite"),
                "cvss": it.get("cvssScore") or it.get("cvss"),
                "st": it.get("statut", "nouveau"), "s": i,
            },
        )


async def run(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    async with service_session("admin_service") as session:
        orgs = await _import_organisations(session, data.get("organisations", []))
        await _import_applications(session, data.get("applications", []), orgs)
        await _import_scenarios(session, data.get("threatScenarios", []))
        await _import_audits(session, data.get("audits", []), orgs)
        await _import_vulnerabilities(session, data.get("vulnerabilities", []), orgs)

    counts = {k: len(data.get(k, [])) for k in _ORDER}
    print(f"[import] terminé : {counts}")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m app.import_maquette <export.json>", file=sys.stderr)
        return 2
    asyncio.run(run(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
