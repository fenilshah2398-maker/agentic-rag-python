"""
Score one eval case against an answer + the short RAG trace.

Three independent checks (this is the point of a golden set):

  tool choice  — did the agent call every required tool?
  retrieval    — did a required policy file (and optional section) show up?
  answer fact  — does the final sentence contain a known string?

A later change (hybrid search, better chunks, a new prompt) should
move these three numbers. If they do not move, the change did not
help — or did not hurt.

Retrieval is N/A when the case has no expected_sources and no
expected_sections (order-only questions never search policy docs).
"""

from __future__ import annotations

import re
from typing import Any


def normalize_text(text: str) -> str:
    cleaned = (text or "").lower()
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", cleaned).strip()


def _variants(text: str) -> set[str]:
    """
    "5-7" and "5 to 7" are the same fact for scoring.

    Models often rewrite a hyphen as the words "to".
    """
    normal = normalize_text(text)
    return {
        normal,
        normal.replace("-", " to "),
        normal.replace(" to ", "-"),
    }


def contains_fact(answer: str, fact: str) -> bool:
    answers = _variants(answer)
    facts = _variants(fact)
    return any(fact_text in answer_text for answer_text in answers for fact_text in facts)


def _actual_tools(trace: dict) -> list[dict]:
    return list(trace.get("tools") or [])


def _actual_sources(trace: dict) -> list[str]:
    sources = []
    for chunk in trace.get("chunks") or []:
        source = chunk.get("source")
        if source:
            sources.append(source)
    return sources


def _actual_sections(trace: dict) -> list[str]:
    sections = []
    for chunk in trace.get("chunks") or []:
        section = chunk.get("section")
        if section:
            sections.append(section)
    return sections


def score_case(case: dict, answer: str, trace: dict) -> dict:
    """
    Return a result dict for one case.

    tool_ok / answer_ok are True or False.
    retrieve_ok is True, False, or None (None = this case has no source).
    """
    expected_tools = list(case.get("expected_tools") or [])
    actual_tools = _actual_tools(trace)
    actual_names = [tool.get("name") for tool in actual_tools]
    tool_ok = set(expected_tools) <= set(actual_names)

    expected_order_id = case.get("expected_order_id")
    if expected_order_id:
        wanted = str(expected_order_id).upper()
        called = False
        for tool in actual_tools:
            if tool.get("name") != "get_order_by_id":
                continue
            got = str((tool.get("args") or {}).get("order_id") or "").upper()
            if got == wanted:
                called = True
                break
        tool_ok = tool_ok and called

    expected_sources = list(case.get("expected_sources") or [])
    expected_sections = list(case.get("expected_sections") or [])
    actual_sources = _actual_sources(trace)
    actual_sections = _actual_sections(trace)
    if expected_sources or expected_sections:
        source_ok = True
        if expected_sources:
            source_ok = any(source in actual_sources for source in expected_sources)
        section_ok = True
        if expected_sections:
            section_ok = any(
                section in actual_sections for section in expected_sections
            )
        retrieve_ok = source_ok and section_ok
    else:
        retrieve_ok = None

    missing: list[str] = []
    answer_ok = True
    for fact in case.get("must_contain") or []:
        if not contains_fact(answer, fact):
            answer_ok = False
            missing.append(fact)
    any_facts = list(case.get("must_contain_any") or [])
    if any_facts and not any(contains_fact(answer, fact) for fact in any_facts):
        answer_ok = False
        missing.append("any of: " + ", ".join(any_facts))

    return {
        "id": case["id"],
        "question": case["question"],
        "tool_ok": tool_ok,
        "retrieve_ok": retrieve_ok,
        "answer_ok": answer_ok,
        "expected_tools": expected_tools,
        "actual_tools": actual_names,
        "expected_sources": expected_sources,
        "actual_sources": actual_sources,
        "expected_sections": expected_sections,
        "actual_sections": actual_sections,
        "missing_facts": missing,
        "answer": answer,
        "error": None,
    }


def summarize(results: list[dict]) -> dict:
    """Turn a list of score_case() rows into the three percentages."""
    tool_hits = tool_total = 0
    retrieve_hits = retrieve_total = 0
    answer_hits = answer_total = 0

    for row in results:
        tool_total += 1
        tool_hits += int(bool(row["tool_ok"]))

        if row["retrieve_ok"] is not None:
            retrieve_total += 1
            retrieve_hits += int(bool(row["retrieve_ok"]))

        answer_total += 1
        answer_hits += int(bool(row["answer_ok"]))

    checks_hit = tool_hits + retrieve_hits + answer_hits
    checks_total = tool_total + retrieve_total + answer_total
    overall = (checks_hit / checks_total) if checks_total else 0.0

    return {
        "cases": len(results),
        "tool": {"hits": tool_hits, "total": tool_total},
        "retrieve": {"hits": retrieve_hits, "total": retrieve_total},
        "answer": {"hits": answer_hits, "total": answer_total},
        "overall": overall,
        "checks_hit": checks_hit,
        "checks_total": checks_total,
    }


def _mark(value: Any) -> str:
    if value is None:
        return "·"
    return "✓" if value else "✗"


def format_report(results: list[dict], summary: dict) -> str:
    lines = [
        "",
        "=" * 68,
        "RAG EVAL",
        "=" * 68,
    ]
    for index, row in enumerate(results, start=1):
        flag = ""
        if row.get("error"):
            flag = f"  error: {row['error']}"
        elif row["missing_facts"] and not row["answer_ok"]:
            flag = f"  missing {row['missing_facts']}"
        lines.append(
            f"{index:2}. {row['id']:<28} "
            f"tools {_mark(row['tool_ok'])}   "
            f"retrieve {_mark(row['retrieve_ok'])}   "
            f"answer {_mark(row['answer_ok'])}"
            f"{flag}"
        )

    tool = summary["tool"]
    retrieve = summary["retrieve"]
    answer = summary["answer"]
    lines.extend(
        [
            "-" * 68,
            f"tool choice   {tool['hits']}/{tool['total']}   {_pct(tool['hits'], tool['total'])}",
            f"retrieval     {retrieve['hits']}/{retrieve['total']}   {_pct(retrieve['hits'], retrieve['total'])}",
            f"answer fact   {answer['hits']}/{answer['total']}   {_pct(answer['hits'], answer['total'])}",
            f"overall                 {summary['overall'] * 100:.0f}%   "
            f"({summary['checks_hit']}/{summary['checks_total']} checks)",
            "=" * 68,
        ]
    )

    failures = [
        row
        for row in results
        if (not row["tool_ok"])
        or (row["retrieve_ok"] is False)
        or (not row["answer_ok"])
        or row.get("error")
    ]
    if failures:
        lines.append("FAILURES")
        for row in failures:
            lines.append(f"  {row['id']}")
            if row.get("error"):
                lines.append(f"    error: {row['error']}")
                continue
            if not row["tool_ok"]:
                lines.append(f"    expected tools: {row['expected_tools']}")
                lines.append(f"    actual tools:   {row['actual_tools']}")
            if row["retrieve_ok"] is False:
                if row.get("expected_sources"):
                    lines.append(f"    expected source in {row['expected_sources']}")
                    lines.append(f"    actual sources:    {row['actual_sources']}")
                if row.get("expected_sections"):
                    lines.append(f"    expected section in {row['expected_sections']}")
                    lines.append(f"    actual sections:    {row['actual_sections']}")
            if not row["answer_ok"]:
                lines.append(f"    missing facts: {row['missing_facts']}")
                lines.append(f"    answer: {row['answer'][:240]}")
        lines.append("=" * 68)

    return "\n".join(lines)


def _pct(hits: int, total: int) -> str:
    if not total:
        return "n/a"
    return f"{(hits / total) * 100:.0f}%"


def self_test() -> None:
    """Tiny fake traces so the scorer can be checked without Gemini."""
    case = {
        "id": "demo",
        "question": "How long is a refund?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["refund.md"],
        "must_contain": ["5-7"],
    }
    good = score_case(
        case,
        "Refunds take 5 to 7 business days.",
        {
            "tools": [{"name": "search_policy", "args": {"query": "refund"}}],
            "chunks": [{"source": "refund.md", "section": "Refund window", "score": 0.9}],
        },
    )
    assert good["tool_ok"] and good["retrieve_ok"] and good["answer_ok"]

    bad_tool = score_case(
        case,
        "Refunds take 5-7 business days.",
        {
            "tools": [{"name": "get_today_orders", "args": {}}],
            "chunks": [{"source": "refund.md", "score": 0.9}],
        },
    )
    assert bad_tool["tool_ok"] is False

    bad_source = score_case(
        case,
        "Refunds take 5-7 business days.",
        {
            "tools": [{"name": "search_policy", "args": {}}],
            "chunks": [{"source": "delivery.md", "score": 0.4}],
        },
    )
    assert bad_source["retrieve_ok"] is False

    bad_fact = score_case(
        case,
        "We will send the money soon.",
        {
            "tools": [{"name": "search_policy", "args": {}}],
            "chunks": [{"source": "refund.md", "score": 0.9}],
        },
    )
    assert bad_fact["answer_ok"] is False

    order_only = score_case(
        {
            "id": "today",
            "question": "What did I order today?",
            "expected_tools": ["get_today_orders"],
            "expected_sources": [],
            "must_contain_any": ["MacBook", "iPhone"],
        },
        "You ordered a MacBook Pro.",
        {"tools": [{"name": "get_today_orders", "args": {}}], "chunks": []},
    )
    assert order_only["retrieve_ok"] is None
    assert order_only["answer_ok"] is True

    print("eval self-test: 5 checks passed")
