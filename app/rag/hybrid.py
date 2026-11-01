"""
Hybrid retrieval: vector list + keyword list, then Reciprocal Rank Fusion.

RRF does not mix raw scores (they live on different scales). It only
uses rank:

    fused(d) = 1/(60 + rank_vector) + 1/(60 + rank_keyword)

A chunk that is #1 on both lists beats a chunk that is #1 on only one.
"""

from __future__ import annotations

from time import perf_counter

from app.rag.bm25 import bm25_rank, chunk_id


FETCH_K = 20
RRF_K = 60


def _from_document(document, score: float) -> dict:
    return {
        "content": document.page_content,
        "source": document.metadata.get("source"),
        "policy": document.metadata.get("policy"),
        "section": document.metadata.get("section"),
        "active": document.metadata.get("active", True),
        "score": round(float(score), 4),
        "vector_score": round(float(score), 4),
    }


def _from_mongo(row: dict) -> dict | None:
    if row.get("active") is False:
        return None
    content = row.get("text") or row.get("page_content") or ""
    if not content:
        return None
    return {
        "content": content,
        "source": row.get("source"),
        "policy": row.get("policy"),
        "section": row.get("section"),
        "active": row.get("active", True),
    }


async def load_active_chunks() -> list[dict]:
    from app.db.mongo import policy_collection

    rows = await policy_collection.find({}).to_list(length=500)
    chunks = []
    for row in rows:
        item = _from_mongo(row)
        if item:
            chunks.append(item)
    return chunks


async def vector_hits(query: str, k: int = FETCH_K) -> list[dict]:
    from app.rag.vector_store import vector_store

    pairs = await vector_store.asimilarity_search_with_score(query, k=k)
    hits = []
    for document, score in pairs:
        item = _from_document(document, score)
        if item.get("active") is False:
            continue
        hits.append(item)
    return hits


async def keyword_hits(query: str, k: int = FETCH_K) -> list[dict]:
    corpus = await load_active_chunks()
    return bm25_rank(query, corpus, k=k)


def reciprocal_rank_fusion(
    vector_list: list[dict],
    keyword_list: list[dict],
) -> list[dict]:
    ranks: dict[str, dict] = {}

    def add(items: list[dict], kind: str) -> None:
        for index, item in enumerate(items, start=1):
            key = chunk_id(item)
            slot = ranks.setdefault(key, {"item": dict(item), "rrf": 0.0})
            slot["item"].update({k: v for k, v in item.items() if v is not None})
            slot["rrf"] += 1.0 / (RRF_K + index)
            slot["item"][f"{kind}_rank"] = index

    add(vector_list, "vector")
    add(keyword_list, "keyword")

    fused = []
    for slot in ranks.values():
        item = slot["item"]
        item["rrf"] = round(slot["rrf"], 6)
        fused.append(item)
    fused.sort(key=lambda item: item["rrf"], reverse=True)
    return fused


async def hybrid_search(query: str, fetch_k: int = FETCH_K) -> dict:
    started = perf_counter()
    vectors = await vector_hits(query, k=fetch_k)
    keywords = await keyword_hits(query, k=fetch_k)
    fused = reciprocal_rank_fusion(vectors, keywords)
    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        "vector": vectors,
        "keyword": keywords,
        "fused": fused,
        "latency_ms": elapsed_ms,
    }
