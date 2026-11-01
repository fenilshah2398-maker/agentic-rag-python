"""
Request-scoped RAG trace.

Why this exists:
  The chat API used to return only the final sentence. When an answer
  looked wrong you could not tell if the model picked the wrong tool,
  retrieved the wrong chunks, or just worded the answer badly.

  A trace is the evidence for one question:
    question       — what the user typed
    search_query   — the string that was actually embedded (the tool
                     often rewrites the user sentence; later we will
                     add a dedicated rewrite step)
    tools          — every tool the model asked to run
    chunks         — retrieved policy passages with Atlas scores
    latency_ms     — how long the LLM and the vector search took
    tokens         — prompt + completion tokens from Gemini

How it travels:
  start_trace() puts one RequestTrace on a contextvar. That is a
  per-request pocket: the retriever and the agent node can write into
  it without passing the object through every function. Two users
  chatting at once each get their own pocket.

The full trace is printed in the FastAPI terminal.
A shorter copy is sent to the chat page and saved with the Redis cache.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger("rag.trace")

# One trace per in-flight question. Default None when nothing is running.
_current: ContextVar[RequestTrace | None] = ContextVar(
    "rag_trace",
    default=None,
)

PREVIEW_CHARS = 140


def current_trace() -> RequestTrace | None:
    """The trace for the question FastAPI is answering right now, or None."""
    return _current.get()


@contextmanager
def start_trace(question: str):
    """
    Open a trace for one question and close it when the block ends.

    Usage in chat/service.py:

        with start_trace(message) as trace:
            result = await graph.ainvoke(...)
            trace.finish(total_ms=...)
    """
    trace = RequestTrace(question=question)
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


def _as_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "items"):
        return dict(value)
    return {}


def extract_tokens(message: Any) -> dict[str, int]:
    """
    Gemini / LangChain put token counts in a few different pockets.

    We look in this order:
      1. message.usage_metadata              (LangChain standard)
      2. message.response_metadata.usage_metadata
      3. message.response_metadata.token_usage
    """
    usage = _as_dict(getattr(message, "usage_metadata", None))
    if not usage:
        meta = _as_dict(getattr(message, "response_metadata", None))
        usage = _as_dict(meta.get("usage_metadata")) or _as_dict(
            meta.get("token_usage")
        )

    input_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("prompt_token_count")
        or 0
    )
    output_tokens = (
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("candidates_token_count")
        or 0
    )
    total_tokens = (
        usage.get("total_tokens")
        or usage.get("total_token_count")
        or (int(input_tokens) + int(output_tokens))
    )
    return {
        "input": int(input_tokens or 0),
        "output": int(output_tokens or 0),
        "total": int(total_tokens or 0),
    }


def extract_tool_calls(message: Any) -> list[dict]:
    """Turn AIMessage.tool_calls into plain {name, args} dicts."""
    raw_calls = getattr(message, "tool_calls", None) or []
    calls = []
    for call in raw_calls:
        if isinstance(call, dict):
            name = call.get("name") or ""
            args = call.get("args") or {}
        else:
            name = getattr(call, "name", "") or ""
            args = getattr(call, "args", {}) or {}
        calls.append({"name": name, "args": dict(args)})
    return calls


LATENCY_BUDGET_MS = {
    "rewrite": 4000,
    "retrieve": 3000,
    "rerank": 200,
    "llm": 20000,
    "total": 25000,
}


@dataclass
class RequestTrace:
    question: str
    search_queries: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    vector_hits: list[dict] = field(default_factory=list)
    keyword_hits: list[dict] = field(default_factory=list)
    llm_ms: int = 0
    retrieve_ms: int = 0
    rewrite_ms: int = 0
    rerank_ms: int = 0
    total_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    from_cache: bool = False
    abstain: bool = False
    best_vector: float | None = None
    original_query: str | None = None

    def record_llm(self, message: Any, latency_ms: int) -> None:
        """One THINK step: how long Gemini took, tokens, and any tool calls."""
        self.llm_ms += int(latency_ms)
        tokens = extract_tokens(message)
        self.tokens_input += tokens["input"]
        self.tokens_output += tokens["output"]
        self.tokens_total += tokens["total"]
        self.tools.extend(extract_tool_calls(message))

    def record_retrieval(
        self,
        query: str,
        chunks: list[dict],
        latency_ms: int,
    ) -> None:
        """Kept for backfill / older callers."""
        self.search_queries.append(query)
        self.retrieve_ms += int(latency_ms)
        self.chunks.extend(chunks)

    def record_rewrite(self, original: str, rewritten: str, latency_ms: int) -> None:
        self.original_query = original
        self.search_queries.append(rewritten)
        self.rewrite_ms += int(latency_ms)

    def record_hybrid(
        self,
        query: str,
        vector: list[dict],
        keyword: list[dict],
        chunks: list[dict],
        retrieve_ms: int,
        rerank_ms: int,
        abstain: bool,
        best_vector: float,
    ) -> None:
        if query and query not in self.search_queries:
            self.search_queries.append(query)
        self.vector_hits = vector[:5]
        self.keyword_hits = keyword[:5]
        self.chunks = list(chunks)
        self.retrieve_ms += int(retrieve_ms)
        self.rerank_ms += int(rerank_ms)
        self.abstain = abstain
        self.best_vector = best_vector

    def finish(self, total_ms: int) -> None:
        self.total_ms = int(total_ms)

    def backfill_from_messages(self, messages: list) -> None:
        """
        Fill any holes from the graph transcript.

        The retriever and agent_node write live. If a LangGraph worker
        dropped the contextvar, the ToolMessages still hold the chunks
        (with scores) and the AIMessages still hold tool_calls + tokens.
        """
        if not self.tools:
            for message in messages:
                self.tools.extend(extract_tool_calls(message))

        if not self.search_queries:
            for tool in self.tools:
                if tool.get("name") != "search_policy":
                    continue
                query = (tool.get("args") or {}).get("query")
                if query:
                    self.search_queries.append(str(query))

        if not self.chunks:
            for message in messages:
                if getattr(message, "name", None) != "search_policy":
                    continue
                payload = _parse_tool_payload(getattr(message, "content", None))
                if isinstance(payload, dict):
                    self.chunks.extend(payload.get("chunks") or [])
                    self.abstain = bool(payload.get("abstain"))
                elif isinstance(payload, list):
                    self.chunks.extend(payload)

        if self.tokens_total == 0:
            for message in messages:
                tokens = extract_tokens(message)
                self.tokens_input += tokens["input"]
                self.tokens_output += tokens["output"]
                self.tokens_total += tokens["total"]

    @property
    def search_query(self) -> str | None:
        """Latest search string. None if the policy tool never ran."""
        if not self.search_queries:
            return None
        return self.search_queries[-1]

    def to_public(self) -> dict:
        """
        Short copy for the chat page and the Redis cache.

        Chunks keep source + score + a preview. Full text stays in the
        server log so the WebSocket payload stays small.
        """
        return {
            "question": self.question,
            "original_query": self.original_query,
            "search_query": self.search_query,
            "tools": self.tools,
            "chunks": [
                {
                    "source": chunk.get("source"),
                    "policy": chunk.get("policy"),
                    "section": chunk.get("section"),
                    "score": chunk.get("score") or chunk.get("vector_score"),
                    "preview": _preview(chunk.get("content") or ""),
                }
                for chunk in self.chunks
            ],
            "vector_hits": [
                {
                    "source": hit.get("source"),
                    "section": hit.get("section"),
                    "score": hit.get("score"),
                }
                for hit in self.vector_hits
            ],
            "keyword_hits": [
                {
                    "source": hit.get("source"),
                    "section": hit.get("section"),
                    "score": hit.get("keyword_score"),
                }
                for hit in self.keyword_hits
            ],
            "latency_ms": {
                "total": self.total_ms,
                "llm": self.llm_ms,
                "rewrite": self.rewrite_ms,
                "retrieve": self.retrieve_ms,
                "rerank": self.rerank_ms,
            },
            "over_budget": self.over_budget(),
            "tokens": {
                "input": self.tokens_input,
                "output": self.tokens_output,
                "total": self.tokens_total,
            },
            "from_cache": self.from_cache,
            "abstain": self.abstain,
            "best_vector": self.best_vector,
        }

    def over_budget(self) -> list[str]:
        flags = []
        pairs = {
            "rewrite": self.rewrite_ms,
            "retrieve": self.retrieve_ms,
            "rerank": self.rerank_ms,
            "llm": self.llm_ms,
            "total": self.total_ms,
        }
        for name, value in pairs.items():
            if value > LATENCY_BUDGET_MS[name]:
                flags.append(name)
        return flags

    def format_log(self) -> str:
        """Human-readable block for the FastAPI terminal."""
        lines = [
            "",
            "=" * 64,
            "RAG TRACE",
            "=" * 64,
            f"question      : {self.question}",
            f"original_query: {self.original_query or '(same as question)'}",
            f"search_query  : {self.search_query or '(policy tool not used)'}",
            "tools         :",
        ]
        if not self.tools:
            lines.append("  (none)")
        for index, tool in enumerate(self.tools, start=1):
            args = json.dumps(tool.get("args") or {}, ensure_ascii=True)
            lines.append(f"  {index}. {tool.get('name')}  {args}")

        lines.append("vector_hits   :")
        if not self.vector_hits:
            lines.append("  (none)")
        for index, hit in enumerate(self.vector_hits, start=1):
            lines.append(
                f"  {index}. {hit.get('source')} · {hit.get('section')}  "
                f"score={hit.get('score')}"
            )
        lines.append("keyword_hits  :")
        if not self.keyword_hits:
            lines.append("  (none)")
        for index, hit in enumerate(self.keyword_hits, start=1):
            lines.append(
                f"  {index}. {hit.get('source')} · {hit.get('section')}  "
                f"bm25={hit.get('keyword_score')}"
            )
        lines.append(
            f"abstain       : {self.abstain}  best_vector={self.best_vector}"
        )
        lines.append("chunks        :")
        if not self.chunks:
            lines.append("  (none)")
        for index, chunk in enumerate(self.chunks, start=1):
            score = chunk.get("score")
            source = chunk.get("source") or "?"
            content = (chunk.get("content") or "").replace("\n", " ").strip()
            policy = chunk.get("policy") or "?"
            section = chunk.get("section") or "?"
            lines.append(
                f"  {index}. score={score}  source={source}  "
                f"policy={policy}  section={section}"
            )
            lines.append(f"     {content}")

        over = self.over_budget()
        lines.append(
            "latency_ms    : "
            f"total={self.total_ms}  llm={self.llm_ms}  "
            f"rewrite={self.rewrite_ms}  retrieve={self.retrieve_ms}  "
            f"rerank={self.rerank_ms}"
        )
        if over:
            lines.append(f"over_budget   : {', '.join(over)}")
        lines.append(
            "tokens        : "
            f"input={self.tokens_input}  output={self.tokens_output}  "
            f"total={self.tokens_total}"
        )
        if self.from_cache:
            lines.append("cache         : HIT (agent did not run)")
        lines.append("=" * 64)
        return "\n".join(lines)

    def log(self) -> None:
        text = self.format_log()
        logger.info(text)
        # uvicorn shows print() in the same terminal you started it from
        print(text, flush=True)


def _parse_tool_payload(content: Any) -> Any:
    """ToolMessage.content is often a JSON string of the Python return value."""
    if isinstance(content, (list, dict)):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return content


def _preview(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= PREVIEW_CHARS:
        return cleaned
    return cleaned[: PREVIEW_CHARS - 1] + "…"


def public_trace_from_cache(stored: dict | None) -> dict:
    """Mark a saved trace as a cache hit so the UI can say so."""
    if not stored:
        return {
            "question": "",
            "search_query": None,
            "tools": [],
            "chunks": [],
            "latency_ms": {"total": 0, "llm": 0, "retrieve": 0},
            "tokens": {"input": 0, "output": 0, "total": 0},
            "from_cache": True,
        }
    return {**stored, "from_cache": True}
