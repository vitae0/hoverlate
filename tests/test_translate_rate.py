"""No-network tests for cached, rate-limited live translations."""
import sys
from types import SimpleNamespace

import pytest

from hoverlate.translate import ThrottledTranslator, TranslationRateLimited


def fake_provider(monkeypatch, replies):
    calls = []

    class FakeGoogle:
        def __init__(self, source, target):
            assert (source, target) == ("de", "en")

        def translate(self, word):
            calls.append(word)
            value = replies.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

    monkeypatch.setitem(sys.modules, "deep_translator",
                        SimpleNamespace(GoogleTranslator=FakeGoogle))
    return calls


def test_cached_words_are_immediate_during_throttle(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("hoverlate.translate.time.monotonic", lambda: clock[0])
    calls = fake_provider(monkeypatch, ["hello", "world"])
    service = ThrottledTranslator(min_interval=3)
    assert service.try_translate("Hallo") == "hello"
    clock[0] = 100.2
    assert service.try_translate("Welt") is None
    assert service.try_translate("HALLO") == "hello"
    assert calls == ["Hallo"]
    clock[0] = 103.5
    assert service.try_translate("Welt") == "world"
    assert calls == ["Hallo", "Welt"]


def test_429_has_exponential_cooldown_without_repeat_calls(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("hoverlate.translate.time.monotonic", lambda: clock[0])
    calls = fake_provider(monkeypatch, [
        RuntimeError("Server Error: You made too many requests to the server"),
        RuntimeError("HTTP 429"),
        "hello",
    ])
    service = ThrottledTranslator(min_interval=3, base_backoff=60, max_backoff=600)
    with pytest.raises(TranslationRateLimited) as first:
        service.try_translate("Hallo")
    assert first.value.wait_seconds == 60
    clock[0] = 120.0
    assert service.try_translate("Hallo") is None
    assert len(calls) == 1
    clock[0] = 160.1
    with pytest.raises(TranslationRateLimited) as second:
        service.try_translate("Hallo")
    assert second.value.wait_seconds == 120
    clock[0] = 280.2
    assert service.try_translate("Hallo") == "hello"
    assert service.failures == 0
    assert len(calls) == 3


def test_network_error_defers_next_attempt(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("hoverlate.translate.time.monotonic", lambda: clock[0])
    calls = fake_provider(monkeypatch, [ConnectionError("offline"), "yes"])
    service = ThrottledTranslator(min_interval=3)
    with pytest.raises(ConnectionError):
        service.try_translate("ja")
    clock[0] = 20.0
    assert service.try_translate("ja") is None
    assert len(calls) == 1
    clock[0] = 26.0
    assert service.try_translate("ja") == "yes"


def test_reject_invalid_pacing():
    with pytest.raises(ValueError):
        ThrottledTranslator(min_interval=0)
