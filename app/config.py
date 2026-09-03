from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


_INSECURE_VALUES = {
    "", "change-me", "change-me-before-sharing", "change-me-in-real-pilot",
    "lg_demo_secret", "password", "secret", "admin",
}


def _looks_insecure_secret(value: str | None, *, minimum: int = 24) -> bool:
    if value is None:
        return True
    v = value.strip()
    return len(v) < minimum or v.lower() in _INSECURE_VALUES or "change-me" in v.lower()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("LOOPGRID_DATABASE_URL", "sqlite:///./data/loopgrid.db")
    # LOOPGRID_PLATFORM_ADMIN_KEY is the preferred v0.8 name. LOOPGRID_API_KEY remains
    # a compatibility alias for older local setups. It is never accepted by normal evidence
    # endpoints; it only bootstraps platform/workspace administration paths.
    api_key: str = os.getenv("LOOPGRID_PLATFORM_ADMIN_KEY") or os.getenv("LOOPGRID_API_KEY", "lg_demo_secret")
    environment: str = os.getenv("LOOPGRID_ENV", "development").strip().lower()
    public_base_url: str = os.getenv("LOOPGRID_PUBLIC_BASE_URL", "http://localhost:8000")

    # Database runtime. SQLite remains the zero-setup local path; PostgreSQL is the
    # controlled design-partner deployment database.
    db_pool_size: int = _int("LOOPGRID_DB_POOL_SIZE", 10)
    db_max_overflow: int = _int("LOOPGRID_DB_MAX_OVERFLOW", 20)
    db_pool_recycle_seconds: int = _int("LOOPGRID_DB_POOL_RECYCLE_SECONDS", 1800)

    # Signing. Local Ed25519 is appropriate for local/design-partner evaluation. AWS KMS
    # remains an optional hardened boundary and is not required for the v0.8 design-partner release.
    signer_provider: str = os.getenv("LOOPGRID_SIGNER_PROVIDER", "local_ed25519")
    signing_key_path: Path = Path(os.getenv("LOOPGRID_SIGNING_KEY_PATH", "./data/signing-key.pem"))
    public_key_path: Path = Path(os.getenv("LOOPGRID_PUBLIC_KEY_PATH", "./data/signing-public.pem"))
    aws_kms_key_id: str | None = os.getenv("LOOPGRID_AWS_KMS_KEY_ID")
    aws_region: str | None = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

    # Raw payload vault. Signed events contain commitments/descriptors; full payloads are
    # encrypted separately so retention/erasure can remove plaintext without breaking proof.
    payload_key_path: Path = Path(os.getenv("LOOPGRID_PAYLOAD_KEY_PATH", "./data/payload-key.bin"))
    payload_master_key_b64: str | None = os.getenv("LOOPGRID_PAYLOAD_MASTER_KEY_B64")

    # Optional RFC3161 timestamp authority.
    tsa_url: str | None = os.getenv("LOOPGRID_TSA_URL")
    tsa_timeout_seconds: int = _int("LOOPGRID_TSA_TIMEOUT_SECONDS", 8)
    tsa_ca_file: str | None = os.getenv("LOOPGRID_TSA_CA_FILE")

    # Production/design-partner safety.
    ingest_rate_limit_per_minute: int = _int("LOOPGRID_INGEST_RATE_LIMIT_PER_MINUTE", 600)
    admin_rate_limit_per_minute: int = _int("LOOPGRID_ADMIN_RATE_LIMIT_PER_MINUTE", 120)
    max_request_body_bytes: int = _int("LOOPGRID_MAX_REQUEST_BODY_BYTES", 2_000_000)
    bootstrap_token: str | None = os.getenv("LOOPGRID_BOOTSTRAP_TOKEN")
    require_user_auth: bool = _bool("LOOPGRID_REQUIRE_USER_AUTH", False)
    strict_production_safety: bool = _bool("LOOPGRID_STRICT_PRODUCTION_SAFETY", True)
    session_hours: int = _int("LOOPGRID_SESSION_HOURS", 12)
    cors_origins: tuple[str, ...] = _csv("LOOPGRID_CORS_ORIGINS")
    mcp_upstreams_json: str = os.getenv("LOOPGRID_MCP_UPSTREAMS_JSON", "{}")

    # Evidence gateway behavior.
    enforce_lifecycle: bool = _bool("LOOPGRID_ENFORCE_LIFECYCLE", True)

    @property
    def mcp_upstreams(self) -> dict[str, str]:
        try:
            value = json.loads(self.mcp_upstreams_json or "{}")
            return {str(k): str(v) for k, v in value.items() if str(v).startswith(("https://", "http://"))}
        except Exception:
            return {}


def production_safety_errors(cfg: Settings) -> list[str]:
    """Return blocking configuration errors for a production-mode design-partner deployment."""
    if cfg.environment != "production" or not cfg.strict_production_safety:
        return []
    errors: list[str] = []
    if not cfg.database_url.startswith("postgres"):
        errors.append("production mode requires PostgreSQL (LOOPGRID_DATABASE_URL)")
    if not cfg.require_user_auth:
        errors.append("production mode requires LOOPGRID_REQUIRE_USER_AUTH=true")
    if _looks_insecure_secret(cfg.api_key):
        errors.append("LOOPGRID_PLATFORM_ADMIN_KEY must be a non-placeholder secret of at least 24 characters")
    if _looks_insecure_secret(cfg.bootstrap_token):
        errors.append("LOOPGRID_BOOTSTRAP_TOKEN must be a non-placeholder secret of at least 24 characters")
    if "*" in cfg.cors_origins:
        errors.append("production mode does not allow wildcard LOOPGRID_CORS_ORIGINS")
    if cfg.max_request_body_bytes <= 0:
        errors.append("LOOPGRID_MAX_REQUEST_BODY_BYTES must be positive")
    return errors


def assert_production_safe(cfg: Settings) -> None:
    errors = production_safety_errors(cfg)
    if errors:
        joined = "; ".join(errors)
        raise RuntimeError(f"Unsafe LoopGrid production configuration: {joined}")


settings = Settings()
