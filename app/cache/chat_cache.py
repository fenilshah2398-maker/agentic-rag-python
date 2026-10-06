"""
Last-5 answer cache, one list per user.

A hash is a fingerprint of the text. Same user + same cleaned question
always produces the same hash. Change the user or the words, and the
hash changes, so we do not return the wrong person's answer.
"""

import hashlib
import json
import re

from app.db.redis import redis_client

# Keep this many recent answers for one user.
MAX_RECENT = 5

# Drop the list after 10 minutes so "what did I order today?" cannot
# stay correct-looking after the orders change.
CACHE_TTL_SECONDS = 600


def normalize(message: str) -> str:
    """
    Ignore capital letters and extra spaces before hashing.

    "  What is the Refund Policy?  "
    becomes
    "what is the refund policy?"
    """
    cleaned = message.strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def question_hash(user_id: str, message: str) -> str:
    """
    Fingerprint of user_id + cleaned question.

    USER-001 + "what is the refund policy?" → one hash
    USER-002 + the same sentence            → a different hash
    """
    raw = f"{user_id}|{normalize(message)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _key(user_id: str) -> str:
    """Redis list name. Example: chat:recent:USER-001"""
    return f"chat:recent:{user_id}"


async def get_cached_answer(user_id: str, q_hash: str) -> str | None:
    """
    Read this user's list and return the answer if the hash is in it.

    None means the question is not among the last 5, so the agent must run.
    """
    raw_items = await redis_client.lrange(_key(user_id), 0, MAX_RECENT - 1)

    for raw in raw_items:
        item = json.loads(raw)
        if item["hash"] == q_hash:
            return item["answer"]

    return None


async def save_answer(
    user_id: str,
    q_hash: str,
    question: str,
    answer: str,
) -> None:
    """
    Store one new answer and throw away anything older than the last 5.

    LPUSH  → put this item at the front (newest)
    LTRIM  → keep indexes 0 through 4
    EXPIRE → restart the 10-minute timer
    """
    key = _key(user_id)
    item = json.dumps(
        {
            "hash": q_hash,
            "question": normalize(question),
            "answer": answer,
        }
    )

    await redis_client.lpush(key, item)
    await redis_client.ltrim(key, 0, MAX_RECENT - 1)
    await redis_client.expire(key, CACHE_TTL_SECONDS)