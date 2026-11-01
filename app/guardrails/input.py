"""
Input guardrail — runs BEFORE the agent.

The system prompt already says "be good". That is not a lock.
This file is Python. It can refuse a question without calling Gemini.

Three jobs:
  1. Strip emails / long digit runs that look like secrets
  2. Block prompt-injection phrases
  3. Block questions that are not about orders or policy
"""

from __future__ import annotations

import re


INJECTION = [
    re.compile(r"ignore (all )?(previous|above|prior) instructions", re.I),
    re.compile(r"reveal (your )?(system )?prompt", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"disregard (your|the) (rules|instructions)", re.I),
]

TOPIC = re.compile(
    r"\b(refund|return|cancel|cancellation|order|delivery|ship|"
    r"policy|policies|ord-\d+|payment|money|back|track|window)\b",
    re.I,
)

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
LONG_DIGITS = re.compile(r"\b\d{12,}\b")


def strip_secrets(text: str) -> str:
    cleaned = EMAIL.sub("[redacted-email]", text)
    cleaned = LONG_DIGITS.sub("[redacted-number]", cleaned)
    return cleaned


def check_input(message: str) -> dict:
    """
    Return {ok, reason, cleaned}.

    ok=False means FastAPI should answer itself and skip the graph.
    """
    raw = (message or "").strip()
    if not raw:
        return {"ok": False, "reason": "empty", "cleaned": ""}

    cleaned = strip_secrets(raw)
    for pattern in INJECTION:
        if pattern.search(cleaned):
            return {
                "ok": False,
                "reason": "injection",
                "cleaned": cleaned,
            }

    if not TOPIC.search(cleaned):
        return {
            "ok": False,
            "reason": "off_topic",
            "cleaned": cleaned,
        }

    return {"ok": True, "reason": None, "cleaned": cleaned}


REFUSALS = {
    "empty": "Type a question first.",
    "injection": "I cannot follow that request.",
    "off_topic": (
        "I only answer questions about your orders and company policy "
        "(refund, return, cancellation, delivery)."
    ),
}
