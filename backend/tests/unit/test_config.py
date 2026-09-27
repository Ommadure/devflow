import pytest
from pydantic import ValidationError

from app.core.config import Settings, is_transaction_pooler, normalize_database_url
from tests.helpers import TEST_JWT_SECRET


def make(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


def test_neon_url_becomes_an_asyncpg_url() -> None:
    url = "postgres://u:p@ep-x-pooler.aws.neon.tech/db?sslmode=require&channel_binding=require"
    assert (
        normalize_database_url(url)
        == "postgresql+asyncpg://u:p@ep-x-pooler.aws.neon.tech/db?ssl=require"
    )


def test_asyncpg_url_is_left_alone() -> None:
    url = "postgresql+asyncpg://u:p@localhost:5434/db"
    assert normalize_database_url(url) == url


def test_pooler_detection() -> None:
    assert is_transaction_pooler("postgresql+asyncpg://u:p@ep-x-pooler.aws.neon.tech/db")
    assert not is_transaction_pooler("postgresql+asyncpg://u:p@ep-x.aws.neon.tech/db")


def test_missing_required_settings_fail_outside_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "REDIS_URL", "JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL, REDIS_URL, JWT_SECRET"):
        make(app_env="production")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        make(app_env="test", jwt_secret="too-short")


def test_production_settings_are_accepted_when_complete() -> None:
    settings = make(
        app_env="production",
        database_url="postgres://u:p@ep-x-pooler.aws.neon.tech/db?sslmode=require",
        database_direct_url="postgres://u:p@ep-x.aws.neon.tech/db?sslmode=require",
        redis_url="redis://localhost:6379/0",
        jwt_secret=TEST_JWT_SECRET,
        cors_origins="https://devflow.example.com/, https://preview.example.com",
    )
    assert settings.is_production
    assert settings.uses_transaction_pooler
    assert settings.migrations_database_url.startswith("postgresql+asyncpg://u:p@ep-x.aws")
    assert settings.cors_origin_list == [
        "https://devflow.example.com",
        "https://preview.example.com",
    ]


def test_migrations_fall_back_to_the_app_url() -> None:
    settings = make(app_env="test", database_url="postgresql+asyncpg://u:p@localhost/db")
    assert settings.migrations_database_url == "postgresql+asyncpg://u:p@localhost/db"


def test_secrets_are_masked_when_printed() -> None:
    settings = make(app_env="test", jwt_secret=TEST_JWT_SECRET)
    assert TEST_JWT_SECRET not in repr(settings)
