from argon2 import PasswordHasher as Argon2Hasher

from app.core.passwords import PasswordHasher
from tests.helpers import fast_hasher


def test_hash_is_argon2id_and_verifies() -> None:
    hasher = fast_hasher()
    password_hash = hasher.hash("Correct-Horse-9")
    assert password_hash.startswith("$argon2id$")
    assert hasher.verify(password_hash, "Correct-Horse-9")


def test_wrong_password_does_not_verify() -> None:
    hasher = fast_hasher()
    assert not hasher.verify(hasher.hash("Correct-Horse-9"), "correct-horse-9")


def test_garbage_hash_does_not_verify_or_raise() -> None:
    assert not fast_hasher().verify("not-a-hash", "anything")


def test_same_password_hashes_differently() -> None:
    # A random salt per hash: equal passwords don't produce equal hashes.
    hasher = fast_hasher()
    assert hasher.hash("Correct-Horse-9") != hasher.hash("Correct-Horse-9")


def test_hashes_made_with_weaker_parameters_need_rehash() -> None:
    weak = fast_hasher().hash("Correct-Horse-9")
    strong = PasswordHasher(Argon2Hasher(time_cost=2, memory_cost=2048, parallelism=1))
    assert strong.needs_rehash(weak)
    assert not strong.needs_rehash(strong.hash("Correct-Horse-9"))


def test_burn_time_never_matches() -> None:
    fast_hasher().burn_time("not-a-real-password")  # must not raise
