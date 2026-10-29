"""Unit tests for the live hover backend; no GNOME session required."""
from unittest.mock import patch

from PIL import Image

from hoverlate.live import recognize_crop, request_path


def test_request_path_uses_sender_and_token():
    assert request_path(":1.42", "hv_abc") == (
        "/org/freedesktop/portal/desktop/request/1_42/hv_abc"
    )


def test_crop_targets_actual_cursor():
    image = Image.new("RGB", (800, 400), "white")
    data = {
        "text": ["gehen", "bleiben"],
        "conf": [98, 95],
        "left": [520, 940],
        "top": [190, 190],
        "width": [90, 100],
        "height": [30, 30],
    }
    # With cursor (400, 200), crop begins at (140, 100), so text x 520
    # corresponds to absolute x=400; y 190 corresponds to absolute y=195.
    with patch("pytesseract.image_to_data", return_value=data):
        assert recognize_crop(image, (400, 200), "deu") == "gehen"


def test_cursor_beyond_image_gives_no_word():
    image = Image.new("RGB", (100, 80), "white")
    assert recognize_crop(image, (1000, 1000), "deu") is None
