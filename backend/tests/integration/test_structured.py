from typing import Any

import pytest
from sqlalchemy import Connection, text
from test_foundation import seed

from klimakompas.agent import structured
from klimakompas.agent.runner import AgentResult
from klimakompas.agent.structured import (
    named_in_question,
    parse_intent,
    resolve_place,
    run_structured,
)


class OneReply:
    def __init__(self, content: str) -> None:
        self.content = content

    def chat(self, messages: list[dict[str, Any]], use_tools: bool) -> dict[str, Any]:
        assert use_tools is False
        return {"content": self.content}


def ask(conn: Connection, reply: str, question: str = "pitanje") -> AgentResult:
    result: AgentResult = list(run_structured(conn, OneReply(reply), question))[-1]["result"]
    return result


@pytest.fixture
def seeded(conn: Connection) -> Connection:
    seed(conn)
    return conn


def test_parses_json_inside_other_text() -> None:
    intent = parse_intent('Evo: {"intent": "place", "place": "Osijek"} gotovo')
    assert intent is not None
    assert intent.place == "Osijek"


def test_invalid_intent_is_rejected() -> None:
    assert parse_intent('{"intent": "hack"}') is None
    assert parse_intent("nije json") is None


def test_unknown_place_is_never_replaced_by_a_similar_one(seeded: Connection) -> None:
    assert resolve_place(seeded, "Xqzvillegrad") is None
    answer = ask(seeded, '{"intent": "place", "place": "Xqzvillegrad"}', "Rizik u Xqzvillegrad?")
    assert "Nisam pronašao" in answer.text
    assert answer.citations == []


def test_place_name_without_diacritics_matches(seeded: Connection) -> None:
    place = resolve_place(seeded, "sodolovci")
    assert place is not None
    assert place["label"] == "Šodolovci"


def test_out_of_scope_and_advice_use_fixed_text(seeded: Connection) -> None:
    assert ask(seeded, '{"intent": "out_of_scope"}').text == structured.OUT_OF_SCOPE
    assert ask(seeded, '{"intent": "advice"}', "Trebam li lijek?").text == structured.ADVICE
    assert ask(seeded, '{"intent": "no_data"}').text == structured.NO_DATA


def test_unreadable_model_reply_falls_back_to_the_rules(seeded: Connection) -> None:
    # The model's own text is never shown; the rules read the original question instead.
    answer = ask(seeded, "Rizik je 99 %.", "Napiši pjesmu.")
    assert answer.text == structured.OUT_OF_SCOPE


def test_works_without_any_model(seeded: Connection) -> None:
    events = list(run_structured(seeded, None, "Ima li danas upozorenja?"))
    assert events[-1]["result"].tools_used == ["get_active_warnings"]


def test_warnings_answer_is_cited(seeded: Connection) -> None:
    answer = ask(seeded, '{"intent": "warnings"}')
    assert "nema aktivnih upozorenja" in answer.text
    assert answer.citations[0]["id"] == "dhmz_cap"
    assert answer.tools_used == ["get_active_warnings"]


def test_model_cannot_bring_in_a_place_the_user_did_not_name() -> None:
    assert not named_in_question("Zagrad", "Kakav je rizik u mjestu Xqzvillegrad?")
    assert named_in_question("Slavonski Brod", "Kakav je zrak u Slavonskom Brodu?")
    assert named_in_question("Zadar", "Koliko je vrućih dana u Zadru?")
    assert named_in_question("Požega", "Rizik u Pozegi?")
    assert named_in_question("Trg slobode 7", "Što je s adresom Trg slobode 7?")


def test_same_address_in_two_towns_asks_which_one(seeded: Connection) -> None:
    seeded.execute(
        text(
            "INSERT INTO ref.addresses (id, label, house_number, jls_code, search_text, geom) "
            "VALUES ('KB.9', 'Trg slobode 7 Nekamo', '7', '06149', "
            "ref.normalize_search('Trg slobode 7 Nekamo'), "
            "ST_SetSRID(ST_MakePoint(4800100, 2500100), 3035))"
        )
    )
    assert resolve_place(seeded, "Trg slobode 7") == {"ambiguous": ["Osijek", "Šodolovci"]}
    answer = ask(seeded, '{"intent": "place", "place": "Trg slobode 7"}', "Trg slobode 7?")
    assert "više mjesta" in answer.text


def test_bad_optional_field_does_not_lose_the_intent() -> None:
    intent = parse_intent('{"intent": "place", "place": "Knin", "hazard": "vrucina"}')
    assert intent is not None
    assert intent.place == "Knin"
    assert intent.hazard is None


def test_ranking_for_an_unrelated_question_becomes_a_refusal(seeded: Connection) -> None:
    answer = ask(seeded, '{"intent": "rank"}', "Napiši mi pjesmu o moru.")
    assert answer.text == structured.OUT_OF_SCOPE


def test_advice_only_for_real_advice_questions(seeded: Connection) -> None:
    assert ask(seeded, '{"intent": "advice"}', "Preporuči film.").text == structured.OUT_OF_SCOPE
    assert ask(seeded, '{"intent": "advice"}', "Trebam li lijek?").text == structured.ADVICE
