"""
Run the golden RAG eval.

From the project root:

    python -m scripts.eval_rag
    python -m scripts.eval_rag --self-test
    python -m scripts.eval_rag --limit 3
    python -m scripts.eval_rag --id refund-window,today-orders

What it does:
  1. Load cases from app/eval/cases.py
  2. Call the real agent for each question (no Redis cache)
  3. Score tool choice, retrieval hit, and a required fact
  4. Print a table you can re-run after every later change
  5. Write evals/last_run.json so you can compare two runs

Order cases need the seed data:

    python -m scripts.seed_orders
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.eval.cases import CASES, EVAL_USER_ID
from app.eval.scoring import format_report, score_case, self_test, summarize


RESULTS_PATH = Path("evals/last_run.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Score the support agent on a fixed set of questions.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Score fake traces. Does not call Gemini or MongoDB.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only the first N cases (0 = all).",
    )
    parser.add_argument(
        "--id",
        default="",
        help="Comma-separated case ids, e.g. refund-window,today-orders",
    )
    return parser.parse_args()


def select_cases(args) -> list[dict]:
    cases = list(CASES)
    if args.id:
        wanted = {item.strip() for item in args.id.split(",") if item.strip()}
        missing = wanted - {case["id"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown case id(s): {sorted(missing)}")
        cases = [case for case in cases if case["id"] in wanted]
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
    return cases


async def run_one(case: dict) -> dict:
    # Imported here so --self-test never loads Gemini / Atlas.
    from app.chat.service import run_agent

    user_id = case.get("user_id") or EVAL_USER_ID
    try:
        payload = await run_agent(
            user_id,
            case["question"],
            log_trace=False,
        )
    except Exception as exc:
        return {
            "id": case["id"],
            "question": case["question"],
            "tool_ok": False,
            "retrieve_ok": False if (case.get("expected_sources") or case.get("expected_sections")) else None,
            "answer_ok": False,
            "expected_tools": case.get("expected_tools") or [],
            "actual_tools": [],
            "expected_sources": case.get("expected_sources") or [],
            "actual_sources": [],
            "expected_sections": case.get("expected_sections") or [],
            "actual_sections": [],
            "missing_facts": [],
            "answer": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return score_case(case, payload["answer"], payload.get("trace") or {})


async def run_eval(cases: list[dict]) -> list[dict]:
    results = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{total}] {case['id']}: {case['question']}", flush=True)
        result = await run_one(case)
        mark = "ok" if result["tool_ok"] and result["answer_ok"] and result["retrieve_ok"] is not False else "FAIL"
        if result.get("error"):
            mark = "ERROR"
        print(f"         → {mark}", flush=True)
        results.append(result)
    return results


def write_results(results: list[dict], summary: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }
    RESULTS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main():
    args = parse_args()
    if args.self_test:
        self_test()
        return

    cases = select_cases(args)
    if not cases:
        raise SystemExit("No cases selected.")

    print(f"Running {len(cases)} case(s). This calls Gemini for each one.")
    results = asyncio.run(run_eval(cases))
    summary = summarize(results)
    print(format_report(results, summary))
    write_results(results, summary)
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
