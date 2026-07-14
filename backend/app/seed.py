"""Jeu de données de démonstration + référentiels minimaux (make seed).

Crée :
  - un compte admin local (Argon2id) pour la première connexion ;
  - un compte auditeur et un compte CISO de démonstration ;
  - une organisation cliente et une organisation prestataire ;
  - quelques référentiels ATT&CK/D3FEND/OWASP.
Idempotent sur l'email/slug (ON CONFLICT DO NOTHING).
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import text

from app.config import settings
from app.db.session import auth_session, service_session
from app.security.passwords import hash_password

# Référentiels de base (le seed complet viendrait d'un import STIX/MITRE).


async def seed_reference() -> None:
    """Charge tous les catalogues de référence (ATT&CK, D3FEND, OWASP, CWE, CAPEC,
    ATT&CK Groups, MISP Actors) depuis le socle embarqué — mêmes données que la page
    Paramètres. Idempotent."""
    from app.reference.catalogs import CATALOGS, import_catalog

    async with service_session("admin_service") as session:
        total = 0
        for cat in CATALOGS:
            total += await import_catalog(session, cat["id"])
    print(f"[seed] référentiels : {total} entrées chargées ({len(CATALOGS)} catalogues)")


async def seed_org_and_users() -> tuple[str, str]:
    client_id = str(uuid.uuid4())
    org_codes = ["ACME", "PRESTA"]
    async with service_session("admin_service") as session:
        await session.execute(
            text(
                "INSERT INTO organisation (id, nom, code, role, tlp_defaut, statut, "
                "created_at, updated_at) VALUES (:id, :n, :c, 'client', 'AMBER', 'actif', "
                "now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": client_id, "n": "ACME Corp (démo)", "c": "ACME"},
        )
        await session.execute(
            text(
                "INSERT INTO organisation (id, nom, code, role, tlp_defaut, statut, "
                "created_at, updated_at) VALUES (gen_random_uuid(), 'Prestataire Purple', "
                "'PRESTA', 'prestataire', 'AMBER', 'actif', now(), now()) "
                "ON CONFLICT DO NOTHING"
            )
        )
    print(f"[seed] organisation cliente ACME créée ({client_id})")

    # Bucket MinIO par organisation, AVEC Object Lock (impératif à la création,
    # cf. storage/minio_client.py). Sans cet appel, toute génération de livrable
    # ou dépôt de preuve pour ces organisations échoue avec NoSuchBucket.
    try:
        from app.storage import minio_client

        minio_client.ensure_buckets(org_codes)
        print(f"[seed] bucket(s) MinIO prêt(s) pour : {', '.join(org_codes)}")
    except Exception as exc:  # pragma: no cover
        print(f"[seed] ⚠ provisioning MinIO échoué ({exc}) — relancer "
              f"`python -m app.storage.bootstrap` une fois MinIO disponible.")

    # Mots de passe des comptes de démonstration, lus depuis .env (jamais figés en
    # dur). Chaque compte peut avoir le sien ; à défaut, SEED_DEFAULT_PASSWORD.
    admin_pw = settings.seed_admin_password or settings.seed_default_password
    auditeur_pw = settings.seed_auditeur_password or settings.seed_default_password
    ciso_pw = settings.seed_ciso_password or settings.seed_default_password

    admin_id = str(uuid.uuid4())
    async with auth_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO app_user (id, email, display_name, role, client_scope, status,
                                      mfa_enrolled, password_hash, created_at, updated_at)
                VALUES (:id, 'admin@purple.local', 'Admin Démo', 'admin', '{}', 'active',
                        false, :pw, now(), now())
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"id": admin_id, "pw": hash_password(admin_pw)},
        )
        await session.execute(
            text(
                """
                INSERT INTO app_user (id, email, display_name, role, client_scope, status,
                                      mfa_enrolled, password_hash, created_at, updated_at)
                VALUES (gen_random_uuid(), 'auditeur@purple.local', 'Auditeur Démo',
                        'auditeur', CAST(:scope AS uuid[]), 'active', false, :pw,
                        now(), now())
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"scope": [client_id], "pw": hash_password(auditeur_pw)},
        )
        await session.execute(
            text(
                """
                INSERT INTO app_user (id, email, display_name, role, client_scope, status,
                                      mfa_enrolled, password_hash, created_at, updated_at)
                VALUES (gen_random_uuid(), 'ciso@purple.local', 'CISO Démo', 'ciso',
                        CAST(:scope AS uuid[]), 'active', false, :pw, now(), now())
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"scope": [client_id], "pw": hash_password(ciso_pw)},
        )
    print("[seed] comptes admin / auditeur / ciso créés.")
    # On n'imprime JAMAIS un mot de passe personnalisé dans les logs. On rappelle
    # seulement les identifiants quand le défaut « à changer » est resté en place.
    if {admin_pw, auditeur_pw, ciso_pw} == {"ChangeMe!2026"}:
        print("[seed] ⚠ mots de passe par défaut (ChangeMe!2026) — À CHANGER via .env "
              "(SEED_*_PASSWORD) avant tout usage réel.")
    return client_id, admin_id


async def seed_corpus() -> None:
    """Charge la bibliothèque méthodologique (corpus de la maquette, embarqué dans
    le produit sous app/data/corpus.json). Idempotent : clé naturelle = slug ;
    ON CONFLICT met à jour le contenu (le corpus évolue avec le produit)."""
    import json
    from pathlib import Path

    path = Path(__file__).parent / "data" / "corpus.json"
    if not path.is_file():
        print("[seed] corpus.json absent — bibliothèque non chargée")
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    async with service_session("admin_service") as session:
        for r in rows:
            await session.execute(
                text(
                    """
                    INSERT INTO corpus_article
                      (id, slug, nature, profils, titre_fr, titre_en, contenu,
                       controles_iso, gabarit, created_at, updated_at)
                    VALUES
                      (gen_random_uuid(), :slug, :nature, CAST(:profils AS jsonb),
                       :tfr, :ten, CAST(:contenu AS jsonb), CAST(:iso AS jsonb),
                       :gab, now(), now())
                    ON CONFLICT (slug) DO UPDATE SET
                      nature = EXCLUDED.nature, profils = EXCLUDED.profils,
                      titre_fr = EXCLUDED.titre_fr, titre_en = EXCLUDED.titre_en,
                      contenu = EXCLUDED.contenu, controles_iso = EXCLUDED.controles_iso,
                      gabarit = EXCLUDED.gabarit, updated_at = now()
                    """
                ),
                {
                    "slug": r["slug"], "nature": r["nature"],
                    "profils": json.dumps(r["profils"]),
                    "tfr": r["titre_fr"], "ten": r.get("titre_en"),
                    "contenu": json.dumps(r["contenu"], ensure_ascii=False),
                    "iso": json.dumps(r["controles_iso"]),
                    "gab": bool(r.get("gabarit")),
                },
            )
    print(f"[seed] bibliothèque : {len(rows)} article(s) de corpus chargés/actualisés")


async def main() -> None:
    await seed_reference()
    await seed_corpus()
    await seed_org_and_users()
    print("[seed] terminé. Connectez-vous avec admin@purple.local")


if __name__ == "__main__":
    asyncio.run(main())
