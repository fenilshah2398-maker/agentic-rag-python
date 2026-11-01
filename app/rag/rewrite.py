"""
Turn a long user sentence into a short search string.

The question you answer and the query you embed are not the same.

  "can I send the shoes back if they don't fit?"
      → "return policy time limit"

A short query already looks like a search string, so we skip the
extra Gemini call.
"""

from time import perf_counter

from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.llm import llm


REWRITE_PROMPT = """
Rewrite the text into a short search query for company policy docs.

Keep only the topic words. No full sentence. No question mark.
Topics you may see: refund, return, cancellation, delivery, order.
Return only the query.
"""


def already_short(query: str) -> bool:
    words = query.strip().rstrip("?").strip().split()
    return len(words) <= 6


async def rewrite_query(query: str) -> tuple[str, int]:
    """
    Return (search_query, latency_ms).

    On any model error, keep the original query so search still runs.
    """
    cleaned = " ".join((query or "").split()).strip()
    if not cleaned:
        return "", 0
    if already_short(cleaned):
        return cleaned, 0

    started = perf_counter()
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=REWRITE_PROMPT),
                HumanMessage(content=cleaned),
            ]
        )
        text = (response.content or "").strip()
        if isinstance(text, list):
            text = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in text
            ).strip()
        rewritten = " ".join(str(text).split())
        if not rewritten:
            rewritten = cleaned
    except Exception:
        rewritten = cleaned
    elapsed_ms = int((perf_counter() - started) * 1000)
    return rewritten, elapsed_ms
