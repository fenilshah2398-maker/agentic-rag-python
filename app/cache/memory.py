"""
Conversation memory — last few user/assistant turns per user.

Each chat question used to start a brand new graph. "And for returns?"
then had no link to the refund answer above it.

We store only the spoken turns (not tool JSON) in Redis, and send
the last 6 with the new question.
"""

import json

from app.db.redis import redis_client


MAX_TURNS = 6
TTL_SECONDS = 60 * 60 * 24


def _key(user_id: str) -> str:
    return f"chat:memory:{user_id}"


async def load_history(user_id: str) -> list[dict]:
    raw = await redis_client.lrange(_key(user_id), 0, MAX_TURNS - 1)
    turns = []
    for item in reversed(raw):
        try:
            turns.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return turns


async def append_turn(user_id: str, role: str, content: str) -> None:
    key = _key(user_id)
    await redis_client.lpush(
        key,
        json.dumps({"role": role, "content": content}),
    )
    await redis_client.ltrim(key, 0, MAX_TURNS - 1)
    await redis_client.expire(key, TTL_SECONDS)
