"""`kk agent eval`: tool choice, grounding, citations and latency on a fixed question set."""

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import Engine

from klimakompas.agent.runner import AgentResult, LlmClient, LlmUnavailableError, run_agent
from klimakompas.core.config import ROOT

QUESTIONS = Path(__file__).parent / "questions.jsonl"
RESULTS_PATH = ROOT / "docs" / "agent-rezultati.json"


def load_questions() -> list[dict[str, Any]]:
    with QUESTIONS.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def score_answer(question: dict[str, Any], result: AgentResult) -> dict[str, Any]:
    expected = set(question["tools"])
    used = set(result.tools_used)
    tool_ok = not used if not expected else bool(used & expected)
    forbidden = [word for word in question.get("forbidden", []) if word in result.text]
    return {
        "id": question["id"],
        "kind": question["kind"],
        "question": question["question"],
        "tool_ok": tool_ok,
        "tools_used": result.tools_used,
        "grounded": result.grounded and not forbidden,
        "numbers_total": result.numbers_total,
        "numbers_ungrounded": result.numbers_ungrounded,
        "cited": "[" in result.text and bool(result.citations),
        "answer": result.text,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [row for row in rows if "error" not in row]
    latencies = np.array([row["latency_s"] for row in answered]) if answered else np.array([0.0])
    with_data = [row for row in answered if row["tools_used"]]
    numbers = sum(row["numbers_total"] for row in answered)
    ungrounded = sum(row["numbers_ungrounded"] for row in answered)
    return {
        "questions": len(rows),
        "answered": len(answered),
        "tool_choice_accuracy": _share(row["tool_ok"] for row in answered),
        "grounded_answers": _share(row["grounded"] for row in answered),
        "numbers_total": numbers,
        "numbers_grounded_share": round(1 - ungrounded / numbers, 3) if numbers else None,
        "answers_with_citations": _share(row["cited"] for row in with_data),
        "latency_p50_s": round(float(np.percentile(latencies, 50)), 1),
        "latency_p95_s": round(float(np.percentile(latencies, 95)), 1),
    }


def _share(values: Any) -> float | None:
    items = [bool(value) for value in values]
    return round(sum(items) / len(items), 3) if items else None


def run_eval(engine: Engine, llm: LlmClient, model: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for question in load_questions():
        started = time.monotonic()
        try:
            with engine.connect() as conn:
                events = list(run_agent(conn, llm, question["question"]))
            row = score_answer(question, events[-1]["result"])
            row["latency_s"] = round(time.monotonic() - started, 1)
        except LlmUnavailableError as error:
            row = {"id": question["id"], "kind": question["kind"], "error": str(error)}
        rows.append(row)
    result = {"model": model, "summary": summarize(rows), "rows": rows}
    RESULTS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
