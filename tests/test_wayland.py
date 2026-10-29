import base64
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from hoverlate.wayland import recognize_png


def test_invalid_box_does_not_decode():
    assert recognize_png("not-base64", 0, 0, 0, 0, 0, 1) is None


def test_hidpi_cursor_coordinates_match_scaled_image():
    image = Image.new("RGB", (200, 100), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    data = {
        "text": ["hallo"], "conf": [97],
        "left": [195], "top": [95], "width": [20], "height": [20],
    }
    with patch("pytesseract.image_to_data", return_value=data):
        assert recognize_png(payload, 60, 45, 10, 20, 100, 50) == "hallo"
