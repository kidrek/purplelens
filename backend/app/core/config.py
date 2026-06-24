from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SQLite par défaut pour un démarrage zéro-config.
    # En production : postgresql+psycopg2://user:pass@host:5432/purplelens
    database_url: str = "sqlite:///./purplelens.db"

    app_name: str = "PurpleLens"
    api_prefix: str = "/api"

    # Evidence Vault — abstraction de stockage objet.
    # En production, pointer vers MinIO / S3.
    storage_backend: str = "local"  # local | s3
    s3_endpoint: str = ""
    s3_bucket: str = "purplelens-evidence"

    class Config:
        env_file = ".env"


settings = Settings()
