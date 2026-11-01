"""Grounding check (SPEC §10.4): every number in an answer must come from a tool result."""

import json
import re
from dataclasses import dataclass
from typing import Any

# 3.871.833 or 15,8 or 44. Citation markers such as [1] are removed before matching.
NUMBER = re.compile(r"(?<![\w.,])\d{1,3}(?:\.\d{3})+(?:,\d+)?(?!\d)|(?<![\w.,])\d+(?:,\d+)?(?!\d)")
CITATION = re.compile(r"\[\d+\]")
# The emergency number and the fixed names of return periods are not claims about the data.
ALWAYS_ALLOWED = {112.0, 193.0, 65.0, 15.0, 2021.0, 2023.0}
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZČĆĐŠŽ\[])")
NOTE = "Dio odgovora uklonjen je jer ga nije bilo moguće potvrditi podacima iz izvora."


def parse_hr_number(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def numbers_in_answer(text: str) -> list[tuple[str, float]]:
    cleaned = CITATION.sub(" ", text)
    return [(match, parse_hr_number(match)) for match in NUMBER.findall(cleaned)]


def _collect(value: Any, found: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        found.add(float(value))
    elif isinstance(value, str):
        for match in re.findall(r"\d+(?:[.,]\d+)?", value):
            found.add(float(match.replace(",", ".")))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, found)
    elif isinstance(value, list | tuple):
        for item in value:
            _collect(item, found)


def tool_numbers(outputs: list[Any]) -> set[float]:
    found: set[float] = set()
    for output in outputs:
        _collect(json.loads(json.dumps(output, default=str)), found)
    return found


def _decimals(text: str) -> int:
    return len(text.split(",")[1]) if "," in text else 0


def is_grounded(text: str, value: float, known: set[float], question_numbers: set[float]) -> bool:
    """Allows rounding to the shown precision, and shares written as percentages."""
    if value in ALWAYS_ALLOWED or value in question_numbers:
        return True
    tolerance = 0.5 * 10 ** -_decimals(text) + 1e-9
    for number in known:
        if abs(number - value) <= tolerance:
            return True
        if 0 <= number <= 1 and abs(number * 100 - value) <= tolerance:
            return True
    return False


@dataclass(frozen=True)
class GroundingResult:
    ungrounded: list[str]
    total: int

    @property
    def ok(self) -> bool:
        return not self.ungrounded


def check_answer(answer: str, outputs: list[Any], question: str) -> GroundingResult:
    known = tool_numbers(outputs)
    asked = {value for _, value in numbers_in_answer(question)}
    found = numbers_in_answer(answer)
    missing = [text for text, value in found if not is_grounded(text, value, known, asked)]
    return GroundingResult(ungrounded=missing, total=len(found))


def remove_ungrounded(answer: str, outputs: list[Any], question: str) -> str:
    """Drop the sentences with unsupported numbers and say that this happened."""
    kept = [
        sentence
        for sentence in SENTENCE.split(answer)
        if check_answer(sentence, outputs, question).ok
    ]
    return " ".join([*kept, NOTE]).strip()
