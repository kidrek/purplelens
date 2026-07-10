"""Schéma initial : tables métier + sous-système de preuves + RLS + GRANT.

Ordre :
  1. extension pgcrypto (gen_random_uuid) ;
  2. DDL du sous-système de preuves (schema_evidence.sql) — fonctions RLS + audit_dek,
     evidence, evidence_access avec leurs politiques et triggers WORM ;
  3. création des tables métier & sécurité (metadata, hors tables de preuves déjà créées) ;
  4. RLS FORCÉE sur les tables cloisonnées métier (organisation via id, autres via client_id) ;
  5. journal immuable (trigger anti-UPDATE/DELETE) ;
  6. GRANT DML à app_api (jamais DDL).
"""
from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.models import Base, CLIENT_SCOPED_TABLES

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Tables de preuves : créées par schema_evidence.sql, PAS par metadata.create_all.
_EVIDENCE_TABLES = {"audit_dek", "evidence", "evidence_access"}

# Tables métier cloisonnées auxquelles CETTE migration applique la RLS
# (les tables de preuves ont déjà leur RLS via schema_evidence.sql).
_BUSINESS_SCOPED = [t for t in CLIENT_SCOPED_TABLES if t not in _EVIDENCE_TABLES]

# Colonne portant le cloisonnement quand ce n'est pas `client_id` :
#   organisation → sa propre clé primaire (elle EST le client) ;
#   ressource    → organisation_id (rattachement indirect).
_SCOPE_COLUMN = {"organisation": "id", "ressource": "organisation_id"}


def _schema_evidence_sql() -> str:
    # backend/migrations/versions/0001_initial.py → backend/sql/schema_evidence.sql
    root = Path(__file__).resolve().parents[2]
    return (root / "sql" / "schema_evidence.sql").read_text(encoding="utf-8")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Extension : créée en amont par 00-roles.sh (superuser). On échoue tôt et clair
    #    si elle manque, plutôt que de laisser un gen_random_uuid() casser plus loin.
    present = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto'")
    ).first()
    if present is None:
        raise RuntimeError(
            "extension pgcrypto absente — elle doit être créée par 00-roles.sh (superuser) "
            "avant la migration"
        )

    # 2. Sous-système de preuves (fonctions RLS + tables + triggers WORM)
    op.execute(_schema_evidence_sql())

    # 3. Tables métier & sécurité (on exclut les tables de preuves déjà créées)
    tables = [t for name, t in Base.metadata.tables.items() if name not in _EVIDENCE_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables)

    # 4. RLS forcée sur les tables métier cloisonnées.
    for table in _BUSINESS_SCOPED:
        col = _SCOPE_COLUMN.get(table, "client_id")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_rls ON {table}
              USING (app_client_visible({col}))
              WITH CHECK (app_client_visible({col}))
            """
        )

    # 5. Journal immuable : INSERT autorisé, UPDATE/DELETE interdits (tamper-evident).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION journal_no_mutation() RETURNS trigger
          LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'journal is append-only (tamper-evident)';
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER journal_immutable
          BEFORE UPDATE OR DELETE ON journal
          FOR EACH ROW EXECUTE FUNCTION journal_no_mutation();
        """
    )

    # 6. GRANT DML à app_api sur tout ce que possède app_migrator (RLS filtre les lignes).
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_api")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_api")


def downgrade() -> None:
    # Descente non prévue en production (données de preuves sous Object Lock).
    op.execute("DROP TRIGGER IF EXISTS journal_immutable ON journal")
    op.execute("DROP FUNCTION IF EXISTS journal_no_mutation()")
    for table in _BUSINESS_SCOPED:
        op.execute(f"DROP POLICY IF EXISTS {table}_rls ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    tables = [t for name, t in Base.metadata.tables.items() if name not in _EVIDENCE_TABLES]
    Base.metadata.drop_all(bind=op.get_bind(), tables=tables)
    op.execute("DROP TABLE IF EXISTS evidence_access, evidence, audit_dek CASCADE")
