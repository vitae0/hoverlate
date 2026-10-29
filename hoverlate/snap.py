"""One-shot Wayland OCR translator via the standard Screenshot desktop portal.

No GNOME Shell extension, permanent background process, or global pointer access.
"""
import argparse
import asyncio
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
from urllib.parse import unquote, urlparse

from .translate import WordTranslator


PORTAL_NAME = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"


class CaptureCancelled(Exception):
    """The user dismissed the screenshot picker."""


def request_path(unique_name: str, token: str) -> str:
    """Construct the portal request path, including the D-Bus sender ID."""
    sender = unique_name.lstrip(":").replace(".", "_")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", sender) or not re.fullmatch(r"[a-zA-Z0-9_]+", token):
        raise ValueError("Invalid D-Bus unique name or request token")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


def screenshot_file(uri: str) -> Path:
    """Only allow local file:// screenshot URIs (no network access)."""
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise ValueError("The screenshot portal did not return a local image file")
    path = Path(unquote(parsed.path))
    if not path.is_file() or path.stat().st_size > 24_000_000:
        raise ValueError("Screenshot is missing or too large")
    return path


async def capture_screenshot(timeout: float = 180.0) -> str:
    """Open the desktop's interactive screenshot picker and return its image URI.

    Subscribe to the portal Request::Response signal BEFORE making Screenshot()
    to avoid losing a fast response.
    """
    from dbus_next import Message, MessageType, Variant
    from dbus_next.aio import MessageBus

    bus = await MessageBus().connect()
    token = "hoverlate_" + secrets.token_hex(8)
    path = request_path(bus.unique_name, token)
    response = asyncio.get_running_loop().create_future()

    def on_signal(message):
        if (message.message_type == MessageType.SIGNAL
                and message.path == path
                and message.interface == REQUEST_INTERFACE
                and message.member == "Response"
                and not response.done()):
            response.set_result(message.body)
        return False

    bus.add_message_handler(on_signal)
    try:
        rule = f"type='signal',interface='{REQUEST_INTERFACE}',member='Response',path='{path}'"
        add_match = Message(
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="AddMatch",
            signature="s",
            body=[rule],
        )
        answer = await bus.call(add_match)
        if answer.message_type == MessageType.ERROR:
            raise RuntimeError(f"Cannot listen for portal response: {answer.body}")

        call = Message(
            destination=PORTAL_NAME,
            path=PORTAL_PATH,
            interface=PORTAL_INTERFACE,
            member="Screenshot",
            signature="sa{sv}",
            body=["", {
                "interactive": Variant("b", True),
                "handle_token": Variant("s", token),
            }],
        )
        answer = await bus.call(call)
        if answer.message_type == MessageType.ERROR:
            raise RuntimeError(f"Screenshot portal refused request: {answer.body}")
        if not answer.body or answer.body[0] != path:
            raise RuntimeError("Screenshot portal returned an unexpected request handle")

        status, results = await asyncio.wait_for(response, timeout=timeout)
        if status == 1:
            raise CaptureCancelled()
        if status != 0:
            raise RuntimeError(f"Screenshot request failed (code {status})")
        uri = results.get("uri")
        if uri is None or not isinstance(uri.value, str):
            raise RuntimeError("Screenshot portal returned no image URI")
        return uri.value
    finally:
        bus.remove_message_handler(on_signal)
        bus.disconnect()


def extract_text(uri: str, ocr_lang: str = "deu+eng") -> str:
    """Read the portal's image, OCR it in memory, and normalize whitespace."""
    from PIL import Image, ImageOps
    import pytesseract

    path = screenshot_file(uri)
    with Image.open(path) as source:
        source.load()
        image = ImageOps.autocontrast(ImageOps.grayscale(source))
    if image.width * image.height > 70_000_000:
        raise ValueError("Screenshot dimensions are too large")
    # OCR tends to benefit from enlarging small fonts.
    if image.width < 1200:
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    recognized = pytesseract.image_to_string(image, lang=ocr_lang, config="--psm 6")
    return " ".join(recognized.split()).strip()[:600]


def show_translation(original: str, english: str) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = QWidget()
    window.setWindowTitle("Hoverlate")
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    window.setMinimumWidth(330)
    window.setMaximumWidth(620)
    window.setStyleSheet(
        "QWidget {background-color: #181b22; color: #eef2f8;}"
        "QLabel {font-size: 15px; padding: 4px;}"
    )
    layout = QVBoxLayout(window)
    header = QLabel("DE  →  EN")
    header.setStyleSheet("color: #a7b4c7; font-size: 12px;")
    source = QLabel(original)
    source.setWordWrap(True)
    target = QLabel(english)
    target.setWordWrap(True)
    target.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    target.setStyleSheet("color: #b9f7d0; font-size: 18px; padding: 8px 4px;")
    layout.addWidget(header)
    layout.addWidget(source)
    layout.addWidget(target)
    window.show()
    app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select a word on screen and translate it.")
    parser.add_argument("--source", default="de", help="Translation source language")
    parser.add_argument("--target", default="en", help="Translation target language")
    parser.add_argument("--ocr-lang", default="deu+eng", help="Tesseract language packs")
    args = parser.parse_args(argv)

    if not shutil.which("tesseract"):
        parser.error("Tesseract missing: sudo apt install tesseract-ocr tesseract-ocr-deu")
    try:
        uri = asyncio.run(capture_screenshot())
        text = extract_text(uri, args.ocr_lang)
        if not text:
            print("Hoverlate: No text recognized. Try selecting a tighter region.", file=sys.stderr)
            return 1
        translated = WordTranslator(args.source, args.target).translate(text)
        show_translation(text, translated)
        return 0
    except CaptureCancelled:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Hoverlate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
