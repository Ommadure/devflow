"""Application settings, read from environment variables (and backend/.env).

Every setting lives here so the rest of the code never reads os.environ directly.
Secrets are typed as SecretStr so they are masked if a Settings object is ever printed or
logged. Invalid or missing values fail at startup, not on the first request that needs them.
"""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]

REQUIRED_OUTSIDE_TESTS: tuple[str, ...] = ("database_url", "redis_url", "jwt_secret")
# HS256 is only as strong as its key; RFC 7518 asks for at least as many bits as the hash.
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # `FOO=` in .env means "not set", not "set to the empty string".
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: AppEnv = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # The API and worker use DATABASE_URL (Neon's pooled host in production). Alembic uses
    # DATABASE_DIRECT_URL when it is set: migrations need a real session, not PgBouncer.
    database_url: str = ""
    database_direct_url: str = ""
    redis_url: str = ""

    jwt_secret: SecretStr = SecretStr("")
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=90)
    # Two tabs refreshing at once present the same token; the loser is not a thief.
    refresh_reuse_grace_seconds: int = Field(default=30, ge=0, le=300)
    # Browsers accept Secure cookies on http://localhost (except Safari); turn off only then.
    cookie_secure: bool = True

    # Comma-separated. Used by CORS and by the Origin check on cookie-authenticated routes.
    cors_origins: str = "http://localhost:5173"

    # Embeddings (ADR 0004). "fake" gives deterministic vectors with no model download
    # (tests, CI); the dimension is checked against the model at startup.
    embedding_provider: Literal["fastembed", "fake"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    # Where FastEmbed keeps the model. The Docker image downloads it here at build time.
    fastembed_cache_path: str = ".cache/fastembed"
    # Search embeds the query on every request; the same query within this window reuses it.
    query_embedding_cache_seconds: int = Field(default=3600, ge=0)

    # LLM (Phase 5). "fake" answers from a script: tests, CI, and running without a key.
    llm_provider: Literal["gemini", "fake"] = "gemini"
    llm_model: str = "gemini-3.5-flash"
    gemini_api_key: SecretStr = SecretStr("")
    # {"model": [usd_per_1M_input_tokens, usd_per_1M_output_tokens]}, copied from the
    # provider's pricing page. Unpriced models record a cost of 0 (and say so in the logs).
    llm_pricing: dict[str, tuple[float, float]] = {}
    llm_timeout_seconds: float = Field(default=60, gt=0)
    # Gemini "thinking" models spend hidden reasoning tokens that count against the output
    # limit (measured: 287 of 300 on a tagging call, leaving no room for the JSON). These
    # tasks don't need deep reasoning; "minimal" = faster, cheaper, and the answer fits.
    # Empty = the model's default.
    llm_thinking_level: Literal["", "minimal", "low", "medium", "high"] = "minimal"
    ai_daily_quota_per_user: int = Field(default=50, ge=0)
    # Below this cosine similarity, "ask your notes" says it found nothing — without
    # calling the LLM (no cost, no made-up answer).
    notes_min_similarity: float = Field(default=0.6, ge=0, le=1)

    sentry_dsn: str = ""  # empty: Sentry off
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)

    @field_validator("database_url", "database_direct_url")
    @classmethod
    def _asyncpg_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @model_validator(mode="after")
    def _fail_fast(self) -> Self:
        if self.app_env != "test":
            missing = [
                name.upper() for name in REQUIRED_OUTSIDE_TESTS if not _is_set(getattr(self, name))
            ]
            if missing:
                raise ValueError(f"Missing required settings: {', '.join(missing)}")
        secret = self.jwt_secret.get_secret_value()
        if secret and len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin]

    @property
    def migrations_database_url(self) -> str:
        return self.database_direct_url or self.database_url

    @property
    def uses_transaction_pooler(self) -> bool:
        return is_transaction_pooler(self.database_url)


def normalize_database_url(url: str) -> str:
    """Accept the URL a host hands out (Neon: `postgres://…?sslmode=require`) as-is.

    It becomes `postgresql+asyncpg://…?ssl=require`: asyncpg needs its own driver name,
    spells the TLS option `ssl`, and rejects `channel_binding`.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        return url  # already has a driver (postgresql+asyncpg), or empty
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            query.append(("ssl", value))
        elif key != "channel_binding":
            query.append((key, value))
    return urlunsplit(parts._replace(scheme="postgresql+asyncpg", query=urlencode(query)))


def is_transaction_pooler(url: str) -> bool:
    """Neon's pooled hostnames carry `-pooler` (ep-cool-name-123-pooler.region.aws.neon.tech)."""
    return "-pooler" in (urlsplit(url).hostname or "")


def _is_set(value: object) -> bool:
    # SecretStr is always truthy, even when empty, so unwrap it before checking.
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
