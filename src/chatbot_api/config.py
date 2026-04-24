import os
from urllib.parse import quote_plus

from pydantic import BaseModel


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _sqlserver_url_from_env() -> str | None:
    explicit = os.getenv("CHATBOT_DATABASE_URL")
    if explicit:
        return explicit

    host = os.getenv("CHATBOT_SQLSERVER_HOST")
    if not host:
        return None

    user = os.getenv("CHATBOT_SQLSERVER_USER", "sa")
    password = os.getenv("CHATBOT_SQLSERVER_PASSWORD", "")
    database = os.getenv("CHATBOT_SQLSERVER_DB", "master")
    port = os.getenv("CHATBOT_SQLSERVER_PORT", "1433")
    driver = os.getenv("CHATBOT_SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    encrypt = os.getenv("CHATBOT_SQLSERVER_ENCRYPT", "no")
    trust_server_certificate = os.getenv("CHATBOT_SQLSERVER_TRUST_CERT", "yes")

    quoted_driver = quote_plus(driver)
    quoted_password = quote_plus(password)
    return (
        f"mssql+pyodbc://{user}:{quoted_password}@{host}:{port}/{database}"
        f"?driver={quoted_driver}&Encrypt={encrypt}&TrustServerCertificate={trust_server_certificate}"
    )


class Settings(BaseModel):
    app_name: str = "Universal Chatbot API"
    app_version: str = "0.1.0"
    app_env: str = os.getenv("CHATBOT_ENV", "development").strip().lower()
    strict_startup_validation: bool = _bool_env("CHATBOT_STRICT_STARTUP_VALIDATION", True)
    cookie_secure: bool = _bool_env("CHATBOT_COOKIE_SECURE", False)
    cookie_samesite: str = os.getenv("CHATBOT_COOKIE_SAMESITE", "lax").strip().lower()
    cors_allowed_origins: str = os.getenv("CHATBOT_CORS_ALLOWED_ORIGINS", "")
    trusted_hosts: str = os.getenv("CHATBOT_TRUSTED_HOSTS", "")
    security_headers_enabled: bool = _bool_env("CHATBOT_SECURITY_HEADERS_ENABLED", True)
    default_model: str = "qwen2.5-7b-instruct"
    enable_strict_grounding_default: bool = True
    jwt_secret: str | None = os.getenv("CHATBOT_JWT_SECRET")
    jwt_algorithm: str = os.getenv("CHATBOT_JWT_ALGORITHM", "HS256")
    allow_dev_token_auth: bool = _bool_env("CHATBOT_ALLOW_DEV_TOKEN_AUTH", False)
    local_login_enabled: bool = _bool_env("CHATBOT_LOCAL_LOGIN_ENABLED", True)
    jwt_claim_tenant_id: str = os.getenv("CHATBOT_JWT_CLAIM_TENANT_ID", "tenant_id")
    jwt_claim_user_id: str = os.getenv("CHATBOT_JWT_CLAIM_USER_ID", "user_id")
    jwt_claim_role: str = os.getenv("CHATBOT_JWT_CLAIM_ROLE", "role")
    jwt_claim_sub_fallback_enabled: bool = _bool_env("CHATBOT_JWT_CLAIM_SUB_FALLBACK_ENABLED", True)
    jwt_issuer: str | None = os.getenv("CHATBOT_JWT_ISSUER")
    jwt_audience: str | None = os.getenv("CHATBOT_JWT_AUDIENCE")
    rate_limit_enabled: bool = _bool_env("CHATBOT_RATE_LIMIT_ENABLED", True)
    rate_limit_window_seconds: int = int(os.getenv("CHATBOT_RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_requests_per_window: int = int(os.getenv("CHATBOT_RATE_LIMIT_REQUESTS_PER_WINDOW", "120"))
    rate_limit_chat_requests_per_window: int = int(os.getenv("CHATBOT_RATE_LIMIT_CHAT_REQUESTS_PER_WINDOW", "30"))
    alert_error_rate_percent_threshold: float = float(
        os.getenv("CHATBOT_ALERT_ERROR_RATE_PERCENT_THRESHOLD", "5")
    )
    alert_avg_latency_ms_threshold: float = float(
        os.getenv("CHATBOT_ALERT_AVG_LATENCY_MS_THRESHOLD", "1200")
    )
    external_research_enabled: bool = _bool_env("CHATBOT_EXTERNAL_RESEARCH_ENABLED", True)
    external_research_allowlist: str = os.getenv(
        "CHATBOT_EXTERNAL_RESEARCH_ALLOWLIST",
        "www.rbi.org.in,www.sebi.gov.in,www.investopedia.com",
    )
    # Enable V2 features (experimental) behind a feature flag. Disabled by default.
    enable_v2: bool = _bool_env("CHATBOT_ENABLE_V2", False)
    # Select V2 research backend without changing API route: skeleton | external
    v2_research_provider: str = os.getenv("CHATBOT_V2_RESEARCH_PROVIDER", "skeleton").strip().lower()
    tenant_domain_map: str = os.getenv("CHATBOT_TENANT_DOMAIN_MAP", "tnt_demo:finance")
    default_domain: str | None = os.getenv("CHATBOT_DEFAULT_DOMAIN")
    website_presets_json: str = os.getenv("CHATBOT_WEBSITE_PRESETS_JSON", "")
    website_preset_map: str = os.getenv("CHATBOT_WEBSITE_PRESET_MAP", "")
    tenant_isolation_enforced: bool = _bool_env("CHATBOT_TENANT_ISOLATION_ENFORCED", True)
    database_url: str | None = _sqlserver_url_from_env()
    db_fallback_to_mock: bool = _bool_env("CHATBOT_DB_FALLBACK_TO_MOCK", False)


settings = Settings()
