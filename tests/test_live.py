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
        "left": [345, 940],
        "top": [125, 125],
        "width": [90, 100],
        "height": [30, 30],
    }
    # With the smaller crop (radius 190x70), the origin is (210, 130),
    # so the cursor in the 2x image is (380, 140).
    with patch("pytesseract.image_to_data", return_value=data):
        assert recognize_crop(image, (400, 200), "deu") == "gehen"


def test_cursor_beyond_image_gives_no_word():
    image = Image.new("RGB", (100, 80), "white")
    assert recognize_crop(image, (1000, 1000), "deu") is None

def test_gstreamer_cursor_roi_read_with_mocked_gi(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    from hoverlate.live import get_cursor_metadata

    gi = ModuleType("gi")
    repository = ModuleType("gi.repository")
    roi = SimpleNamespace(roi_type=2, x=143, y=87)
    repository.GstVideo = SimpleNamespace(
        buffer_get_video_region_of_interest_meta_id=lambda buf, index: roi
    )
    repository.GLib = SimpleNamespace(quark_to_string=lambda quark: "cursor")
    gi.repository = repository
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)
    assert get_cursor_metadata(object()) == (143, 87)

    repository.GLib.quark_to_string = lambda quark: "not-a-cursor"
    assert get_cursor_metadata(object()) is None
    repository.GstVideo.buffer_get_video_region_of_interest_meta_id = (
        lambda buf, index: None
    )
    assert get_cursor_metadata(object()) is None
