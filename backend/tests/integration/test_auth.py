"""Auth end to end through HTTP, against the real migrated database."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.routes.auth import REFRESH_COOKIE
from app.models import RefreshToken, User
from tests.helpers import ORIGIN, STRONG_PASSWORD, InMemoryRateLimiter

EMAIL = "om@example.com"
Sessions = async_sessionmaker[AsyncSession]


async def register(api: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    response = await api.post(
        "/api/v1/auth/register", json={"email": email, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response


def bearer(response: httpx.Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def use_cookie(api: httpx.AsyncClient, token: str) -> None:
    """Make the client's cookie jar hold exactly this refresh token, like a browser would."""
    api.cookies.clear()
    api.cookies.set(REFRESH_COOKIE, token)


async def refresh(api: httpx.AsyncClient, token: str | None = None) -> httpx.Response:
    if token:
        use_cookie(api, token)
    return await api.post("/api/v1/auth/refresh", headers={"Origin": ORIGIN})


# ---- register ----


async def test_register_returns_a_session_and_a_hardened_cookie(api: httpx.AsyncClient) -> None:
    response = await register(api, "  Om@Example.com ")
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["user"]["email"] == EMAIL
    assert "refresh" not in response.text.lower().replace("refresh_token", "")

    cookie = response.headers["set-cookie"]
    for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/api/v1/auth"):
        assert attribute in cookie
    token = api.cookies.get(REFRESH_COOKIE)
    assert token is not None
    assert token not in response.text  # never in the body


async def test_passwords_and_refresh_tokens_are_not_stored_in_plaintext(
    api: httpx.AsyncClient, sessionmaker: Sessions
) -> None:
    await register(api)
    raw = api.cookies[REFRESH_COOKIE]
    async with sessionmaker() as session:
        user = await session.scalar(select(User))
        stored = await session.scalar(select(RefreshToken))
    assert user is not None and stored is not None
    assert user.password_hash.startswith("$argon2id$")
    assert STRONG_PASSWORD not in user.password_hash
    assert stored.token_hash != raw


async def test_duplicate_email_is_a_conflict_in_any_case(api: httpx.AsyncClient) -> None:
    await register(api)
    response = await api.post(
        "/api/v1/auth/register", json={"email": "OM@example.com", "password": STRONG_PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_weak_password_is_rejected_without_echoing_it(api: httpx.AsyncClient) -> None:
    response = await api.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "weakpassword"}
    )
    assert response.status_code == 422
    assert "weakpassword" not in response.text


# ---- login ----


async def test_login_works_and_is_case_insensitive(api: httpx.AsyncClient) -> None:
    await register(api)
    api.cookies.clear()
    response = await api.post(
        "/api/v1/auth/login", json={"email": "OM@EXAMPLE.COM", "password": STRONG_PASSWORD}
    )
    assert response.status_code == 200
    assert api.cookies.get(REFRESH_COOKIE)
    me = await api.get("/api/v1/me", headers=bearer(response))
    assert me.json()["email"] == EMAIL


async def test_wrong_password_and_unknown_email_look_the_same(api: httpx.AsyncClient) -> None:
    await register(api)
    wrong_password = await api.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "Wrong-Horse-9"}
    )
    unknown_email = await api.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": STRONG_PASSWORD}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["code"] == unknown_email.json()["error"]["code"]
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_login_is_rate_limited_per_email(
    api: httpx.AsyncClient, limiter: InMemoryRateLimiter
) -> None:
    await register(api)
    for _ in range(5):
        await api.post("/api/v1/auth/login", json={"email": EMAIL, "password": "Wrong-Horse-9"})
    response = await api.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["retry-after"]) > 0
    assert not any(EMAIL in key for key in limiter.counts)  # emails are hashed in keys


async def test_login_is_rate_limited_per_ip(api: httpx.AsyncClient) -> None:
    for n in range(10):
        await api.post("/api/v1/auth/login", json={"email": f"u{n}@example.com", "password": "x"})
    response = await api.post("/api/v1/auth/login", json={"email": EMAIL, "password": "x"})
    assert response.status_code == 429


async def test_register_is_rate_limited_per_ip(api: httpx.AsyncClient) -> None:
    for n in range(5):
        await register(api, f"u{n}@example.com")
    response = await api.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 429


# ---- bearer tokens ----


async def test_me_requires_a_token(api: httpx.AsyncClient) -> None:
    response = await api.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_me_rejects_a_malformed_header(api: httpx.AsyncClient) -> None:
    response = await api.get("/api/v1/me", headers={"Authorization": "Token abc"})
    assert response.json()["error"]["code"] == "MALFORMED_TOKEN"


async def test_me_rejects_a_token_for_a_deleted_user(
    api: httpx.AsyncClient, sessionmaker: Sessions
) -> None:
    headers = bearer(await register(api))
    async with sessionmaker() as session:
        user = await session.scalar(select(User))
        await session.delete(user)
        await session.commit()
    response = await api.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


# ---- refresh: rotation and reuse detection ----


async def test_refresh_rotates_the_token(api: httpx.AsyncClient) -> None:
    await register(api)
    first = api.cookies[REFRESH_COOKIE]
    response = await refresh(api)
    assert response.status_code == 200
    second = api.cookies[REFRESH_COOKIE]
    assert second != first
    me = await api.get("/api/v1/me", headers=bearer(response))
    assert me.status_code == 200


async def test_refresh_without_a_cookie_is_401(api: httpx.AsyncClient) -> None:
    response = await api.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_with_an_unknown_token_is_401(api: httpx.AsyncClient) -> None:
    response = await refresh(api, "made-up-token")
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_from_a_foreign_origin_is_refused(api: httpx.AsyncClient) -> None:
    await register(api)
    response = await api.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.test"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


async def test_expired_refresh_token_is_401(api: httpx.AsyncClient, sessionmaker: Sessions) -> None:
    await register(api)
    async with sessionmaker() as session:
        await session.execute(
            update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    response = await refresh(api)
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_parallel_reuse_within_the_grace_window_is_benign(api: httpx.AsyncClient) -> None:
    await register(api)
    original = api.cookies[REFRESH_COOKIE]
    assert (await refresh(api)).status_code == 200
    successor = api.cookies[REFRESH_COOKIE]

    # A second tab presents the token the first tab just rotated.
    raced = await refresh(api, original)
    assert raced.status_code == 401
    assert raced.json()["error"]["code"] == "REFRESH_TOKEN_ROTATED"

    # Nothing was revoked: the successor still works.
    assert (await refresh(api, successor)).status_code == 200


async def test_truly_concurrent_refreshes_cannot_both_succeed(api: httpx.AsyncClient) -> None:
    """SELECT … FOR UPDATE makes the second request wait for the first, then see the
    rotation. Without the lock both would mint a new token from the same one."""
    await register(api)
    first, second = await asyncio.gather(refresh(api), refresh(api))
    assert sorted([first.status_code, second.status_code]) == [200, 401]
    loser = first if first.status_code == 401 else second
    assert loser.json()["error"]["code"] == "REFRESH_TOKEN_ROTATED"


async def test_reuse_after_the_grace_window_revokes_the_whole_family(
    api: httpx.AsyncClient, sessionmaker: Sessions
) -> None:
    await register(api)
    stolen = api.cookies[REFRESH_COOKIE]
    assert (await refresh(api)).status_code == 200
    legitimate = api.cookies[REFRESH_COOKIE]

    # Age the rotation past the grace window, then replay the stolen token.
    async with sessionmaker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.revoked_at.is_not(None))
            .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await session.commit()
    replay = await refresh(api, stolen)
    assert replay.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # The legitimate user's newer token died with the family.
    after = await refresh(api, legitimate)
    assert after.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_reuse_detection_does_not_touch_other_logins(api: httpx.AsyncClient) -> None:
    await register(api)
    laptop = api.cookies[REFRESH_COOKIE]
    api.cookies.clear()
    await api.post("/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    phone = api.cookies[REFRESH_COOKIE]

    use_cookie(api, laptop)
    await api.post("/api/v1/auth/logout")
    assert (await refresh(api, phone)).status_code == 200


# ---- logout ----


async def test_logout_revokes_the_session_and_clears_the_cookie(api: httpx.AsyncClient) -> None:
    await register(api)
    token = api.cookies[REFRESH_COOKIE]
    response = await api.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    assert response.status_code == 204
    assert REFRESH_COOKIE not in api.cookies
    assert (await refresh(api, token)).status_code == 401


async def test_logout_without_a_session_is_still_204(api: httpx.AsyncClient) -> None:
    assert (await api.post("/api/v1/auth/logout")).status_code == 204


# ---- change password ----


async def test_change_password_signs_out_everywhere_and_starts_a_new_session(
    api: httpx.AsyncClient,
) -> None:
    session = await register(api)
    other_device = api.cookies[REFRESH_COOKIE]
    new_password = "Brand-New-Pass-7"

    response = await api.post(
        "/api/v1/me/password",
        json={"current_password": STRONG_PASSWORD, "new_password": new_password},
        headers=bearer(session),
    )
    assert response.status_code == 200
    this_device = api.cookies[REFRESH_COOKIE]
    assert this_device != other_device

    assert (await refresh(api, other_device)).status_code == 401
    assert (await refresh(api, this_device)).status_code == 200

    old = await api.post("/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert old.status_code == 401
    new = await api.post("/api/v1/auth/login", json={"email": EMAIL, "password": new_password})
    assert new.status_code == 200


async def test_change_password_with_a_wrong_current_password_is_422(
    api: httpx.AsyncClient,
) -> None:
    # 422, not 401: a 401 would make the frontend think the session expired.
    session = await register(api)
    response = await api.post(
        "/api/v1/me/password",
        json={"current_password": "Wrong-Horse-9", "new_password": "Brand-New-Pass-7"},
        headers=bearer(session),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"


async def test_change_password_requires_a_token(api: httpx.AsyncClient) -> None:
    response = await api.post(
        "/api/v1/me/password",
        json={"current_password": STRONG_PASSWORD, "new_password": "Brand-New-Pass-7"},
    )
    assert response.status_code == 401


# ---- rehash ----


async def test_login_upgrades_a_hash_made_with_old_parameters(
    api: httpx.AsyncClient, sessionmaker: Sessions
) -> None:
    from argon2 import PasswordHasher as Argon2Hasher

    await register(api)
    weaker = Argon2Hasher(time_cost=1, memory_cost=512, parallelism=1).hash(STRONG_PASSWORD)
    async with sessionmaker() as session:
        await session.execute(update(User).values(password_hash=weaker))
        await session.commit()

    response = await api.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 200
    async with sessionmaker() as session:
        user = await session.scalar(select(User))
    assert user is not None
    assert user.password_hash != weaker
