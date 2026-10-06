from langchain_core.messages import HumanMessage

from app.agent.graph import graph
from app.cache.chat_cache import get_cached_answer, question_hash, save_answer


def as_text(content) -> str:
    """Gemini sometimes returns a string, sometimes a list of text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


async def answer_question(user_id: str, message: str) -> dict:
    """
    Same path as POST /chat.

    1. Hash user + question and look in the last-5 Redis list.
    2. Hit  → return the saved answer.
    3. Miss → run the LangGraph agent, save the answer, return it.
    """
    q_hash = question_hash(user_id, message)
    cached = await get_cached_answer(user_id, q_hash)
    if cached is not None:
        return {"answer": cached, "cached": True}

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
        }
    )
    answer = as_text(result["messages"][-1].content)
    await save_answer(user_id, q_hash, message, answer)
    return {"answer": answer, "cached": False}