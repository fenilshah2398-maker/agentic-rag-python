"""
Tiny BM25 — keyword search over the policy chunks already in Mongo.

Vector search is good at meaning ("send the shoes back" ≈ return).
It is weak at exact tokens ("5-7", "ORD-1002", a heading name).
BM25 scores those tokens the way a search box does.

We run this in Python over the small active set. A production app
would use Atlas Search. The fusion math later is the same.
"""

from __future__ import annotations

import math
import re
from collections import Counter


TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall((text or "").lower())


def chunk_id(chunk: dict) -> str:
    return f"{chunk.get('source')}|{chunk.get('section')}|{(chunk.get('content') or '')[:40]}"


def bm25_rank(query: str, corpus: list[dict], k: int = 20) -> list[dict]:
    """
    Score every chunk. Return the top k with keyword_score set.

    k1=1.5 and b=0.75 are the usual textbook defaults.
    """
    if not corpus:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    docs = [tokenize(item.get("content") or "") for item in corpus]
    lengths = [len(tokens) or 1 for tokens in docs]
    avg_len = sum(lengths) / len(lengths)
    df: Counter[str] = Counter()
    for tokens in docs:
        df.update(set(tokens))

    n = len(docs)
    k1 = 1.5
    b = 0.75
    scored = []
    for chunk, tokens, length in zip(corpus, docs, lengths):
        tf = Counter(tokens)
        score = 0.0
        for word in query_tokens:
            if word not in tf:
                continue
            idf = math.log(1 + (n - df[word] + 0.5) / (df[word] + 0.5))
            denom = tf[word] + k1 * (1 - b + b * length / avg_len)
            score += idf * (tf[word] * (k1 + 1)) / denom
        if score <= 0:
            continue
        item = dict(chunk)
        item["keyword_score"] = round(float(score), 4)
        scored.append(item)

    scored.sort(key=lambda item: item["keyword_score"], reverse=True)
    return scored[:k]
