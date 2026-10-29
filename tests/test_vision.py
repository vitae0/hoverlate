"""Small-game-ROI OCR tests, with Tesseract mocked out (no GPU/network)."""
from unittest.mock import patch

from PIL import Image, ImageDraw

from hoverlate.vision import (
    cursor_crop, prepare_image, recognize_image_at, region_fingerprint,
)


def ocr_record(word: str):
    return {
        "text": [word],
        "conf": [96],
        "left": [345], "top": [125],
        "width": [90], "height": [30],
    }


def test_ocr_uses_small_region_near_cursor():
    image = Image.new("RGB", (1920, 1080), "white")
    region, point = cursor_crop(image, (400, 200))
    assert region.size == (380, 140)
    assert point == (190, 70)


def test_image_ocr_fast_path_one_tesseract_call():
    image = Image.new("RGB", (800, 400), "white")
    with patch("pytesseract.image_to_data", return_value=ocr_record("spielen")) as call:
        word = recognize_image_at(
            image, (400, 200), known_word=lambda w: w == "spielen"
        )
    assert word == "spielen"
    assert call.call_count == 1
    assert call.call_args.kwargs["timeout"] == 2.0


def test_game_font_fallback_only_if_first_ocr_is_invalid():
    image = Image.new("RGB", (800, 400), "white")
    with patch("pytesseract.image_to_data",
               side_effect=[ocr_record("spleln"), ocr_record("spielen")]) as call:
        word = recognize_image_at(
            image, (400, 200), known_word=lambda w: w == "spielen"
        )
    assert word == "spielen"
    assert call.call_count == 2
    assert "--psm 11" in call.call_args.kwargs["config"]


def test_fast_mode_never_runs_expensive_fallback():
    image = Image.new("RGB", (800, 400), "white")
    with patch("pytesseract.image_to_data", return_value=ocr_record("spleln")) as call:
        word = recognize_image_at(
            image, (400, 200), known_word=lambda _: False, mode="fast"
        )
    assert word == "spleln"
    assert call.call_count == 1


def test_static_image_signature_changes_when_text_changes():
    image = Image.new("RGB", (800, 400), "white")
    a = region_fingerprint(image, (400, 200))
    assert a == region_fingerprint(image.copy(), (400, 200))
    painter = ImageDraw.Draw(image)
    painter.rectangle((340, 190, 440, 210), fill="black")
    assert a != region_fingerprint(image, (400, 200))


def test_dark_dialogue_box_is_normalized_to_light_background():
    dark = Image.new("RGB", (380, 140), "#171717")
    image = prepare_image(dark)
    assert image.size == (760, 280)
    assert image.getpixel((4, 4)) > 220


def test_cropped_cursor_outside_shared_monitor():
    image = Image.new("RGB", (100, 90), "white")
    assert cursor_crop(image, (900, 900)) is None
    assert recognize_image_at(image, (900, 900)) is None
