"""The assistant loop (SPEC §10.1): tools, grounding check, citations. Nothing is stored."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from klimakompas.agent.grounding import check_answer, remove_ungrounded
from klimakompas.agent.tools import TOOL_SCHEMAS, run_tool, to_tool_message
from klimakompas.core.config import Settings

MAX_STEPS = 4
MAX_INPUT_CHARS = 1000
LLM_TIMEOUT_S = 90.0
MAX_ANSWER_TOKENS = 500
PROMPT = (Path(__file__).parent / "prompts" / "system_hr.md").read_text(encoding="utf-8")
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
CITATION = re.compile(r"\[(\d+)\]")
OUT_OF_SCOPE = (
    "Mogu pomoći samo oko klimatskih rizika, okoliša i otvorenih podataka za mjesta u Hrvatskoj. "
    "Za takvo pitanje nemam provjerene podatke."
)
MARKDOWN_EMPHASIS = re.compile(r"\*\*(.+?)\*\*")
RETRY = (
    "Ovi brojevi nisu u rezultatima alata: {numbers}. Napiši odgovor ponovno i koristi samo "
    "brojeve iz rezultata alata, uz citate [n]."
)


class LlmUnavailableError(Exception):
    pass


class LlmClient(Protocol):
    def chat(self, messages: list[dict[str, Any]], use_tools: bool) -> dict[str, Any]: ...


class OpenAiCompatibleClient:
    """Any /v1/chat/completions server: the code does not depend on one provider."""

    def __init__(self, settings: Settings) -> None:
        self.url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        self.model = settings.llm_model
        self.key = settings.llm_api_key.get_secret_value()

    def chat(self, messages: list[dict[str, Any]], use_tools: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": MAX_ANSWER_TOKENS,
        }
        if use_tools:
            payload["tools"] = TOOL_SCHEMAS
            payload["tool_choice"] = "auto"
        try:
            response = httpx.post(
                self.url,
                json=payload,
                headers={"Authorization": f"Bearer {self.key}"},
                timeout=LLM_TIMEOUT_S,
            )
            response.raise_for_status()
            message: dict[str, Any] = response.json()["choices"][0]["message"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
            raise LlmUnavailableError(type(error).__name__) from error
        return message


def llm_available(settings: Settings) -> bool:
    if not settings.llm_base_url:
        return False
    try:
        response = httpx.get(settings.llm_base_url.rstrip("/") + "/models", timeout=3.0)
    except httpx.HTTPError:
        return False
    return response.is_success


@dataclass
class AgentResult:
    text: str
    citations: list[dict[str, Any]]
    map_actions: list[dict[str, Any]]
    grounded: bool
    tools_used: list[str] = field(default_factory=list)
    numbers_total: int = 0
    numbers_ungrounded: int = 0


def _clean(content: str | None) -> str:
    return THINK.sub("", content or "").strip()


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_tool_call(content: str) -> dict[str, Any] | None:
    """Weaker models write the call as JSON text instead of using tool calling (SPEC §10.1)."""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("tool"), str):
        return {"name": parsed["tool"], "arguments": parsed.get("arguments") or {}}
    return None


def _map_actions(name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data")
    if name == "geocode" and isinstance(data, list) and data:
        first = data[0]
        return [{"type": "show", "lat": first["lat"], "lon": first["lon"], "label": first["label"]}]
    if name == "get_place_card" and isinstance(data, dict) and "mjesto" in data:
        return [{"type": "show", "lat": data["lat"], "lon": data["lon"], "label": data["mjesto"]}]
    if name == "get_jls_profile" and isinstance(data, dict) and "lat" in data:
        return [{"type": "show", "lat": data["lat"], "lon": data["lon"], "label": data["name"]}]
    return []


def _citations(text: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Numbered sources in tool order. Markers without a source are removed by the caller."""
    return [{"n": position, **source} for position, source in enumerate(sources, start=1)]


def _strip_unknown_citations(text: str, count: int) -> str:
    return CITATION.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= count else "", text)


def run_agent(conn: Connection, llm: LlmClient, question: str) -> Iterator[dict[str, Any]]:
    """Yields progress events and one final `answer` event."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": question[:MAX_INPUT_CHARS]},
    ]
    outputs: list[Any] = []
    sources: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    actions: list[dict[str, Any]] = []
    tools_used: list[str] = []
    answer = ""

    for _ in range(MAX_STEPS):
        message = llm.chat(messages, use_tools=True)
        calls = message.get("tool_calls") or []
        content = _clean(message.get("content"))
        if not calls and (fallback := _json_tool_call(content)):
            calls = [{"id": "fallback", "function": fallback}]
        if not calls:
            answer = content
            break
        messages.append(
            {"role": "assistant", "content": content, "tool_calls": message.get("tool_calls")}
            if message.get("tool_calls")
            else {"role": "assistant", "content": content}
        )
        for call in calls:
            name = call["function"]["name"]
            arguments = _parse_arguments(call["function"].get("arguments"))
            yield {"event": "tool", "name": name}
            result = run_tool(conn, name, arguments)
            tools_used.append(name)
            outputs.append(result.get("data"))
            actions.extend(_map_actions(name, result))
            numbered = []
            for source in result.get("sources", []):
                if source["id"] not in seen_sources:
                    seen_sources.add(source["id"])
                    sources.append(source)
                numbered.append(
                    next(i for i, s in enumerate(sources, 1) if s["id"] == source["id"])
                )
            payload = {**result, "cite_as": [f"[{n}]" for n in numbered]}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "name": name,
                    "content": to_tool_message(payload),
                }
            )
    else:
        message = llm.chat(messages, use_tools=False)
        answer = _clean(message.get("content"))

    question_text = question[:MAX_INPUT_CHARS]
    check = check_answer(answer, outputs, question_text)
    numbers_total = check.total
    numbers_ungrounded = len(check.ungrounded)
    if not check.ok:
        messages.append({"role": "assistant", "content": answer})
        messages.append(
            {"role": "user", "content": RETRY.format(numbers=", ".join(check.ungrounded))}
        )
        answer = _clean(llm.chat(messages, use_tools=False).get("content"))
        check = check_answer(answer, outputs, question_text)
        numbers_total = check.total
        numbers_ungrounded = len(check.ungrounded)
        if not check.ok:
            # With no tool result at all, nothing in the answer can be trusted.
            answer = (
                OUT_OF_SCOPE if not outputs else remove_ungrounded(answer, outputs, question_text)
            )

    answer = _strip_unknown_citations(MARKDOWN_EMPHASIS.sub(r"\1", answer), len(sources))
    yield {
        "event": "answer",
        "result": AgentResult(
            text=answer,
            citations=_citations(answer, sources),
            map_actions=actions[:1],
            grounded=check.ok,
            tools_used=tools_used,
            numbers_total=numbers_total,
            numbers_ungrounded=numbers_ungrounded,
        ),
    }
