import pytest
from pydantic import ValidationError

from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest


def test_email_is_lowercased_and_trimmed() -> None:
    body = RegisterRequest(email="  Om@Example.COM ", password="Correct-Horse-9")
    assert body.email == "om@example.com"


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("Short1", "at least 8"),
        ("alllowercase1", "an uppercase letter"),
        ("ALLUPPERCASE1", "a lowercase letter"),
        ("NoDigitsHere", "a number"),
        ("A1" + "a" * 127, "at most 128"),
    ],
)
def test_weak_passwords_are_rejected_with_the_reason(password: str, problem: str) -> None:
    with pytest.raises(ValidationError, match=problem):
        RegisterRequest(email="om@example.com", password=password)


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="Correct-Horse-9")


def test_login_does_not_apply_the_password_rules() -> None:
    # Telling a guesser "must contain a number" would narrow the search.
    assert LoginRequest(email="om@example.com", password="x").password == "x"


def test_new_password_follows_the_rules() -> None:
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="anything", new_password="weakpass")
