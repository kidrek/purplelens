-- =============================================================================
-- schema_evidence.sql — DDL de référence du sous-système de preuves
-- Cahier §6quater.5 (modèle de données) · §6quater.6 (WORM deux étages)
-- Spec backend v2 §3.1 (matrice Preuves) · §3.3 (RLS)
--
-- Ce fichier est la SOURCE NORMATIVE des trois tables de preuves. La migration
-- Alembic l'exécute tel quel (op.execute) pour garantir zéro dérive.
-- =============================================================================

-- Extension pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Contexte de session RLS : helpers lisant les GUC posés par l'API ────────
-- L'API pose à chaque transaction :  SET LOCAL app.user_id / app.role / app.client_scope
CREATE OR REPLACE FUNCTION app_current_role() RETURNS text
  LANGUAGE sql STABLE AS $$ SELECT current_setting('app.role', true) $$;

CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS uuid
  LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
  $$;

-- client_scope : liste d'UUID séparés par des virgules. Vide => tous clients
-- (dans la limite du rôle). La politique l'implémente EXPLICITEMENT (jamais par absence).
CREATE OR REPLACE FUNCTION app_client_scope() RETURNS uuid[]
  LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
      NULLIF(current_setting('app.client_scope', true), '')::uuid[],
      ARRAY[]::uuid[]
    )
  $$;

-- Vrai si le client passé est visible selon le scope courant.
-- SÉCURITÉ : un contexte applicatif DOIT être établi (app.role posé). Une connexion
-- brute sur app_api, sans contexte, ne voit RIEN — sinon un scope « vide » (= tous
-- clients, pour un rôle multi-clients) serait indistinguable d'une absence de contexte.
-- Scope vide AVEC rôle posé = tous clients (dans la limite du rôle, appliquée côté API).
CREATE OR REPLACE FUNCTION app_client_visible(cid uuid) RETURNS boolean
  LANGUAGE sql STABLE AS $$
    SELECT
      NULLIF(current_setting('app.role', true), '') IS NOT NULL
      AND (
        cardinality(app_client_scope()) = 0
        OR cid = ANY (app_client_scope())
      )
  $$;

-- =============================================================================
-- audit_dek — la « frontière conteneur » : une DEK par audit, enveloppée
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_dek (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        uuid NOT NULL,
    client_id       uuid NOT NULL,                 -- dénormalisé : porte la RLS
    wrapped_dek     bytea,                          -- DEK enveloppée par la KEK client (Vault)
    kek_ref         text NOT NULL,                  -- référence de la KEK dans Vault
    kek_version     integer NOT NULL DEFAULT 1,
    status          text NOT NULL DEFAULT 'active'  -- active | rotated | destroyed
                    CHECK (status IN ('active','rotated','destroyed')),
    destroyed_at    timestamptz,
    destroyed_by    uuid,
    destroyed_reason text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- Une seule DEK active par audit
    CONSTRAINT audit_dek_wrapped_when_not_destroyed
      CHECK (status = 'destroyed' OR wrapped_dek IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS audit_dek_one_active
  ON audit_dek (audit_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS audit_dek_client ON audit_dek (client_id);

-- =============================================================================
-- evidence — une ligne par preuve
-- =============================================================================
CREATE TABLE IF NOT EXISTS evidence (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Rattachement (frontière)
    audit_id          uuid NOT NULL,
    client_id         uuid NOT NULL,                -- dénormalisé volontairement (RLS)
    finding_id        uuid,                          -- optionnels, cumulables
    audit_action_id   uuid,
    attack_step_id    uuid,
    -- Fichier
    original_filename text NOT NULL,
    declared_mime     text,                          -- déclaration HTTP (ne fait pas foi)
    detected_mime     text,                          -- magic bytes (fait foi)
    size_bytes        bigint,
    sha256_plaintext  char(64),                      -- fonde la custody (chaînée au journal)
    sha256_ciphertext char(64),                      -- contrôle d'intégrité sans déchiffrer
    -- Stockage
    bucket            text,
    object_key        text,
    thumbnail_key     text,
    -- Crypto
    dek_id            uuid REFERENCES audit_dek(id),
    nonce             bytea,                          -- 96 bits (12 octets) unique par objet
    encryption_alg    text DEFAULT 'AES-256-GCM',
    aad_fields        text DEFAULT 'id+audit_id+sha256_plaintext',
    -- Classification (TLP 2.0 / PAP / sensibilité)
    tlp               text DEFAULT 'RED'
                      CHECK (tlp IN ('RED','AMBER','AMBER+STRICT','GREEN','CLEAR')),
    pap               text DEFAULT 'RED'
                      CHECK (pap IN ('RED','AMBER','GREEN','WHITE')),
    contains_pii      boolean NOT NULL DEFAULT false,
    contains_secrets  boolean NOT NULL DEFAULT false,
    caption           text,
    context           jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {"host","tool","operator_note"}
    -- Custody
    ingest_status     text NOT NULL DEFAULT 'quarantined'
                      CHECK (ingest_status IN ('quarantined','scanning','stored','rejected')),
    rejected_reason   text,
    av_verdict        text,
    av_engine_version text,
    uploaded_by       uuid,
    uploaded_at       timestamptz NOT NULL DEFAULT now(),
    stored_at         timestamptz,
    journal_entry_id  uuid,
    -- Rétention
    retention_until   timestamptz,
    legal_hold        boolean NOT NULL DEFAULT false,
    object_lock_until timestamptz,
    -- Cycle de vie
    deleted_at        timestamptz,                   -- soft delete uniquement
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    -- Une preuve 'stored' est nécessairement complète
    CONSTRAINT evidence_stored_complete CHECK (
      ingest_status <> 'stored' OR (
        sha256_plaintext IS NOT NULL AND sha256_ciphertext IS NOT NULL AND
        bucket IS NOT NULL AND object_key IS NOT NULL AND
        dek_id IS NOT NULL AND nonce IS NOT NULL AND
        journal_entry_id IS NOT NULL AND stored_at IS NOT NULL
      )
    ),
    CONSTRAINT evidence_nonce_96bits CHECK (nonce IS NULL OR octet_length(nonce) = 12),
    CONSTRAINT evidence_object_unique UNIQUE (bucket, object_key)
);
CREATE INDEX IF NOT EXISTS evidence_audit    ON evidence (audit_id);
CREATE INDEX IF NOT EXISTS evidence_client   ON evidence (client_id);
CREATE INDEX IF NOT EXISTS evidence_finding  ON evidence (finding_id);
CREATE INDEX IF NOT EXISTS evidence_sha_plain ON evidence (sha256_plaintext);  -- détection doublons
CREATE INDEX IF NOT EXISTS evidence_status   ON evidence (ingest_status);

-- =============================================================================
-- evidence_access — qui a déchiffré quoi (refus compris)
-- =============================================================================
CREATE TABLE IF NOT EXISTS evidence_access (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id         uuid NOT NULL REFERENCES evidence(id),
    client_id           uuid NOT NULL,               -- dénormalisé (RLS)
    actor_user_id       uuid,
    actor_label         text,                         -- 'report_render', 'admin_audit'...
    purpose             text NOT NULL
                        CHECK (purpose IN ('view','report_render','export','admin_audit')),
    granted             boolean NOT NULL,             -- les refus sont tracés aussi
    denial_reason       text,
    presigned_expires_at timestamptz,
    ip                  inet,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_access_evidence ON evidence_access (evidence_id);
CREATE INDEX IF NOT EXISTS evidence_access_client   ON evidence_access (client_id);

-- =============================================================================
-- WORM étage BASE — trigger evidence_enforce_worm (cahier §6quater.6)
-- Une fois `stored`, les colonnes de custody sont figées. DELETE physique interdit.
-- =============================================================================
CREATE OR REPLACE FUNCTION evidence_enforce_worm() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'evidence: DELETE physique interdit (WORM) — utiliser deleted_at (soft delete)';
  END IF;

  -- Sur une preuve déjà scellée, les champs de custody sont immuables.
  IF OLD.ingest_status = 'stored' THEN
    IF NEW.sha256_plaintext  IS DISTINCT FROM OLD.sha256_plaintext
    OR NEW.sha256_ciphertext IS DISTINCT FROM OLD.sha256_ciphertext
    OR NEW.bucket            IS DISTINCT FROM OLD.bucket
    OR NEW.object_key        IS DISTINCT FROM OLD.object_key
    OR NEW.dek_id            IS DISTINCT FROM OLD.dek_id
    OR NEW.nonce             IS DISTINCT FROM OLD.nonce
    OR NEW.encryption_alg    IS DISTINCT FROM OLD.encryption_alg
    OR NEW.uploaded_by       IS DISTINCT FROM OLD.uploaded_by
    OR NEW.uploaded_at       IS DISTINCT FROM OLD.uploaded_at
    OR NEW.stored_at         IS DISTINCT FROM OLD.stored_at
    OR NEW.journal_entry_id  IS DISTINCT FROM OLD.journal_entry_id
    OR NEW.audit_id          IS DISTINCT FROM OLD.audit_id
    OR NEW.client_id         IS DISTINCT FROM OLD.client_id
    OR NEW.ingest_status     IS DISTINCT FROM OLD.ingest_status
    THEN
      RAISE EXCEPTION 'evidence: champ de custody immuable après scellement (WORM base)';
    END IF;
  END IF;

  NEW.updated_at := now();
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_evidence_worm ON evidence;
CREATE TRIGGER trg_evidence_worm
  BEFORE UPDATE OR DELETE ON evidence
  FOR EACH ROW EXECUTE FUNCTION evidence_enforce_worm();

-- audit_dek : seule transition autorisée hors création = crypto-shredding (→ destroyed).
CREATE OR REPLACE FUNCTION audit_dek_enforce() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'audit_dek: DELETE interdit (les empreintes/custody doivent survivre)';
  END IF;
  IF OLD.status = 'destroyed' THEN
    RAISE EXCEPTION 'audit_dek: une DEK détruite est immuable (crypto-shredding irréversible)';
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS trg_audit_dek_enforce ON audit_dek;
CREATE TRIGGER trg_audit_dek_enforce
  BEFORE UPDATE OR DELETE ON audit_dek
  FOR EACH ROW EXECUTE FUNCTION audit_dek_enforce();

-- =============================================================================
-- RLS — cloisonnement par client (spec v2 §3.3). FORCE pour que le rôle owner
-- lui-même y soit soumis lorsqu'il agit comme app_api.
-- =============================================================================
ALTER TABLE evidence         ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence         FORCE  ROW LEVEL SECURITY;
ALTER TABLE audit_dek        ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_dek        FORCE  ROW LEVEL SECURITY;
ALTER TABLE evidence_access  ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_access  FORCE  ROW LEVEL SECURITY;

-- evidence : visible/écrivable si le client est dans le scope (vide = tous).
DROP POLICY IF EXISTS evidence_rls ON evidence;
CREATE POLICY evidence_rls ON evidence
  USING (app_client_visible(client_id))
  WITH CHECK (app_client_visible(client_id));

DROP POLICY IF EXISTS evidence_access_rls ON evidence_access;
CREATE POLICY evidence_access_rls ON evidence_access
  USING (app_client_visible(client_id))
  WITH CHECK (app_client_visible(client_id));

-- audit_dek : les clés enveloppées ne sont JAMAIS lues par un humain (spec v2 §3.1 note ³).
-- Seuls les comptes de service (role in service roles) accèdent, dans la limite du scope.
DROP POLICY IF EXISTS audit_dek_rls ON audit_dek;
CREATE POLICY audit_dek_rls ON audit_dek
  USING (
    app_current_role() IN ('report_render','job_retention','job_integrity','admin_service')
    AND app_client_visible(client_id)
  )
  WITH CHECK (
    app_current_role() IN ('report_render','job_retention','job_integrity','admin_service')
    AND app_client_visible(client_id)
  );
