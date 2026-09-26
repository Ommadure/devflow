"""Access tokens (JWT) and refresh tokens (opaque random strings).

Access token: HS256 JWT, 15 minutes, kept only in the frontend's memory. Anyone holding it
is the user until it expires, so it is short-lived and never stored.

Refresh token: 32 random bytes in an HttpOnly cookie. It proves nothing by itself; the
server looks up its SHA-256 hash in `refresh_tokens`, so it can be revoked at any time.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import UnauthorizedError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "devflow"
JWT_AUDIENCE = "devflow-api"
REQUIRED_CLAIMS = ["exp", "iat", "sub", "iss", "aud"]


def create_access_token(user_id: UUID, settings: Settings, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_ttl_minutes),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> UUID:
    """Return the user id in a valid token, or raise UnauthorizedError.

    `algorithms` is an explicit allow-list: a token claiming `alg: none`, or an asymmetric
    algorithm that would treat our secret as a public key, is rejected outright.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Your session has expired.", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        # Never echo why: "bad signature" vs "wrong audience" helps an attacker, not a user.
        raise UnauthorizedError("Invalid access token.", code="INVALID_TOKEN") from exc
    try:
        return UUID(str(claims["sub"]))
    except ValueError as exc:
        raise UnauthorizedError("Invalid access token.", code="INVALID_TOKEN") from exc


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of randomness


def hash_refresh_token(token: str) -> str:
    # A fast hash is right here (unlike passwords): the input is 256 random bits, so there
    # is nothing to brute-force, and every refresh has to look it up.
    return hashlib.sha256(token.encode()).hexdigest()
