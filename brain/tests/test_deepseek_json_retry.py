"""The batch provider re-asks when a 200 comes back with an empty/non-JSON body (no network).

The openai SDK retries HTTP failures; it does not retry a successful response whose body isn't
JSON, and the batch model emits one occasionally. That used to abort a whole round mid-ingest.
These tests drive a fake client so nothing here touches the network.
"""

from __future__ import annotations

import pytest

from warp_compass_brain.config import Settings
from warp_compass_brain.llm.base import LLMError
from warp_compass_brain.llm.deepseek import DeepSeekProvider


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class FakeClient:
    """Returns each queued body in turn; records how many calls it saw."""

    def __init__(self, bodies: list[str]) -> None:
        self._bodies = list(bodies)
        self.calls = 0
        self.chat = self  # so `client.chat.completions.create` resolves back here
        self.completions = self

    def create(self, **kwargs) -> _Resp:
        self.calls += 1
        return _Resp(self._bodies.pop(0) if self._bodies else "")


def _provider(bodies: list[str], *, attempts: int = 3) -> tuple[DeepSeekProvider, FakeClient]:
    settings = Settings(
        deepseek_api_key="test-key",
        llm_json_attempts=attempts,
        llm_json_base_delay=0.0,  # keep the suite fast — no real backoff
    )
    p = DeepSeekProvider(settings)
    client = FakeClient(bodies)
    p._client = client  # noqa: SLF001 — injecting the transport is the point of the test
    return p, client


def test_empty_body_then_success_returns_the_parsed_object():
    p, client = _provider(["", '{"nodes": [], "relations": []}'])
    assert p.complete_json("sys", "user") == {"nodes": [], "relations": []}
    assert client.calls == 2  # first body was empty, so it re-asked


def test_prose_body_then_success():
    p, client = _provider(["I'm sorry, I can't help with that.", '{"ok": true}'])
    assert p.complete_json("sys", "user") == {"ok": True}
    assert client.calls == 2


def test_gives_up_after_the_configured_attempts_and_raises_the_parse_error():
    p, client = _provider(["", "", ""], attempts=3)
    with pytest.raises(LLMError, match="did not return valid JSON"):
        p.complete_json("sys", "user")
    assert client.calls == 3  # exhausted, not infinite


def test_attempts_of_one_disables_the_retry():
    p, client = _provider(["", '{"ok": true}'], attempts=1)
    with pytest.raises(LLMError):
        p.complete_json("sys", "user")
    assert client.calls == 1


def test_a_good_first_response_costs_exactly_one_call():
    p, client = _provider(['{"ok": true}'])
    assert p.complete_json("sys", "user") == {"ok": True}
    assert client.calls == 1


def test_a_json_fence_is_still_tolerated_without_a_retry():
    p, client = _provider(['```json\n{"ok": true}\n```'])
    assert p.complete_json("sys", "user") == {"ok": True}
    assert client.calls == 1


def test_a_json_array_is_a_hard_error_worth_retrying():
    """Valid JSON but the wrong shape — the caller needs an object, so re-ask."""
    p, client = _provider(["[1, 2, 3]", '{"ok": true}'])
    assert p.complete_json("sys", "user") == {"ok": True}
    assert client.calls == 2
