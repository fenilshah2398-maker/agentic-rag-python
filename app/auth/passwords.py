import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    Turn a password into a stored hash.

    salt is random bytes mixed into the hash so two users with the same
    password do not get the same stored value.
    Returns (salt, hash). On sign-in we pass the saved salt back in.
    """
    if salt is None:
        salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return salt, digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """True when this password reproduces the stored hash."""
    _, digest = hash_password(password, salt)
    return secrets.compare_digest(digest, password_hash)