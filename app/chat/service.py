from time import perf_counter

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import graph
from app.cache.chat_cache import get_cached_answer, question_hash, save_answer
from app.cache.memory import append_turn, load_history
from app.cache.semantic import get_semantic, save_semantic
from app.guardrails.input import REFUSALS, check_input
import re

_POLICY_ONLY_QUESTION = re.compile(
    r"\b(refund|return|policy|delivery|cancel|cancellation)\b",
    re.I,
)
_ORDER_ID = re.compile(r"\bord-\d+\b", re.I)
from app.guardrails.output import check_output, citations_from_chunks
from app.trace import public_trace_from_cache, start_trace


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


def _history_messages(history: list[dict]) -> list:
    messages = []
    for turn in history:
        text = turn.get("content") or ""
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=text))
        else:
            messages.append(AIMessage(content=text))
    return messages


def _parse_tool_content(content):
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        import json

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return content


def extract_approval(messages: list) -> dict | None:
    for message in reversed(messages or []):
        if getattr(message, "name", None) != "request_cancellation":
            continue
        payload = _parse_tool_content(getattr(message, "content", None))
        if isinstance(payload, dict) and payload.get("needs_approval"):
            return {
                "order_id": payload.get("order_id"),
                "product": payload.get("product"),
                "status": payload.get("status"),
                "message": payload.get("message"),
            }
    return None


def _policy_only(trace: dict) -> bool:
    names = [tool.get("name") for tool in (trace.get("tools") or [])]
    return bool(names) and all(name == "search_policy" for name in names)


async def run_agent(
    user_id: str,
    message: str,
    *,
    log_trace: bool = True,
    history: list[dict] | None = None,
) -> dict:
    """
    Run the LangGraph agent once. Does not read or write the Redis cache.
    """
    prior = _history_messages(history or [])
    with start_trace(message) as trace:
        started = perf_counter()
        result = await graph.ainvoke(
            {
                "messages": [*prior, HumanMessage(content=message)],
                "user_id": user_id,
            },
            {"recursion_limit": 12},
        )
        trace.finish(total_ms=int((perf_counter() - started) * 1000))
        trace.backfill_from_messages(result["messages"])
        last = result["messages"][-1]
        if getattr(last, "tool_calls", None):
            answer = "I reached the tool-round limit. Please ask a narrower question."
        else:
            answer = as_text(last.content)
        public = trace.to_public()
        if log_trace:
            trace.log()

    approval = extract_approval(result["messages"])
    chunks = trace.chunks
    answer = check_output(answer, chunks, public.get("abstain", False))
    sources = citations_from_chunks(chunks)
    public["sources"] = sources
    return {
        "answer": answer,
        "cached": False,
        "trace": public,
        "sources": sources,
        "approval": approval,
    }


async def answer_question(user_id: str, message: str) -> dict:
    """
    Live chat path:

    1. Input guardrail
    2. Exact Redis cache
    3. Semantic cache (policy questions only)
    4. Agent with conversation memory
    5. Output guardrail + citations
    """
    guard = check_input(message)
    if not guard["ok"]:
        return {
            "answer": REFUSALS[guard["reason"]],
            "cached": False,
            "trace": None,
            "sources": [],
            "approval": None,
            "blocked": guard["reason"],
        }

    cleaned = guard["cleaned"]
    q_hash = question_hash(user_id, cleaned)
    cached = await get_cached_answer(user_id, q_hash)
    if cached is not None:
        trace = public_trace_from_cache(cached.get("trace"))
        print(
            "\n======== RAG TRACE (cache hit) ========\n"
            f"question: {cleaned}\n"
            "agent skipped — exact Redis match\n"
            "======================================\n",
            flush=True,
        )
        return {
            "answer": cached["answer"],
            "cached": True,
            "cache_kind": "exact",
            "trace": trace,
            "sources": (cached.get("trace") or {}).get("sources") or [],
            "approval": None,
        }

    semantic = None
    if _POLICY_ONLY_QUESTION.search(cleaned) and not _ORDER_ID.search(cleaned):
        semantic = await get_semantic(user_id, cleaned)
    if semantic is not None:
        print(
            "\n======== RAG TRACE (semantic cache) ========\n"
            f"question: {cleaned}\n"
            f"similarity: {semantic['similarity']}\n"
            "============================================\n",
            flush=True,
        )
        return {
            "answer": semantic["answer"],
            "cached": True,
            "cache_kind": "semantic",
            "trace": public_trace_from_cache(semantic.get("trace")),
            "sources": semantic.get("sources") or [],
            "approval": None,
        }

    history = await load_history(user_id)
    payload = await run_agent(
        user_id,
        cleaned,
        history=history,
    )
    await append_turn(user_id, "user", cleaned)
    await append_turn(user_id, "assistant", payload["answer"])

    if not payload.get("approval"):
        await save_answer(
            user_id,
            q_hash,
            cleaned,
            payload["answer"],
            trace=payload["trace"],
        )
        if _policy_only(payload.get("trace") or {}):
            await save_semantic(
                user_id,
                cleaned,
                payload["answer"],
                payload.get("trace"),
                payload.get("sources"),
            )
    return payload
