"""
Login sessions in Redis.

A token is a random string, not the user id and not the password.
The browser keeps the token. Redis remembers which user it belongs to.

    session:<token>  ->  USER-A1B2C3

The chat socket sends this token. FastAPI looks it up here and gets
the user_id. The question message itself does not carry a user id.
"""

import secrets

from app.db.redis import redis_client

# A login lasts one day. After that Redis deletes the key.
SESSION_TTL_SECONDS = 60 * 60 * 24


async def create_session(user_id: str) -> str:
    """
    Create a random token and remember which user it belongs to.

    Called at the end of both sign-up and sign-in.
    """
    token = secrets.token_urlsafe(32)
    await redis_client.set(f"session:{token}", user_id, ex=SESSION_TTL_SECONDS)
    return token


async def get_user_id(token: str) -> str | None:
    """Look up the user for this token. None means the login is missing or expired."""
    if not token:
        return None
    return await redis_client.get(f"session:{token}")


async def delete_session(token: str) -> None:
    """Sign-out. The token stops working immediately."""
    if token:
        await redis_client.delete(f"session:{token}")
