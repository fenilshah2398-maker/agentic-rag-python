import secrets

from app.db.redis import redis_client

# A login lasts one day. After that Redis deletes the token.
SESSION_TTL_SECONDS = 60 * 60 * 24


async def create_session(user_id: str) -> str:
    """
    Create a random token and remember which user it belongs to.

    Redis key:  session:<token>
    Redis value: USER-A1B2C3
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