"""
Policy tool — hybrid RAG inside the agent.

search_policy(query) now:
  1. rewrites the query if it is a long sentence
  2. runs vector + keyword search
  3. fuses with RRF, reranks, maybe abstains
  4. returns {abstain, search_query, chunks}
"""

from langchain_core.tools import tool

from app.rag.retriever import search_policy_chunks


@tool
async def search_policy(query: str):
    """
    Search company policy documents for cancellation, refund,
    delivery and returns. Use a short topical query.
    """

    return await search_policy_chunks(query)
