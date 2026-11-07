"""Application settings — all secrets come from environment variables (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration.

    Nothing sensitive is hardcoded: every value can be overridden by the
    environment (see .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "SOAR IOC Factory"
    app_env: str = "development"  # development | testing | production
    debug: bool = False
    api_prefix: str = "/api/v1"

    # --- Security ---
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database (never exposed outside the Docker network) ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "soar"
    postgres_password: str = "soar-dev-password"
    postgres_db: str = "soar_ioc"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- Integrations (optional API keys — sources work without them) ---
    otx_api_key: str = ""
    abuseipdb_api_key: str = ""
    # abuse.ch Auth-Key (portail auth.abuse.ch) — requis pour URLhaus/ThreatFox
    abusech_auth_key: str = ""
    misp_url: str = ""
    misp_key: str = ""
    misp_verify_cert: bool = False

    # --- Scoring policy (initial values, tunable) ---
    score_threshold_publish: int = 80
    score_threshold_monitor: int = 50

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
