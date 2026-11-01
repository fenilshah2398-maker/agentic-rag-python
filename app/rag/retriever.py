"""
Online RAG path used by search_policy.

  user / tool query
    → rewrite into a short search string
    → hybrid (vector + BM25 + RRF)
    → rerank, keep 4, or abstain
    → write everything onto the request trace
"""

from app.rag.hybrid import hybrid_search
from app.rag.rerank import rerank_and_abstain
from app.rag.rewrite import rewrite_query
from app.trace import current_trace


async def search_policy_chunks(query: str) -> dict:
    rewritten, rewrite_ms = await rewrite_query(query)
    search_query = rewritten or query

    hybrid = await hybrid_search(search_query)
    decided = rerank_and_abstain(hybrid["fused"])

    trace = current_trace()
    if trace is not None:
        trace.record_rewrite(query, search_query, rewrite_ms)
        trace.record_hybrid(
            query=search_query,
            vector=hybrid["vector"],
            keyword=hybrid["keyword"],
            chunks=decided["chunks"],
            retrieve_ms=hybrid["latency_ms"],
            rerank_ms=decided["latency_ms"],
            abstain=decided["abstain"],
            best_vector=decided["best_vector"],
        )

    if decided["abstain"]:
        return {
            "abstain": True,
            "reason": "no supporting policy",
            "search_query": search_query,
            "chunks": [],
        }

    return {
        "abstain": False,
        "search_query": search_query,
        "chunks": decided["chunks"],
    }
