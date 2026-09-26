"""Request and response models for authentication and the account."""

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

PASSWORD_MIN_LENGTH = 8
# Argon2 accepts any length, but hashing megabytes per request is a cheap DoS; 128 is
# far beyond any passphrase a person types.
PASSWORD_MAX_LENGTH = 128


def _lowercase_email(value: str) -> str:
    # One account per address regardless of case: Om@x.com and om@x.com are the same person.
    return value.strip().lower()


def _password_rules(value: str) -> str:
    """The same rules the sign-up form shows (8+ chars, upper, lower, number)."""
    problems = []
    if not re.search(r"[A-Z]", value):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", value):
        problems.append("a lowercase letter")
    if not re.search(r"\d", value):
        problems.append("a number")
    if problems:
        raise ValueError(f"Password must contain {', '.join(problems)}.")
    return value


Email = Annotated[EmailStr, AfterValidator(_lowercase_email)]
# Rules apply only when a password is chosen; login accepts anything so it can't leak them.
NewPassword = Annotated[
    str,
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(_password_rules),
]
AnyPassword = Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class RegisterRequest(BaseModel):
    email: Email
    password: NewPassword


class LoginRequest(BaseModel):
    email: Email
    password: AnyPassword


class ChangePasswordRequest(BaseModel):
    current_password: AnyPassword
    new_password: NewPassword


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    github_username: str | None
    created_at: datetime


class SessionOut(BaseModel):
    """Returned by register, login, refresh and change-password. The refresh token is
    never in the body — it travels only in the HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  (the OAuth 2 scheme name, not a secret)
    expires_in: int = Field(description="Seconds until the access token expires.")
    user: UserOut
