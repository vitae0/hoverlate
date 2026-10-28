from hoverlate.geometry import region_around
from hoverlate.ocr import clean_word, hovered_word
from hoverlate.translate import WordTranslator


def test_region_inside_screen():
    box = region_around(100, 80, {"left": 0, "top": 0, "width": 1920, "height": 1080})
    assert box == {"left": 0, "top": 0, "width": 520, "height": 220}


def test_region_negative_origin_and_small_screen():
    box = region_around(-90, 10, {"left": -100, "top": -50, "width": 160, "height": 80})
    assert box == {"left": -100, "top": -50, "width": 160, "height": 80}


def test_region_rejects_zero():
    import pytest
    with pytest.raises(ValueError):
        region_around(0, 0, {"left": 0, "top": 0, "width": 0, "height": 100})


def test_word_cleanup():
    assert clean_word("(verlassen!)") == "verlassen"
    assert clean_word("Äpfel,") == "Äpfel"
    assert clean_word("123") is None
    assert clean_word("") is None


def test_hovered_word_selects_correct_bbox():
    data = {
        "text": ["gehen", "bleiben"],
        "conf": [91, 87],
        "left": [10, 110],
        "top": [20, 20],
        "width": [70, 75],
        "height": [25, 25],
    }
    assert hovered_word(data, 24, 30) == "gehen"
    assert hovered_word(data, 126, 30) == "bleiben"
    assert hovered_word(data, 90, 30) is None


def test_low_confidence_discarded():
    data = {"text": ["abc"], "conf": [5], "left": [0], "top": [0], "width": [10], "height": [10]}
    assert hovered_word(data, 4, 4) is None


def test_translation_lru_without_network():
    service = WordTranslator(cache_size=2)
    service._cache["hallo"] = "hello"
    service._cache["welt"] = "world"
    assert service.cached("HALLO") == "hello"
    assert list(service._cache) == ["welt", "hallo"]
