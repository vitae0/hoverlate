"""German-first OCR, mapped back onto physical screen coordinates."""

import re

from .geometry import region_around

_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)


def clean_word(text: str) -> str | None:
    """Extract one alphabetic word without surrounding punctuation."""
    match = _WORD.search(text.strip())
    return match.group(0) if match else None


def hovered_word(data: dict, px: int, py: int, *, min_conf: float = 20) -> str | None:
    """Return an OCR word whose bounding box includes the cursor, if any.

    Both OCR coordinates and cursor coordinates are in the scaled image space.
    Prefer the smallest matching box over unrelated large text regions.
    """
    matches = []
    count = len(data.get("text", []))
    for i in range(count):
        try:
            conf = float(data["conf"][i])
            left = int(data["left"][i])
            top = int(data["top"][i])
            width = int(data["width"][i])
            height = int(data["height"][i])
            text = clean_word(str(data["text"][i]))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if not text or conf < min_conf or width <= 0 or height <= 0:
            continue
        if left - 5 <= px <= left + width + 5 and top - 5 <= py <= top + height + 5:
            matches.append((width * height, -conf, text))
    return min(matches)[2] if matches else None


def recognize_at(x: int, y: int, *, ocr_lang: str = "deu+eng") -> str | None:
    """Capture only a small region; do not write screenshots to disk."""
    import mss
    import pytesseract
    from PIL import Image, ImageOps

    with mss.MSS() as screen:
        box = region_around(x, y, screen.monitors[0])
        screenshot = screen.grab(box)
    image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    image = ImageOps.autocontrast(ImageOps.grayscale(image))
    scale = 2
    image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    data = pytesseract.image_to_data(
        image, lang=ocr_lang, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    return hovered_word(data, (x - box["left"]) * scale, (y - box["top"]) * scale)
