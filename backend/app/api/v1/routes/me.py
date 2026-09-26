"""The signed-in user's own account."""

from fastapi import APIRouter, Response

from app.api.deps import (
    AuthServiceDep,
    CurrentUserDep,
    RateLimiterDep,
    SessionDep,
    SettingsDep,
    enforce,
)
from app.api.v1.routes.auth import start_session
from app.core.errors import UnauthorizedError
from app.core.rate_limit import Rule
from app.repositories import users
from app.schemas.auth import ChangePasswordRequest, SessionOut, UserOut

router = APIRouter(prefix="/me", tags=["account"])

CHANGE_PASSWORD_PER_USER = Rule(limit=5, window_seconds=900)


@router.get("", responses={401: {"description": "Not authenticated"}})
async def get_me(current: CurrentUserDep, session: SessionDep) -> UserOut:
    user = await users.get_by_id(session, current.id)
    if user is None:
        # A valid token for a user that no longer exists.
        raise UnauthorizedError("Invalid access token.", code="INVALID_TOKEN")
    return UserOut.model_validate(user)


@router.post(
    "/password",
    responses={
        401: {"description": "Not authenticated"},
        422: {"description": "Current password incorrect, or new password too weak"},
        429: {"description": "Rate limited"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    current: CurrentUserDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    limiter: RateLimiterDep,
) -> SessionOut:
    """Change the password, sign out every session, and return a fresh one for this device."""
    # A stolen access token must not become unlimited guesses at the current password.
    await enforce(limiter, f"password:user:{current.id}", CHANGE_PASSWORD_PER_USER)
    issued = await auth.change_password(current.id, body.current_password, body.new_password)
    return start_session(response, issued, settings)
