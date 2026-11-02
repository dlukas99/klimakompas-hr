import pytest
from sqlalchemy import Connection
from test_foundation import seed

from klimakompas.agent import rules
from klimakompas.agent.rules import find_names, fold, parse_rules


@pytest.fixture
def seeded(conn: Connection) -> Connection:
    seed(conn)
    rules._NAMES.clear()
    return conn


def test_fold_removes_diacritics() -> None:
    assert fold("Šodolovci Đakovo") == "sodolovci dakovo"


def test_place_in_another_case_is_found(seeded: Connection) -> None:
    assert [name.label for name in find_names(seeded, "Kakav je rizik u Osijeku?")][0] == "Osijek"


def test_similar_but_different_word_is_not_a_place(seeded: Connection) -> None:
    assert find_names(seeded, "Kakav je rizik u mjestu Osijekgrad?") == []
    assert find_names(seeded, "Osipek je daleko") == []


def test_question_kinds(seeded: Connection) -> None:
    assert parse_rules(seeded, "Je li Osijek u zoni poplave?").hazard == "flood"
    assert parse_rules(seeded, "Koliko stanovnika ima Osijek?").intent == "jls"
    assert parse_rules(seeded, "Ima li danas upozorenja?").intent == "warnings"
    assert parse_rules(seeded, "Koje općine imaju najveći rizik od požara?").intent == "rank"
    assert parse_rules(seeded, "Trebam li uzeti lijek?").intent == "advice"
    assert parse_rules(seeded, "Koliko je ljudi poginulo u poplavi?").intent == "no_data"
    assert parse_rules(seeded, "Napiši mi pjesmu o moru.").intent == "out_of_scope"


def test_unknown_named_place_is_not_answered_for_all_of_croatia(seeded: Connection) -> None:
    intent = parse_rules(seeded, "Kakav je rizik u mjestu Qwertograd?")
    assert intent.intent == "place"
    assert structured_place_is_unknown(seeded, intent.place or "")


def structured_place_is_unknown(conn: Connection, name: str) -> bool:
    from klimakompas.agent.structured import resolve_place

    return resolve_place(conn, name) is None


def test_address_with_town_in_another_case(seeded: Connection) -> None:
    intent = parse_rules(seeded, "Kakvi su rizici na adresi Trg slobode 7 u Osijeku?")
    assert intent.intent == "place"
    assert intent.place == "Trg slobode 7 Osijek"
