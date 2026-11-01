"""
Output guardrail — runs AFTER the agent.

If search abstained, the model must not invent a policy sentence.
If search returned chunks, the answer must share real words with them.
Otherwise we replace the answer. The prompt is not trusted here either.
"""

from __future__ import annotations

import re


DONT_KNOW = "I don't have that in the policy."

WORD = re.compile(r"[a-z0-9]{4,}")


def _words(text: str) -> set[str]:
    return set(WORD.findall((text or "").lower()))


def is_grounded(answer: str, chunks: list[dict]) -> bool:
    if not chunks:
        return False
    answer_words = _words(answer)
    if not answer_words:
        return False
    for chunk in chunks:
        overlap = answer_words & _words(chunk.get("content") or "")
        if len(overlap) >= 2:
            return True
    return False


def check_output(answer: str, chunks: list[dict], abstain: bool) -> str:
    text = (answer or "").strip()
    if abstain:
        return DONT_KNOW
    if chunks and text and not is_grounded(text, chunks):
        return DONT_KNOW
    return text or DONT_KNOW


def citations_from_chunks(chunks: list[dict]) -> list[dict]:
    seen = set()
    citations = []
    for chunk in chunks or []:
        source = chunk.get("source")
        section = chunk.get("section")
        key = (source, section)
        if not source or key in seen:
            continue
        seen.add(key)
        citations.append({"source": source, "section": section})
    return citations
