"""
Recall, then precision.

Hybrid search pulls ~20 chunks (recall: do not miss the right one).
Rerank keeps the best 4 (precision: do not stuff the prompt).

If even the best vector score is weak, we abstain. A low match is
not "close enough" — it is a reason to say we do not know.
"""

from time import perf_counter


FINAL_K = 4
# Atlas cosine on this small corpus: policy hits were ~0.85–0.90.
# Off-topic questions often still land ~0.70. This line is the gate.
ABSTAIN_MIN_VECTOR = 0.78


def _combined(chunk: dict) -> float:
    vector = float(chunk.get("vector_score") or chunk.get("score") or 0)
    rrf = float(chunk.get("rrf") or 0)
    return (0.7 * vector) + (0.3 * min(rrf * 30, 1.0))


def rerank_and_abstain(fused: list[dict], final_k: int = FINAL_K) -> dict:
    started = perf_counter()
    ranked = sorted(fused, key=_combined, reverse=True)
    top = ranked[:final_k]
    best_vector = 0.0
    best_keyword = 0.0
    if ranked:
        best_vector = max(
            float(item.get("vector_score") or item.get("score") or 0)
            for item in ranked
        )
        best_keyword = max(
            float(item.get("keyword_score") or 0) for item in ranked
        )
    # Weak vectors alone are not enough. A strong keyword hit
    # (exact "5-7", a heading) can still support an answer — and
    # covers the minute after ingest when Atlas has no vectors yet.
    abstain = not top or (
        best_vector < ABSTAIN_MIN_VECTOR and best_keyword < 1.0
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        "chunks": [] if abstain else top,
        "abstain": abstain,
        "best_vector": round(best_vector, 4),
        "latency_ms": elapsed_ms,
    }
