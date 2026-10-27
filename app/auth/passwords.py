"""
Password storage for sign-up and sign-in.

MongoDB stores a salt and a hash. It never stores the password text.
Sign-up creates a new salt. Sign-in reuses the saved salt and checks
that the typed password produces the same hash.
"""

import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    Turn a password into a stored hash.

    salt is random text mixed into the hash so two users with the same
    password do not get the same stored value.
    Returns (salt, hash). On sign-in we pass the saved salt back in.
    """
    # Sign-up calls this with no salt, so we create one.
    # Sign-in calls this with the salt already saved on the user document.
    if salt is None:
        salt = secrets.token_hex(16)

    # 120_000 repeats makes guessing a password slower.
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
    # compare_digest does not stop at the first different character,
    # so the timing of a wrong password leaks less information.
    return secrets.compare_digest(digest, password_hash)
