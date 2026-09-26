"""Auth routes: register, login, refresh, logout.

Only /auth/refresh and /auth/logout read the refresh cookie; its Path keeps the browser
from sending it anywhere else. Every other route authenticates with the bearer header.
"""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import (
    AuthServiceDep,
    RateLimiterDep,
    SettingsDep,
    client_ip,
    enforce,
)
from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.rate_limit import Rule, hashed
from app.schemas.auth import LoginRequest, RegisterRequest, SessionOut, UserOut
from app.services.auth import IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "devflow_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

LOGIN_PER_IP = Rule(limit=10, window_seconds=60)
LOGIN_PER_EMAIL = Rule(limit=5, window_seconds=60)
REGISTER_PER_IP = Rule(limit=5, window_seconds=3600)

AUTH_ERRORS: dict[int | str, dict[str, str]] = {
    401: {"description": "Not authenticated"},
    429: {"description": "Rate limited"},
}


@router.post("/register", status_code=status.HTTP_201_CREATED, responses=AUTH_ERRORS)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> SessionOut:
    await enforce(limiter, f"register:ip:{client_ip(request)}", REGISTER_PER_IP)
    issued = await auth.register(body.email, body.password)
    return start_session(response, issued, settings)


@router.post("/login", responses=AUTH_ERRORS)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> SessionOut:
    # Per IP stops one machine trying many accounts; per email stops many machines
    # trying one account.
    await enforce(limiter, f"login:ip:{client_ip(request)}", LOGIN_PER_IP)
    await enforce(limiter, f"login:email:{hashed(body.email)}", LOGIN_PER_EMAIL)
    issued = await auth.login(body.email, body.password)
    return start_session(response, issued, settings)


@router.post("/refresh", responses=AUTH_ERRORS)
async def refresh(
    request: Request, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> SessionOut:
    _check_origin(request, settings)
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise UnauthorizedError("No active session.", code="INVALID_REFRESH_TOKEN")
    issued = await auth.refresh(raw)
    return start_session(response, issued, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> None:
    _check_origin(request, settings)
    await auth.logout(request.cookies.get(REFRESH_COOKIE))
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def start_session(response: Response, issued: IssuedSession, settings: Settings) -> SessionOut:
    set_refresh_cookie(response, issued, settings)
    return SessionOut(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        user=UserOut.model_validate(issued.user),
    )


def set_refresh_cookie(response: Response, issued: IssuedSession, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        expires=issued.refresh_expires_at,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,  # JavaScript can never read it, so XSS can't steal it
        samesite="lax",  # not sent on cross-site POSTs: the first CSRF defence
    )


def _check_origin(request: Request, settings: Settings) -> None:
    """Second CSRF defence for the cookie-authenticated routes.

    Browsers send Origin on every POST; a page on another site can't forge it. Clients
    without an Origin (curl, tests) aren't browsers, so they can't be tricked into
    sending someone else's cookie in the first place.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.cors_origin_list:
        raise ForbiddenError("Request origin is not allowed.", code="ORIGIN_NOT_ALLOWED")
