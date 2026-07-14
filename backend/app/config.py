"""Configuration typée (pydantic-settings) — DAT §2.1.

Toute la configuration vient de l'environnement (.env en dev, secrets injectés en prod).
Aucun secret n'est codé en dur.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Général
    environment: str = Field("development", alias="ENVIRONMENT")
    public_host: str = Field("localhost", alias="PUBLIC_HOST")

    # Base de données (rôle app_api, NOBYPASSRLS)
    database_url: str = Field(
        "postgresql+asyncpg://app_api:api@postgres:5432/purple", alias="DATABASE_URL"
    )
    migration_database_url: str = Field(
        "postgresql+psycopg://app_migrator:migrator@postgres:5432/purple",
        alias="MIGRATION_DATABASE_URL",
    )

    # Redis / Celery
    redis_url: str = Field("redis://redis:6379/0", alias="REDIS_URL")

    # MinIO
    minio_endpoint: str = Field("minio:9000", alias="MINIO_ENDPOINT")
    minio_root_user: str = Field("minioadmin", alias="MINIO_ROOT_USER")
    minio_root_password: str = Field("minioadmin", alias="MINIO_ROOT_PASSWORD")
    # Préfixe de chemin sous lequel nginx expose MinIO (location /storage/, cf.
    # deploy/nginx/nginx.conf) — un choix de topologie, pas de host/port : ceux-ci
    # sont dérivés de la requête entrante (X-Forwarded-Host), jamais figés ici,
    # pour que les ports exposés restent librement personnalisables (EDGE_HTTPS_PORT).
    minio_public_path_prefix: str = Field("/storage", alias="MINIO_PUBLIC_PATH_PREFIX")
    # Région S3 : DOIT être fournie explicitement. Sinon minio-py tente de la
    # découvrir par un appel réseau au serveur avant de signer — impossible pour
    # le client "public" (configuré avec l'hôte du navigateur, injoignable depuis
    # le conteneur api). Avec la région fixée, la signature devient purement locale.
    minio_region: str = Field("us-east-1", alias="MINIO_REGION")
    minio_secure: bool = Field(False, alias="MINIO_SECURE")
    minio_quarantine_bucket: str = Field("quarantine", alias="MINIO_QUARANTINE_BUCKET")
    minio_evidence_bucket_prefix: str = Field("evidence", alias="MINIO_EVIDENCE_BUCKET_PREFIX")
    # Bucket WORM (Object Lock) recevant les ancres de tête de chaîne du journal.
    journal_anchor_bucket: str = Field("journal-anchor", alias="JOURNAL_ANCHOR_BUCKET")

    # Vault (transit engine)
    vault_addr: str = Field("http://vault:8200", alias="VAULT_ADDR")
    vault_token: str = Field("", alias="VAULT_TOKEN")
    vault_transit_mount: str = Field("transit", alias="VAULT_TRANSIT_MOUNT")

    # OIDC / Keycloak
    oidc_issuer: str = Field("https://localhost/idp/realms/purple", alias="OIDC_ISSUER")
    oidc_client_id: str = Field("purple-cockpit", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field("", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(
        "https://localhost/api/auth/callback", alias="OIDC_REDIRECT_URI"
    )

    # Jetons
    jwt_signing_key: str = Field(alias="JWT_SIGNING_KEY")  # OBLIGATOIRE — pas de valeur par défaut
    access_token_ttl_seconds: int = Field(600, alias="ACCESS_TOKEN_TTL_SECONDS")
    refresh_token_ttl_seconds: int = Field(1_209_600, alias="REFRESH_TOKEN_TTL_SECONDS")
    step_up_max_age_seconds: int = Field(300, alias="STEP_UP_MAX_AGE_SECONDS")

    # Comptes locaux de repli (désactivés par défaut — spec v2 §1.1)
    local_accounts_enabled: bool = Field(False, alias="LOCAL_ACCOUNTS_ENABLED")

    # Clé de chiffrement des secrets TOTP au repos (P2). Optionnelle : à défaut, dérivée
    # de JWT_SIGNING_KEY (séparation de domaine). Fournir une clé dédiée en prod permet
    # de la faire tourner indépendamment du secret de signature des jetons.
    totp_enc_key: str = Field("", alias="TOTP_ENC_KEY")

    # Limitation de débit des routes d'auth (durcissement P1). Activée par défaut ;
    # désactivable pour le runner de tests (une seule IP in-process pour tous les
    # comptes fausserait les compteurs). Ce n'est PAS un secret.
    rate_limit_enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")

    # Sas d'ingestion
    clamav_host: str = Field("clamav", alias="CLAMAV_HOST")
    clamav_port: int = Field(3310, alias="CLAMAV_PORT")
    max_evidence_bytes: int = Field(209_715_200, alias="MAX_EVIDENCE_BYTES")
    # Taille max d'une preuve image embarquée en aperçu inline dans un livrable PDF
    # (au-delà, la preuve est référencée par empreinte sans être inlinée). 4 Mio par défaut.
    evidence_preview_max_bytes: int = Field(4_194_304, alias="EVIDENCE_PREVIEW_MAX_BYTES")
    presign_upload_ttl_seconds: int = Field(300, alias="PRESIGN_UPLOAD_TTL_SECONDS")
    presign_download_ttl_seconds: int = Field(300, alias="PRESIGN_DOWNLOAD_TTL_SECONDS")

    # Rétention
    default_retention_days: int = Field(365, alias="DEFAULT_RETENTION_DAYS")

    # Enrichissement CVE
    enrichment_base_url: str = Field(
        "https://vulnerability.circl.lu", alias="ENRICHMENT_BASE_URL"
    )
    # Endpoint EPSS dédié (domaine distinct — vulnerability-lookup n'expose pas
    # l'EPSS de façon fiable dans l'agrégat ; cf. cve.circl.lu/api/epss/{cve}).
    enrichment_epss_url: str = Field(
        "https://cve.circl.lu", alias="ENRICHMENT_EPSS_URL"
    )
    enrichment_timeout_seconds: float = Field(8.0, alias="ENRICHMENT_TIMEOUT_SECONDS")

    # Synchronisation des référentiels depuis les sources amont (MITRE).
    attack_stix_url: str = Field(
        "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
        "refs/heads/master/enterprise-attack/enterprise-attack.json",
        alias="ATTACK_STIX_URL",
    )
    d3fend_ontology_url: str = Field(
        "https://raw.githubusercontent.com/d3fend/d3fend/"
        "refs/heads/gh-pages/ontologies/d3fend.json",
        alias="D3FEND_ONTOLOGY_URL",
    )
    # Cluster MISP Galaxy « threat-actor » (acteurs de la menace + synonymes). Configurable
    # pour instance miroir / air-gap, comme les autres sources amont.
    misp_threat_actor_url: str = Field(
        "https://raw.githubusercontent.com/MISP/misp-galaxy/"
        "main/clusters/threat-actor.json",
        alias="MISP_THREAT_ACTOR_URL",
    )
    reference_sync_timeout_seconds: float = Field(90.0, alias="REFERENCE_SYNC_TIMEOUT_SECONDS")

    # Rendu des livrables (micro-service Chromium headless)
    pdf_renderer_url: str = Field("http://pdf-renderer:3000/pdf", alias="PDF_RENDERER_URL")

    # Mots de passe des comptes de démonstration créés par le seed (app.seed).
    # Externalisés pour ne PAS figer de secret dans le code. Défaut « à changer » :
    # le seed avertit s'il est resté tel quel. En production, définir des valeurs
    # propres dans .env (et préférer le SSO + enrôlement MFA aux comptes locaux).
    seed_default_password: str = Field("ChangeMe!2026", alias="SEED_DEFAULT_PASSWORD")
    seed_admin_password: str | None = Field(None, alias="SEED_ADMIN_PASSWORD")
    seed_auditeur_password: str | None = Field(None, alias="SEED_AUDITEUR_PASSWORD")
    seed_ciso_password: str | None = Field(None, alias="SEED_CISO_PASSWORD")

    @model_validator(mode="after")
    def _validate_secrets(self) -> Settings:
        """Validation des secrets obligatoires au démarrage (spec v2 §1.3).

        JWT_SIGNING_KEY est exigé dans TOUS les environnements (il n'a pas de défaut).
        Les autres secrets d'infrastructure (MinIO, Vault, OIDC) ont des valeurs de
        confort pour le développement/démo ; on interdit ces valeurs faibles ou par
        défaut UNIQUEMENT en production, où elles constitueraient une compromission
        directe (accès WORM en clair, unwrap de KEK, usurpation OIDC).
        """
        if not self.jwt_signing_key:
            raise ValueError(
                "JWT_SIGNING_KEY est obligatoire. "
                "Définissez la variable d'environnement JWT_SIGNING_KEY (voir .env.example)."
            )
        key = self.jwt_signing_key.lower()
        if "dev-" in key or "change" in key or "example" in key or "default" in key:
            raise ValueError(
                f"JWT_SIGNING_KEY semble être une valeur par défaut (« {self.jwt_signing_key} »). "
                "Générez une clé forte unique (min. 32 bytes) et définissez JWT_SIGNING_KEY."
            )

        if self.is_production:
            self._validate_production_secrets()
        return self

    def _validate_production_secrets(self) -> None:
        """Refuse les secrets d'infrastructure faibles/par défaut en production."""
        # Motifs révélant un secret laissé au gabarit (.env.example) ou au défaut usine.
        weak = ("change", "example", "default", "minioadmin", "admin")

        def _is_weak(value: str) -> bool:
            v = (value or "").lower()
            return not value or any(m in v for m in weak)

        problems: list[str] = []
        if _is_weak(self.minio_root_user):
            problems.append("MINIO_ROOT_USER (défaut « minioadmin »)")
        if _is_weak(self.minio_root_password):
            problems.append("MINIO_ROOT_PASSWORD (défaut/gabarit)")
        if _is_weak(self.vault_token):
            problems.append("VAULT_TOKEN (vide ou gabarit)")
        if _is_weak(self.oidc_client_secret):
            problems.append("OIDC_CLIENT_SECRET (vide ou gabarit)")
        # Vault protège la KEK : sa liaison DOIT être chiffrée en production.
        if not self.vault_addr.lower().startswith("https://"):
            problems.append("VAULT_ADDR (doit être https:// en production)")

        if problems:
            raise ValueError(
                "Secrets d'infrastructure invalides en production "
                "(ENVIRONMENT=" + self.environment + ") : "
                + ", ".join(problems)
                + ". Injectez des valeurs propres hors dépôt (voir .env.example)."
            )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
