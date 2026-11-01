"""
HTTP response schema for chat answers.

main.py returns a plain dict. This model documents the shape:
  answer  — final sentence
  cached  — True when Redis served it
  sources — policy filenames (filled later when citations land)
  trace   — short RAG evidence for this question
"""

from pydantic import BaseModel


class TraceChunk(BaseModel):
    source: str | None = None
    policy: str | None = None
    section: str | None = None
    score: float | None = None
    preview: str = ""


class TraceTool(BaseModel):
    name: str
    args: dict = {}


class TraceLatency(BaseModel):
    total: int = 0
    llm: int = 0
    retrieve: int = 0


class TraceTokens(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0


class ChatTrace(BaseModel):
    question: str = ""
    search_query: str | None = None
    tools: list[TraceTool] = []
    chunks: list[TraceChunk] = []
    latency_ms: TraceLatency = TraceLatency()
    tokens: TraceTokens = TraceTokens()
    from_cache: bool = False


class Citation(BaseModel):
    source: str | None = None
    section: str | None = None


class ChatResponse(BaseModel):
    answer: str
    cached: bool = False
    cache_kind: str | None = None
    sources: list[Citation] = []
    trace: ChatTrace | None = None
