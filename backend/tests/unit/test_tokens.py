"""Every way an access token can be wrong must end in a 401 with a stable code."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.tokens import (
    REQUIRED_CLAIMS,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    new_refresh_token,
)
from tests.helpers import make_token


def rejects(token: str, settings: Settings, code: str = "INVALID_TOKEN") -> None:
    with pytest.raises(UnauthorizedError) as caught:
        decode_access_token(token, settings)
    assert caught.value.code == code


def test_round_trip(settings: Settings) -> None:
    user_id = uuid4()
    assert decode_access_token(create_access_token(user_id, settings), settings) == user_id


def test_token_lifetime_follows_settings(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = create_access_token(uuid4(), settings, now=now)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == settings.access_token_ttl_minutes * 60


def test_expired(settings: Settings) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    expired = make_token({"iat": past, "exp": past + timedelta(minutes=15)})
    rejects(expired, settings, "TOKEN_EXPIRED")


def test_wrong_audience(settings: Settings) -> None:
    rejects(make_token({"aud": "authenticated"}), settings)


def test_wrong_issuer(settings: Settings) -> None:
    rejects(make_token({"iss": "someone-else"}), settings)


def test_signed_with_another_secret(settings: Settings) -> None:
    rejects(make_token(secret="another-secret-" + "y" * 40), settings)


def test_tampered_payload(settings: Settings) -> None:
    header, _, signature = make_token().split(".")
    forged_payload = make_token({"sub": str(uuid4())}).split(".")[1]
    rejects(f"{header}.{forged_payload}.{signature}", settings)


def test_alg_none_is_refused(settings: Settings) -> None:
    # The classic forgery: an unsigned token that says it needs no signature.
    unsigned = jwt.encode(
        jwt.decode(make_token(), options={"verify_signature": False}), key=None, algorithm="none"
    )
    rejects(unsigned, settings)


def test_other_hmac_algorithm_is_refused(settings: Settings) -> None:
    # Right secret, but HS512 isn't on the allow-list. (Only the verifier's key must match.)
    settings = settings.model_copy(update={"jwt_secret": SecretStr("k" * 64)})
    rejects(make_token(secret="k" * 64, algorithm="HS512"), settings)


@pytest.mark.parametrize("claim", REQUIRED_CLAIMS)
def test_each_required_claim(claim: str, settings: Settings) -> None:
    rejects(make_token(drop=(claim,)), settings)


def test_subject_must_be_a_uuid(settings: Settings) -> None:
    rejects(make_token({"sub": "admin"}), settings)


def test_garbage(settings: Settings) -> None:
    rejects("not.a.jwt", settings)


def test_valid_helper_token_is_accepted(settings: Settings) -> None:
    assert decode_access_token(make_token(), settings) == UUID(
        "7d3f8a2e-5b1c-4e9f-a6d0-2c8b1e4f7a90"
    )


def test_refresh_tokens_are_random_and_hashed_deterministically() -> None:
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second
    assert len(first) >= 43  # 32 bytes, base64url
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert hash_refresh_token(first) != first
