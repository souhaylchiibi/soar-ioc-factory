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
    # Authentication is ON by default; AUTH_ENABLED=false is refused in production.
    auth_enabled: bool = True
    # Shared secret used by n8n (header X-API-Key). Empty = service access disabled.
    service_api_key: str = ""
    # First admin account, created at startup only if the users table is empty.
    admin_username: str = "admin"
    admin_email: str = "admin@soar.local"
    admin_password: str = ""
    # Rate limits (per client IP, per minute)
    rate_limit_per_minute: int = 600
    login_rate_limit_per_minute: int = 10
    # Lock an account after N consecutive failed logins, for M minutes.
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    # Only trust X-Real-IP when the API sits behind our nginx.
    trust_proxy_headers: bool = False

    # --- Sensors (read-only mounts inside the API container) ---
    sensor_root: str = "/sensor"
    n8n_url: str = "http://n8n:5678"

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
    misp_verify_cert: bool = True  # TLS verified by default; disable only for a lab MISP with a self-signed cert

    # --- Scoring policy (initial values, tunable) ---
    score_threshold_publish: int = 80
    score_threshold_monitor: int = 50

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def production_errors(self) -> list[str]:
        """Configuration mistakes that must block a production start."""
        if self.app_env != "production":
            return []
        errors = []
        if self.secret_key.startswith("change-me") or len(self.secret_key) < 32:
            errors.append("SECRET_KEY par défaut ou trop court (>= 32 caractères)")
        if not self.auth_enabled:
            errors.append("AUTH_ENABLED=false interdit en production")
        if self.debug:
            errors.append("DEBUG=true interdit en production")
        if "*" in self.cors_origins_list:
            errors.append("CORS_ORIGINS='*' interdit en production")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
