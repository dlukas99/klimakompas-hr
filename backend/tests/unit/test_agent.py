from typing import Any

import pytest

from klimakompas.agent import runner
from klimakompas.agent.eval.runner import load_questions, score_answer, summarize
from klimakompas.agent.grounding import (
    NOTE,
    check_answer,
    numbers_in_answer,
    parse_hr_number,
    remove_ungrounded,
)
from klimakompas.agent.runner import AgentResult, run_agent
from klimakompas.api.app import RateLimiter


@pytest.mark.parametrize(
    ("text", "value"), [("3.871.833", 3871833), ("15,8", 15.8), ("44", 44), ("1.234,5", 1234.5)]
)
def test_parses_hr_numbers(text: str, value: float) -> None:
    assert parse_hr_number(text) == value


def test_finds_numbers_and_ignores_citations() -> None:
    found = numbers_in_answer("Osijek ima 96.313 stanovnika [1] i 15,8 µg/m³ [2].")
    assert [value for _, value in found] == [96313, 15.8]


def test_number_from_a_tool_is_grounded_with_rounding() -> None:
    assert check_answer("Prosjek je 15,8 µg/m³.", [{"pm25": 15.84}], "pitanje").ok
    assert check_answer("Ima 16 dana.", [{"days": 15.84}], "pitanje").ok


def test_invented_number_is_not_grounded() -> None:
    result = check_answer("Prosjek je 22,4 µg/m³.", [{"pm25": 15.84}], "pitanje")
    assert result.ungrounded == ["22,4"]


def test_rounding_does_not_stretch_beyond_shown_precision() -> None:
    assert not check_answer("Prosjek je 15,9.", [{"pm25": 15.84}], "pitanje").ok


def test_share_may_be_written_as_a_percentage() -> None:
    assert check_answer("Udio je 22 %.", [{"share": 0.217}], "pitanje").ok


def test_numbers_from_the_question_and_the_emergency_number_are_allowed() -> None:
    assert check_answer("U 2030. nazovite 112.", [], "Što će biti 2030.?").ok


def test_dates_inside_tool_strings_count() -> None:
    assert check_answer("Vrijedi do 23.", [{"expires": "2026-11-01T23:59:59"}], "pitanje").ok


def test_removes_only_sentences_with_invented_numbers() -> None:
    answer = "Prosjek je 15,8 µg/m³. Procjena je 99 žrtava. Provjerite izvore."
    result = remove_ungrounded(answer, [{"pm25": 15.8}], "pitanje")
    assert "15,8" in result
    assert "99" not in result
    assert result.endswith(NOTE)


class FakeLlm:
    """Replays prepared assistant messages."""

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.requests: list[list[dict[str, Any]]] = []

    def chat(self, messages: list[dict[str, Any]], use_tools: bool) -> dict[str, Any]:
        self.requests.append(list(messages))
        return self.messages.pop(0)


def tool_call(name: str, arguments: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [{"id": "1", "function": {"name": name, "arguments": arguments}}],
    }


SOURCE = {"id": "dzs", "title": "Popis", "publisher": "DZS", "url": None, "last_modified": None}


@pytest.fixture
def fake_tool(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    def run(_: object, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, arguments))
        return {"data": {"pop": 96313, "name": "Osijek"}, "sources": [SOURCE], "as_of": "now"}

    monkeypatch.setattr(runner, "run_tool", run)
    return calls


def final(llm: FakeLlm, question: str = "Koliko?") -> AgentResult:
    events = list(run_agent(None, llm, question))  # type: ignore[arg-type]
    result: AgentResult = events[-1]["result"]
    return result


def test_answer_uses_tool_and_cites_it(fake_tool: list[Any]) -> None:
    llm = FakeLlm(
        [
            tool_call("get_jls_profile", '{"jls": "Osijek"}'),
            {"content": "Ima 96.313 stanovnika [1]."},
        ]
    )
    result = final(llm)
    assert fake_tool == [("get_jls_profile", {"jls": "Osijek"})]
    assert result.grounded
    assert result.citations[0]["n"] == 1
    assert result.citations[0]["id"] == "dzs"
    assert result.tools_used == ["get_jls_profile"]


def test_invented_number_gets_one_retry(fake_tool: list[Any]) -> None:
    llm = FakeLlm(
        [
            tool_call("get_jls_profile", "{}"),
            {"content": "Ima 50.000 stanovnika."},
            {"content": "Ima 96.313 stanovnika [1]."},
        ]
    )
    result = final(llm)
    assert result.grounded
    assert "96.313" in result.text
    assert "50.000" in llm.requests[-1][-1]["content"]


def test_still_invented_after_retry_is_removed(fake_tool: list[Any]) -> None:
    llm = FakeLlm(
        [
            tool_call("get_jls_profile", "{}"),
            {"content": "Ima 50.000 stanovnika."},
            {"content": "Ima 60.000 stanovnika."},
        ]
    )
    result = final(llm)
    assert not result.grounded
    assert "60.000" not in result.text
    assert NOTE in result.text


def test_citation_without_a_source_is_removed(fake_tool: list[Any]) -> None:
    result = final(FakeLlm([{"content": "Nemam taj podatak [7]."}]))
    assert result.text == "Nemam taj podatak ."


def test_answer_without_tools_for_a_refusal() -> None:
    result = final(FakeLlm([{"content": "Mogu pomoći samo oko klimatskih rizika."}]))
    assert result.grounded
    assert result.tools_used == []


def test_model_thinking_is_hidden() -> None:
    result = final(FakeLlm([{"content": "<think>razmišljam 42</think>Pozdrav."}]))
    assert result.text == "Pozdrav."


def test_tool_call_written_as_json_text_still_works(fake_tool: list[Any]) -> None:
    llm = FakeLlm(
        [
            {"content": '{"tool": "get_jls_profile", "arguments": {"jls": "Osijek"}}'},
            {"content": "Ima 96.313 stanovnika [1]."},
        ]
    )
    assert final(llm).tools_used == ["get_jls_profile"]


def test_long_input_is_cut(fake_tool: list[Any]) -> None:
    llm = FakeLlm([{"content": "U redu."}])
    final(llm, "x" * 5000)
    assert len(llm.requests[0][1]["content"]) == 1000


def test_loop_stops_after_the_step_limit(fake_tool: list[Any]) -> None:
    llm = FakeLlm([tool_call("geocode", "{}") for _ in range(4)] + [{"content": "Gotovo."}])
    result = final(llm)
    assert len(result.tools_used) == 4
    assert result.text == "Gotovo."


def test_rate_limiter_blocks_after_the_limit_and_resets_each_minute() -> None:
    limiter = RateLimiter(2)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)
    assert limiter.allow("a", now=61)


def test_eval_set_is_large_enough_and_covers_every_kind() -> None:
    questions = load_questions()
    assert len(questions) >= 30
    kinds = {question["kind"] for question in questions}
    assert {"rank", "jls", "card", "warnings", "air", "data", "out_of_scope", "trap"} <= kinds


def test_eval_scores_tool_choice_and_forbidden_words() -> None:
    answer = AgentResult("Rizik je 99 % [1].", [{"n": 1}], [], True, ["geocode"], 1, 0)
    row = score_answer(
        {"id": 1, "kind": "trap", "question": "?", "tools": ["geocode"], "forbidden": ["99"]},
        answer,
    )
    assert row["tool_ok"] is True
    assert row["grounded"] is False
    refused = score_answer(
        {"id": 2, "kind": "out_of_scope", "question": "?", "tools": []},
        AgentResult("Mogu samo o klimi.", [], [], True, []),
    )
    assert refused["tool_ok"] is True


def test_eval_summary_shares() -> None:
    rows = [
        {
            "tool_ok": True,
            "grounded": True,
            "cited": True,
            "tools_used": ["a"],
            "numbers_total": 4,
            "numbers_ungrounded": 1,
            "latency_s": 2.0,
        },
        {
            "tool_ok": False,
            "grounded": True,
            "cited": False,
            "tools_used": [],
            "numbers_total": 0,
            "numbers_ungrounded": 0,
            "latency_s": 4.0,
        },
        {"id": 3, "error": "x"},
    ]
    summary = summarize(rows)
    assert summary["answered"] == 2
    assert summary["tool_choice_accuracy"] == 0.5
    assert summary["numbers_grounded_share"] == 0.75
    assert summary["answers_with_citations"] == 1.0
