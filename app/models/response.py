"""
HTTP response schema for chat answers.

Currently main.py returns a plain dict {"answer": ...}.
This model documents the intended API shape and can be used as
response_model=ChatResponse on the FastAPI route later.

sources is optional metadata (e.g. policy filenames) for citations —
not wired in main.py yet, but ready for a future enhancement.
"""

from pydantic import BaseModel


class ChatResponse(BaseModel):
    # Final natural-language answer from the agent
    answer: str

    # Optional list of document/source names used (default empty)
    sources: list[str] = []
