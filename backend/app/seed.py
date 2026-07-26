"""Jeu de données de démonstration + référentiels minimaux (make seed).

Crée :
  - un compte admin local (Argon2id) pour la première connexion ;
  - un compte auditeur, un compte CISO et un compte operateur de démonstration ;
  - une organisation cliente et une organisation prestataire ;
  - quelques référentiels ATT&CK/D3FEND/OWASP.
Idempotent : comptes par email, organisations par `code` (index unique partiel
`uq_organisation_code`, cf. migration 0018), référentiels par clé naturelle — tous en
ON CONFLICT DO NOTHING.
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
    ATT&CK Groups, MISP Actors). Idempotent.

    Si SEED_SYNC_ONLINE (défaut : activé), tente de tirer les catalogues complets depuis
    les sources amont MITRE dès le bootstrap, avec repli automatique sur le socle embarqué
    si Internet est indisponible — même logique que « Tout synchroniser ». Sinon, charge
    uniquement le socle embarqué (installs air-gap / CI rapide)."""
    from app.reference.sync import sync_all_catalogs

    async with service_session("admin_service") as session:
        result = await sync_all_catalogs(session, prefer_online=settings.seed_sync_online)
    total = sum(r["entries"] for r in result.values())
    up = sum(1 for r in result.values() if r["source"] == "upstream")
    fb = sum(1 for r in result.values() if r["source"] == "fallback")
    emb = sum(1 for r in result.values() if r["source"] == "embedded")
    print(
        f"[seed] référentiels : {total} entrées chargées ({len(result)} catalogues) — "
        f"upstream={up} fallback={fb} embedded={emb}"
    )


async def seed_org_and_users() -> tuple[str, str]:
    # Organisations démo : upsert idempotent par `code` (cible = index unique partiel
    # uq_organisation_code, cf. migration 0018). GLOBEX illustre le rôle `operateur`
    # (prestataire pilotant PLUSIEURS clients) et teste le cloisonnement multi-clients.
    # On NE réutilise PAS un uuid généré ici : sur une base déjà seedée, le ON CONFLICT ne
    # réinsère rien et un uuid neuf serait un id fantôme — les comptes démo seraient alors
    # scoppés à une organisation inexistante. On résout donc l'id CANONIQUE par `code`.
    org_codes = ["ACME", "GLOBEX", "PRESTA"]
    async with service_session("admin_service") as session:
        for nom, code, secteur, role in (
            ("ACME Corp (démo)", "ACME", "nace_c", "client"),
            ("Globex SA (démo)", "GLOBEX", "nace_j", "client"),
            ("Prestataire Purple", "PRESTA", "nace_m", "prestataire"),
        ):
            await session.execute(
                text(
                    "INSERT INTO organisation (nom, code, role, secteur, tlp_defaut, statut) "
                    "VALUES (:n, :c, :r, :s, 'AMBER', 'actif') "
                    "ON CONFLICT (code) WHERE deleted_at IS NULL DO NOTHING"
                ),
                {"n": nom, "c": code, "r": role, "s": secteur},
            )

        async def _org_id(code: str) -> str:
            res = await session.execute(
                text("SELECT id FROM organisation WHERE code = :c AND deleted_at IS NULL LIMIT 1"),
                {"c": code},
            )
            return str(res.scalar_one())

        client_id = await _org_id("ACME")
        client2_id = await _org_id("GLOBEX")
    print(f"[seed] organisations clientes ACME ({client_id}) et GLOBEX ({client2_id}) prêtes")

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
    operateur_pw = settings.seed_operateur_password or settings.seed_default_password

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
        # Prestataire multi-clients « super-utilisateur métier » (rôle operateur).
        # Scoppé ici aux DEUX clients démo (ACME + GLOBEX) pour illustrer le profil
        # prestataire ; en usage réel l'admin lui rattache la liste des clients servis
        # (client_scope) — jamais global.
        await session.execute(
            text(
                """
                INSERT INTO app_user (id, email, display_name, role, client_scope, status,
                                      mfa_enrolled, password_hash, created_at, updated_at)
                VALUES (gen_random_uuid(), 'operateur@purple.local', 'Opérateur Démo',
                        'operateur', CAST(:scope AS uuid[]), 'active', false, :pw,
                        now(), now())
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"scope": [client_id, client2_id], "pw": hash_password(operateur_pw)},
        )
    print("[seed] comptes admin / auditeur / ciso / operateur créés.")
    # On n'imprime JAMAIS un mot de passe personnalisé dans les logs. On rappelle
    # seulement les identifiants quand le défaut « à changer » est resté en place.
    if {admin_pw, auditeur_pw, ciso_pw, operateur_pw} == {"ChangeMe!2026"}:
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
