"""Lightweight image-first game-text OCR, without neural network dependencies.

OCR is performed on a tiny cursor-centred image region, not the entire
monitor. Adaptive mode retries a different threshold/segmentation only when
the quick pass cannot find a usable word.
"""
from __future__ import annotations

from hashlib import blake2b


def cursor_crop(image, cursor, radius_x: int = 190, radius_y: int = 70):
    x, y = map(int, cursor)
    left = max(0, x - radius_x)
    top = max(0, y - radius_y)
    right = min(image.width, x + radius_x)
    bottom = min(image.height, y + radius_y)
    if left >= right or top >= bottom:
        return None
    return image.crop((left, top, right, bottom)), (x - left, y - top)


def region_fingerprint(image, cursor) -> bytes | None:
    """Cheap signature for skipping repeated Tesseract calls on static pixels."""
    from PIL import Image
    cropped = cursor_crop(image, cursor)
    if cropped is None:
        return None
    region, _ = cropped
    pixels = region.convert("L").resize((96, 32), Image.Resampling.BILINEAR)
    return blake2b(pixels.tobytes(), digest_size=12).digest()


def prepare_image(region):
    """Boost antialiased/stylized game fonts; normalize light-on-dark overlays."""
    from PIL import Image, ImageFilter, ImageOps
    gray = ImageOps.autocontrast(region.convert("L"), cutoff=1)
    # Sample the border, not the word, to detect dark dialogue boxes.
    width, height = gray.size
    edge = [gray.getpixel((x, y)) for x, y in (
        (0, 0), (width // 2, 0), (width - 1, 0),
        (0, height - 1), (width // 2, height - 1),
        (width - 1, height - 1),
    )]
    if sum(edge) / len(edge) < 120:
        gray = ImageOps.invert(gray)
    # Smaller than the old 520x200 full crop. Avoid upscaling huge fonts.
    return gray.resize((width * 2, height * 2), Image.Resampling.BICUBIC).filter(
        ImageFilter.UnsharpMask(radius=1.1, percent=125, threshold=2)
    )


def recognize_image_at(image, cursor, lang="deu+eng", known_word=None,
                       mode="adaptive") -> str | None:
    """Return a word actually visible beneath the cursor.

    Fast path: one Tesseract pass.
    Adaptive fallback: binarize and use sparse-text mode for unusual game UI.
    A local headword validator can make OCR choose a valid German recognition
    instead of a visually similar nonsense string. Never uses cloud services.
    """
    if mode not in ("fast", "adaptive"):
        raise ValueError("OCR mode must be fast or adaptive")
    cropped = cursor_crop(image, cursor)
    if cropped is None:
        return None
    region, (cx, cy) = cropped
    enhanced = prepare_image(region)

    import pytesseract
    from .ocr import hovered_word
    from PIL import Image

    def scan(target, segmentation):
        data = pytesseract.image_to_data(
            target, lang=lang, config=f"--psm {segmentation}",
            output_type=pytesseract.Output.DICT, timeout=2.0,
        )
        return hovered_word(data, cx * 2, cy * 2, min_conf=18)

    first = scan(enhanced, 6)
    if first and (known_word is None or known_word(first)):
        return first
    if mode == "fast":
        return first

    # Two OCR passes maximum. The fallback is reserved for empty/invalid
    # recognitions, rather than doubling the cost of every normal hover.
    binary = enhanced.point(lambda pixel: 255 if pixel > 150 else 0)
    second = scan(binary, 11)
    if second and (known_word is None or known_word(second)):
        return second
    return first or second
