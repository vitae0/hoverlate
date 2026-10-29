"""Offline translator tests using an in-memory fake model; no network required."""
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from hoverlate.offline import OfflineTranslator, make_translator
from hoverlate.translate import ThrottledTranslator


def fake_argos(monkeypatch):
    provider = ModuleType("argostranslate")
    translate = ModuleType("argostranslate.translate")

    class Model:
        def translate(self, word):
            return {"Hallo": "Hello", "Welt": "World"}[word]

    class Language:
        def __init__(self, code):
            self.code = code

        def get_translation(self, target):
            return Model() if (self.code, target.code) == ("de", "en") else None

    translate.get_installed_languages = lambda: [Language("de"), Language("en")]
    provider.translate = translate
    monkeypatch.setitem(sys.modules, "argostranslate", provider)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", translate)


def test_offline_translates_and_uses_memory_cache(monkeypatch):
    fake_argos(monkeypatch)
    translator = OfflineTranslator("de", "en")
    assert translator.try_translate("Hallo") == "Hello"
    assert translator.try_translate("HALLO") == "Hello"
    assert translator.try_translate("Welt") == "World"


def test_auto_prefers_installed_offline_model(monkeypatch):
    fake_argos(monkeypatch)
    selected = make_translator("de", "en", "auto")
    assert isinstance(selected, OfflineTranslator)


def test_auto_falls_back_to_paced_google_when_no_model():
    with patch("hoverlate.offline.OfflineTranslator",
               side_effect=RuntimeError("missing model")):
        result = make_translator("de", "en", "auto")
    assert isinstance(result, ThrottledTranslator)


def test_explicit_offline_does_not_silently_use_online_service():
    with patch("hoverlate.offline.OfflineTranslator",
               side_effect=RuntimeError("missing model")):
        with pytest.raises(RuntimeError, match="missing model"):
            make_translator("de", "en", "offline")
