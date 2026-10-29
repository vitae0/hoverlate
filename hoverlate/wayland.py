"""Experimental GNOME Wayland bridge: OCR and translate cursor screenshots."""
import argparse
import asyncio
import base64
from io import BytesIO
import math
import os
import shutil
import sys
import time

from .ocr import hovered_word
from .translate import WordTranslator

SERVICE = "org.hoverlate.Shell"
PATH = "/org/hoverlate/Shell"


def recognize_png(payload: str, x: int, y: int, left: int, top: int,
                  width: int, height: int, *, ocr_lang: str = "deu+eng") -> str | None:
    """OCR a cursor-centred PNG, allowing HiDPI capture dimensions."""
    from PIL import Image, ImageOps
    import pytesseract

    if width <= 0 or height <= 0:
        return None
    raw = base64.b64decode(payload, validate=True)
    if len(raw) > 6_000_000:
        raise ValueError("Captured image is too large")
    with Image.open(BytesIO(raw)) as original:
        original.load()
        image = ImageOps.autocontrast(ImageOps.grayscale(original))
    px = (x - left) * image.width / width
    py = (y - top) * image.height / height
    image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    data = pytesseract.image_to_data(
        image, lang=ocr_lang, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    return hovered_word(data, round(px * 2), round(py * 2))


async def run(source: str, target: str, ocr_lang: str, dwell_ms: int) -> None:
    from dbus_next.aio import MessageBus

    bus = await MessageBus().connect()
    try:
        intro = await bus.introspect(SERVICE, PATH)
        proxy = bus.get_proxy_object(SERVICE, PATH, intro)
        shell = proxy.get_interface(SERVICE)
    except Exception as exc:
        bus.disconnect()
        raise RuntimeError(
            "GNOME Shell bridge unavailable. Install and enable hoverlate@hoverlate.dev "
            "as described in README; you may need to log out and back in."
        ) from exc
    translator = WordTranslator(source, target)
    pos = None
    still_since = time.monotonic()
    last_capture = 0.0
    last_word = None
    visible = False
    print("Hoverlate Wayland started. Press Ctrl+C to exit.", flush=True)
    try:
        while True:
            x, y = await shell.call_get_pointer()
            now = time.monotonic()
            if pos is None or math.dist((x, y), pos) > 9:
                pos = (x, y)
                still_since = now
                last_word = None
                if visible:
                    await shell.call_hide_translation()
                    visible = False
            if now - still_since < dwell_ms / 1000 or now - last_capture < 1.1:
                await asyncio.sleep(0.12)
                continue
            last_capture = now
            try:
                frame = await shell.call_capture_hover()
                word = await asyncio.to_thread(
                    recognize_png, frame[6], *frame[:6], ocr_lang=ocr_lang
                )
            except Exception as exc:
                print("Hoverlate OCR: " + str(exc), file=sys.stderr)
                await asyncio.sleep(2)
                continue
            current = await shell.call_get_pointer()
            if math.dist((x, y), current) > 9:
                continue
            if not word:
                if visible:
                    await shell.call_hide_translation()
                    visible = False
                await asyncio.sleep(0.12)
                continue
            if word == last_word and visible:
                await asyncio.sleep(0.12)
                continue
            try:
                translated = await asyncio.to_thread(translator.translate, word)
            except Exception as exc:
                print("Hoverlate translation: " + str(exc), file=sys.stderr)
                await asyncio.sleep(4)
                continue
            current = await shell.call_get_pointer()
            if math.dist((x, y), current) > 9:
                continue
            await shell.call_show_translation(word, translated)
            visible = True
            last_word = word
            await asyncio.sleep(0.12)
    finally:
        try:
            await shell.call_hide_translation()
        except Exception:
            pass
        bus.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GNOME Wayland hover translator")
    parser.add_argument("--source", default="de")
    parser.add_argument("--target", default="en")
    parser.add_argument("--ocr-lang", default="deu+eng")
    parser.add_argument("--dwell-ms", type=int, default=400)
    args = parser.parse_args(argv)
    if args.dwell_ms < 100:
        parser.error("--dwell-ms must be at least 100")
    if sys.platform != "linux" or os.environ.get("XDG_SESSION_TYPE", "").lower() != "wayland":
        parser.error("A Wayland login is required")
    if "GNOME" not in os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
        parser.error("GNOME Shell required (KDE, Sway and Hyprland unsupported)")
    if not shutil.which("tesseract"):
        parser.error("Install tesseract-ocr and tesseract-ocr-deu")
    try:
        asyncio.run(run(args.source, args.target, args.ocr_lang, args.dwell_ms))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print("Hoverlate Wayland: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
