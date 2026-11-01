"""
Semantic cache — same meaning, not the same letters.

Exact cache: "What is the refund policy?" must match that string.
Semantic cache: "What's your refund policy?" can reuse the first answer
if the embeddings are close enough.

We only do this for policy questions. Order answers go stale.
"""

from __future__ import annotations

import json
import math

from app.db.redis import redis_client
from app.rag.embeddings import embeddings


THRESHOLD = 0.93
TTL_SECONDS = 600
MAX_ITEMS = 20


def _key(user_id: str) -> str:
    return f"chat:semantic:{user_id}"


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    n1 = math.sqrt(sum(a * a for a in left))
    n2 = math.sqrt(sum(b * b for b in right))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


async def get_semantic(user_id: str, question: str) -> dict | None:
    vector = embeddings.embed_query(question)
    raw_items = await redis_client.lrange(_key(user_id), 0, MAX_ITEMS - 1)
    best = None
    best_score = 0.0
    for raw in raw_items:
        item = json.loads(raw)
        score = cosine(vector, item.get("embedding") or [])
        if score > best_score:
            best_score = score
            best = item
    if best is None or best_score < THRESHOLD:
        return None
    return {
        "answer": best["answer"],
        "trace": best.get("trace"),
        "sources": best.get("sources") or [],
        "similarity": round(best_score, 4),
    }


async def save_semantic(
    user_id: str,
    question: str,
    answer: str,
    trace: dict | None,
    sources: list | None,
) -> None:
    vector = embeddings.embed_query(question)
    key = _key(user_id)
    item = json.dumps(
        {
            "question": question,
            "answer": answer,
            "trace": trace,
            "sources": sources or [],
            "embedding": vector,
        }
    )
    await redis_client.lpush(key, item)
    await redis_client.ltrim(key, 0, MAX_ITEMS - 1)
    await redis_client.expire(key, TTL_SECONDS)
