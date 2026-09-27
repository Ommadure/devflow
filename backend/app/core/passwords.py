"""Password hashing with argon2id (the winner of the Password Hashing Competition and the
RFC 9106 recommendation). Argon2 is deliberately slow and memory-hard, so each guess
against a leaked hash costs real CPU and RAM.
"""

from functools import cached_property, lru_cache

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    def __init__(self, hasher: Argon2Hasher | None = None) -> None:
        # argon2-cffi's defaults are RFC 9106's "low memory" profile: 3 passes, 64 MiB, 4 lanes.
        self._hasher = hasher or Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """True when the hash was made with older/weaker parameters than today's."""
        return self._hasher.check_needs_rehash(password_hash)

    def burn_time(self, password: str) -> None:
        """Do the work of one verification for an email that has no account.

        Without it, "unknown email" answers in ~1 ms and "wrong password" in ~50 ms, and
        the difference tells an attacker which emails are registered.
        """
        self.verify(self._dummy_hash, password)

    @cached_property
    def _dummy_hash(self) -> str:
        return self._hasher.hash("not-a-real-password")


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return PasswordHasher()
