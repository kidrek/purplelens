"""Configuration typée (pydantic-settings) — DAT §2.1.

Toute la configuration vient de l'environnement (.env en dev, secrets injectés en prod).
Aucun secret n'est codé en dur.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    jwt_signing_key: str = Field("dev-signing-key-change-me-32bytes!", alias="JWT_SIGNING_KEY")
    access_token_ttl_seconds: int = Field(600, alias="ACCESS_TOKEN_TTL_SECONDS")
    refresh_token_ttl_seconds: int = Field(1_209_600, alias="REFRESH_TOKEN_TTL_SECONDS")
    step_up_max_age_seconds: int = Field(300, alias="STEP_UP_MAX_AGE_SECONDS")

    # Comptes locaux de repli (désactivés par défaut — spec v2 §1.1)
    local_accounts_enabled: bool = Field(False, alias="LOCAL_ACCOUNTS_ENABLED")

    # Sas d'ingestion
    clamav_host: str = Field("clamav", alias="CLAMAV_HOST")
    clamav_port: int = Field(3310, alias="CLAMAV_PORT")
    max_evidence_bytes: int = Field(209_715_200, alias="MAX_EVIDENCE_BYTES")
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

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
