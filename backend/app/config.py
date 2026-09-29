from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    default_timezone: str = "America/Bogota"
    dian_calendar_year: int = 2026

    anthropic_api_key: str = ""

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/despacho"

    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance_name: str = ""
    evolution_webhook_secret: str = ""

    n8n_webhook_base: str = ""

    # Ingesta
    ingest_max_docs_per_client_day: int = 50
    ingest_max_file_bytes: int = 10 * 1024 * 1024
    ingest_email_secret: str = ""
    storage_bucket: str = "documents"

    model_sonnet: str = Field(default="claude-sonnet-5")
    model_haiku: str = Field(default="claude-haiku-4-5-20251001")


@lru_cache
def get_settings() -> Settings:
    return Settings()
