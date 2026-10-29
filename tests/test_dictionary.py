"""FreeDict dictionary format and offline-only selection tests (no network)."""
import gzip

import pytest

from hoverlate.dictionary import (
    DIGITS,
    DictionaryUnavailable,
    FreeDictTranslator,
    decode_dict_offset,
    make_translator,
    normalize,
    summarize_definition,
    compact_gloss,
)


def _encoded(number: int) -> str:
    if number == 0:
        return "A"
    digits = []
    while number:
        digits.append(DIGITS[number % 64])
        number //= 64
    return "".join(reversed(digits))


def _fixture(tmp_path):
    data = b""
    records = []
    for headword, definition in [
        ("gehen", "gehen /ˈɡeːən/ v.\ngo; walk"),
        ("Äpfel", "Äpfel [ˈɛpfəl] n.\napples"),
        ("verlassen", "verlassen [fɛɐˈlasən] v.\nto leave; abandon"),
        ("gehen", "gehen\n[ˈɡeːən]\nv.\nto move"),
        ("spielen", "spielen /ˈʃpiːlən/ v.\nto play; perform"),
        ("machen", "machen [ˈmaxən] v.\nmake; do"),
        ("sein", "sein [zaɪn] v.\nbe; exist"),
        ("aufmachen", "aufmachen [ˈaʊfmaxən] v.\nopen; unlock"),
    ]:
        entry = definition.encode("utf-8")
        records.append((headword, len(data), len(entry)))
        data += entry
    data_path = tmp_path / "freedict-deu-eng.dict.dz"
    index_path = tmp_path / "freedict-deu-eng.index"
    with gzip.open(data_path, "wb") as stream:
        stream.write(data)
    index_path.write_text(
        "".join(f"{word}\t{_encoded(offset)}\t{_encoded(size)}\n"
                for word, offset, size in records),
        encoding="utf-8",
    )
    return index_path, data_path


@pytest.mark.parametrize("value", [0, 1, 63, 64, 4096, 1234567])
def test_dict_numerical_base64(value):
    assert decode_dict_offset(_encoded(value)) == value


def test_invalid_base64():
    with pytest.raises(ValueError):
        decode_dict_offset("")


def test_lookup_unicode_casefold_and_multiple_definitions(tmp_path):
    idx, data = _fixture(tmp_path)
    translator = FreeDictTranslator(index_path=idx, data_path=data)
    assert translator.entry_count == 7
    assert translator.try_translate("Gehen") == "go"
    assert translator.try_translate("äPFEL") == "apples"
    assert translator.try_translate("verlassen") == "to leave"
    assert translator.try_translate("niemals") == ""
    assert translator.has_word("ging")
    assert not translator.has_word("niemals")
    assert translator.try_translate("ging") == "go"
    assert translator.try_translate("gespielt") == "to play"
    assert translator.try_translate("spielte") == "to play"
    assert translator.try_translate("machst") == "make"
    assert translator.try_translate("aufgemacht") == "open"
    assert translator.try_translate("bin") == "be"


def test_missing_dictionary_raises_actionable_error(tmp_path):
    with pytest.raises(DictionaryUnavailable, match="sudo apt install"):
        FreeDictTranslator(index_path=tmp_path / "missing.index",
                           data_path=tmp_path / "missing.dict.dz")


def test_default_mode_is_offline_without_provider_fallback(monkeypatch):
    def missing(*args, **kwargs):
        raise DictionaryUnavailable("not installed")

    monkeypatch.setattr("hoverlate.dictionary.FreeDictTranslator", missing)
    with pytest.raises(DictionaryUnavailable, match="not installed"):
        make_translator("de", "en")
    with pytest.raises(DictionaryUnavailable):
        make_translator("de", "en", "auto")


def test_summarize_definition_removes_tags():
    assert summarize_definition(b"<b>go</b>\nwalk") == "go · walk"


def test_only_german_english_supported(tmp_path):
    idx, data = _fixture(tmp_path)
    with pytest.raises(DictionaryUnavailable, match="de -> en"):
        FreeDictTranslator("fr", "en", index_path=idx, data_path=data)


@pytest.mark.parametrize(
    ("definition", "headword", "expected"),
    [
        ("gehen · [v] · go; walk · move", "gehen", "go"),
        ("verlassen · verb · to leave; abandon", "verlassen", "to leave"),
        ("walking; wandering", "", "walking"),
        ("[noun] · cat; feline", "", "cat"),
        ("1. to be / exist", "", "to be"),
        ("A very long explanatory phrase with several more words", "",
         "A very long explanatory"),
        ("", "", ""),
    ],
)
def test_compact_gloss_selects_first_short_meaning(definition, headword, expected):
    assert compact_gloss(definition, headword) == expected


@pytest.mark.parametrize(
    ("raw", "word", "gloss"),
    [
        ("gehen /ˈɡeːən/ v.\ngo; walk", "gehen", "go"),
        ("verlassen\n[fɛɐˈlasən]\nverb\nto leave; abandon", "verlassen", "to leave"),
        ("spielen [ˈʃpiːlən] v. to play; perform", "spielen", "to play"),
        ("gehen · [v] · go; walk · move", "gehen", "go"),
        ("gehen [ˈɡeːən]\nv.", "gehen", ""),
        ("<p>gehen /ˈɡeːən/</p><br><p>go; walk</p>", "gehen", "go"),
    ],
)
def test_realistic_freedict_headwords_and_ipa_are_never_used_as_meanings(
    raw, word, gloss
):
    assert compact_gloss(raw, word) == gloss
