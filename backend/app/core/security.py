"""`get_current_user`: the dependency every protected route uses (spec §8.3)."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.logging import bind_context
from app.core.tokens import decode_access_token


@dataclass(frozen=True)
class CurrentUser:
    id: UUID


def get_current_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> CurrentUser:
    header = request.headers.get("authorization")
    if header is None:
        raise UnauthorizedError("Sign in to continue.", code="MISSING_TOKEN")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Expected 'Authorization: Bearer <token>'.", code="MALFORMED_TOKEN")
    user_id = decode_access_token(token.strip(), settings)
    bind_context(user_id=str(user_id))  # every log line for this request names the user
    return CurrentUser(id=user_id)
