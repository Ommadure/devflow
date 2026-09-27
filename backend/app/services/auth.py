"""Authentication: register, log in, refresh, log out, change password.

Services own the unit of work (they commit) and never import FastAPI: routes translate
HTTP into calls here, and cookies stay a route concern.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, UnauthorizedError, ValidationFailedError
from app.core.logging import bind_context
from app.core.passwords import PasswordHasher
from app.core.tokens import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
)
from app.models import RefreshToken, User
from app.repositories import refresh_tokens, users

log = structlog.get_logger()

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class IssuedSession:
    user: User
    access_token: str
    expires_in: int  # seconds
    refresh_token: str  # raw value: goes into the cookie, never into the database
    refresh_expires_at: datetime


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        hasher: PasswordHasher,
        settings: Settings,
        clock: Clock = utcnow,
    ) -> None:
        self._session = session
        self._hasher = hasher
        self._settings = settings
        self._clock = clock

    async def register(self, email: str, password: str) -> IssuedSession:
        if await users.get_by_email(self._session, email) is not None:
            raise ConflictError("An account with this email already exists.", code="EMAIL_TAKEN")
        try:
            user = await users.add(
                self._session, email=email, password_hash=self._hasher.hash(password)
            )
        except IntegrityError as exc:
            # Two sign-ups racing past the check above: the unique index decides.
            raise ConflictError(
                "An account with this email already exists.", code="EMAIL_TAKEN"
            ) from exc
        issued = await self._issue(user, family_id=uuid.uuid4())
        await self._session.commit()
        log.info("auth.registered", user_id=str(user.id))
        return issued

    async def login(self, email: str, password: str) -> IssuedSession:
        user = await users.get_by_email(self._session, email)
        if user is None:
            self._hasher.burn_time(password)
            raise self._invalid_credentials()
        if not self._hasher.verify(user.password_hash, password):
            log.info("auth.login_failed", user_id=str(user.id))
            raise self._invalid_credentials()
        if self._hasher.needs_rehash(user.password_hash):
            # The only moment we have the plaintext: upgrade old hashes transparently.
            user.password_hash = self._hasher.hash(password)
        issued = await self._issue(user, family_id=uuid.uuid4())
        await self._session.commit()
        log.info("auth.logged_in", user_id=str(user.id))
        return issued

    async def refresh(self, raw_token: str) -> IssuedSession:
        now = self._clock()
        record = await refresh_tokens.get_by_hash_for_update(
            self._session, hash_refresh_token(raw_token)
        )
        if record is None or record.expires_at <= now:
            raise self._invalid_refresh_token()
        bind_context(user_id=str(record.user_id))

        if record.revoked_at is not None:
            if record.replaced_by_id is not None and now - record.revoked_at <= timedelta(
                seconds=self._settings.refresh_reuse_grace_seconds
            ):
                # Just rotated by a parallel request (two tabs opening at once): benign.
                # The browser already holds the successor cookie; the client retries.
                raise UnauthorizedError(
                    "This session was just refreshed. Retry with the new token.",
                    code="REFRESH_TOKEN_ROTATED",
                )
            # A token that was rotated or revoked long ago is being replayed: assume it was
            # stolen and end every session descending from that login.
            await refresh_tokens.revoke_family(self._session, record.family_id, now)
            await self._session.commit()
            log.warning("auth.refresh_token_reused", family_id=str(record.family_id))
            raise self._invalid_refresh_token()

        user = await users.get_by_id(self._session, record.user_id)
        if user is None:  # pragma: no cover  (ON DELETE CASCADE removes the token too)
            raise self._invalid_refresh_token()
        issued, successor = await self._issue_with_record(user, family_id=record.family_id)
        record.revoked_at = now
        record.replaced_by_id = successor.id
        await self._session.commit()
        return issued

    async def logout(self, raw_token: str | None) -> None:
        """Revoke this device's session. Idempotent: an unknown token is simply ignored."""
        if not raw_token:
            return
        record = await refresh_tokens.get_by_hash_for_update(
            self._session, hash_refresh_token(raw_token)
        )
        if record is not None:
            await refresh_tokens.revoke_family(self._session, record.family_id, self._clock())
            await self._session.commit()
            log.info("auth.logged_out", user_id=str(record.user_id))

    async def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> IssuedSession:
        """Set a new password, sign out every session, and start a fresh one for this device.

        Revoking *all* families (not "all but this one") keeps it simple: this route sees
        only the bearer token, not the refresh cookie, so it can't tell which family is
        the caller's — and the fresh session it returns replaces the caller's anyway.
        """
        user = await users.get_by_id(self._session, user_id)
        if user is None:
            raise UnauthorizedError("Invalid access token.", code="INVALID_TOKEN")
        if not self._hasher.verify(user.password_hash, current_password):
            # 422, not 401: the frontend treats 401 as "session expired" and would refresh.
            raise ValidationFailedError(
                "Current password is incorrect.", code="INVALID_CURRENT_PASSWORD"
            )
        user.password_hash = self._hasher.hash(new_password)
        await refresh_tokens.revoke_all_for_user(self._session, user.id, self._clock())
        issued = await self._issue(user, family_id=uuid.uuid4())
        await self._session.commit()
        log.info("auth.password_changed", user_id=str(user.id))
        return issued

    async def _issue(self, user: User, *, family_id: uuid.UUID) -> IssuedSession:
        issued, _ = await self._issue_with_record(user, family_id=family_id)
        return issued

    async def _issue_with_record(
        self, user: User, *, family_id: uuid.UUID
    ) -> tuple[IssuedSession, RefreshToken]:
        now = self._clock()
        raw = new_refresh_token()
        expires_at = now + timedelta(days=self._settings.refresh_token_ttl_days)
        record = await refresh_tokens.add(
            self._session,
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=expires_at,
        )
        issued = IssuedSession(
            user=user,
            access_token=create_access_token(user.id, self._settings, now=now),
            expires_in=self._settings.access_token_ttl_minutes * 60,
            refresh_token=raw,
            refresh_expires_at=expires_at,
        )
        return issued, record

    @staticmethod
    def _invalid_credentials() -> UnauthorizedError:
        # Same message whether the email exists or not.
        return UnauthorizedError("Incorrect email or password.", code="INVALID_CREDENTIALS")

    @staticmethod
    def _invalid_refresh_token() -> UnauthorizedError:
        return UnauthorizedError(
            "Your session has ended. Please sign in again.", code="INVALID_REFRESH_TOKEN"
        )
