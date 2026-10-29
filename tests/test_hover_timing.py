"""Keep hover responsive while avoiding repeated stationary OCR work."""

import pytest

from hoverlate.live import should_scan_ocr, should_forward_frame


def test_first_scan_after_150_ms_dwell():
    now = 100.0
    assert not should_scan_ocr(100.149, now, float("-inf"), 150, False)
    assert should_scan_ocr(100.150, now, float("-inf"), 150, False)


def test_idle_without_word_is_throttled():
    # Old code could run Tesseract every 200ms indefinitely on blank areas.
    assert not should_scan_ocr(10.7, 9.0, 10.0, 150, False)
    assert should_scan_ocr(10.81, 9.0, 10.0, 150, False)


def test_known_word_gets_longer_refresh_interval():
    assert not should_scan_ocr(11.99, 9.0, 10.0, 150, True)
    assert should_scan_ocr(12.0, 9.0, 10.0, 150, True)


def test_cursor_movement_resets_scan_timestamp():
    # Movement should not inherit the cooldown from a different word.
    assert not should_scan_ocr(20.11, 20.0, float("-inf"), 150, True)
    assert should_scan_ocr(20.16, 20.0, float("-inf"), 150, True)


@pytest.mark.parametrize("dwell", [150, 250, 700])
def test_custom_dwell_is_honored(dwell):
    now = 25.0
    assert not should_scan_ocr(now + dwell / 1000 - 0.01, now, float("-inf"), dwell, False)
    assert should_scan_ocr(now + dwell / 1000 + 0.01, now, float("-inf"), dwell, False)



def test_capture_fps_gate_drops_excess_frames_before_conversion():
    assert should_forward_frame(100.0, float("-inf"), 12)
    assert not should_forward_frame(100.01, 100.0, 12)
    assert should_forward_frame(100.10, 100.0, 12)
    assert should_forward_frame(100.20, 100.10, 12)
