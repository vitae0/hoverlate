"""X11 desktop application: dwell over a word to show its translation."""

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
import math
import os
import shutil
import signal
import sys
import time

from .ocr import recognize_at
from .translate import WordTranslator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hover over on-screen text to translate it (X11 MVP).")
    parser.add_argument("--source", default="de", help="Translation source language (default: de)")
    parser.add_argument("--target", default="en", help="Translation target language (default: en)")
    parser.add_argument("--ocr-lang", default="deu+eng", help="Tesseract languages (default: deu+eng)")
    parser.add_argument("--dwell-ms", type=int, default=400, help="Hover delay in milliseconds (default: 400)")
    args = parser.parse_args(argv)

    if os.name != "posix" or sys.platform != "linux":
        parser.error("Version 0.1 currently supports Linux/X11 only")
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        parser.error("Wayland is not supported yet. Log into an X11/Xorg session to run Hoverlate")
    if not os.environ.get("DISPLAY"):
        parser.error("DISPLAY is not set; an X11 desktop session is required")
    if not shutil.which("tesseract"):
        parser.error("Tesseract not found. Install tesseract-ocr and tesseract-ocr-deu")
    if args.dwell_ms < 100:
        parser.error("--dwell-ms must be at least 100")

    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
        from Xlib.display import Display
    except ImportError as exc:
        parser.error(f"Missing dependency: {exc}. Install with pip install -e .")

    class Tip(QWidget):
        def __init__(self) -> None:
            flags = (
                Qt.WindowType.ToolTip
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTransparentForInput
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            super().__init__(None, flags)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setObjectName("tip")
            self.setStyleSheet(
                "QWidget#tip {background: #181b22; border: 1px solid #596171; border-radius: 9px;}"
                "QLabel {color: #f8fafc; font-size: 15px; background: transparent;}"
                "QLabel#original {color: #a7b4c7; font-size: 12px;}"
            )
            layout = QVBoxLayout(self)
            layout.setContentsMargins(13, 9, 13, 10)
            layout.setSpacing(3)
            self.original = QLabel(self)
            self.original.setObjectName("original")
            self.translation = QLabel(self)
            self.translation.setWordWrap(True)
            self.translation.setMaximumWidth(310)
            layout.addWidget(self.original)
            layout.addWidget(self.translation)

        def present(self, word: str, english: str, x: int, y: int, bounds: dict) -> None:
            self.original.setText(word)
            self.translation.setText(english)
            self.adjustSize()
            left, top = bounds["left"], bounds["top"]
            right = left + bounds["width"]
            bottom = top + bounds["height"]
            nx = min(max(x + 18, left), max(left, right - self.width()))
            ny = y + 22
            if ny + self.height() > bottom:
                ny = y - self.height() - 18
            ny = min(max(ny, top), max(top, bottom - self.height()))
            self.move(nx, ny)
            self.show()

    class Hoverlate:
        def __init__(self) -> None:
            self.display = Display()
            self.root = self.display.screen().root
            self.tip = Tip()
            self.translator = WordTranslator(args.source, args.target)
            self.ocr_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hoverlate-ocr")
            self.translation_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hoverlate-translate")
            self.current_pos: tuple[int, int] | None = None
            self.still_since = time.monotonic()
            self.generation = 0
            self.current_word: str | None = None
            self.ocr_job: tuple[Future, int] | None = None
            self.translation_job: tuple[Future, int, str] | None = None
            self.last_ocr_at = -100.0
            self.retry_at = 0.0
            self.timer = QTimer()
            self.timer.setInterval(120)
            self.timer.timeout.connect(self.tick)
            self.timer.start()

        def pos(self) -> tuple[int, int]:
            p = self.root.query_pointer()
            return int(p.root_x), int(p.root_y)

        def tick(self) -> None:
            now = time.monotonic()
            try:
                x, y = self.pos()
            except Exception as exc:
                print(f"Hoverlate: X11 pointer query failed: {exc}", file=sys.stderr)
                self.tip.hide()
                return
            if self.current_pos is None or math.dist((x, y), self.current_pos) > 9:
                self.current_pos = x, y
                self.still_since = now
                self.generation += 1
                self.current_word = None
                self.tip.hide()

            if self.ocr_job and self.ocr_job[0].done():
                future, generation = self.ocr_job
                self.ocr_job = None
                try:
                    word = future.result()
                except Exception as exc:
                    print(f"Hoverlate OCR: {exc}", file=sys.stderr)
                    word = None
                    self.retry_at = now + 3
                if generation == self.generation:
                    if word != self.current_word:
                        self.tip.hide()
                        self.current_word = word
                    if word:
                        cached = self.translator.cached(word)
                        if cached is not None:
                            self.tip.present(word, cached, x, y, self.bounds)
                        elif now >= self.retry_at and (
                            self.translation_job is None or self.translation_job[2] != word
                        ):
                            self.translation_job = (
                                self.translation_pool.submit(self.translator.translate, word),
                                generation,
                                word,
                            )

            if self.translation_job and self.translation_job[0].done():
                future, generation, word = self.translation_job
                self.translation_job = None
                try:
                    translated = future.result()
                except Exception as exc:
                    print(f"Hoverlate translation: {exc}", file=sys.stderr)
                    self.retry_at = now + 12
                else:
                    if generation == self.generation and word == self.current_word:
                        self.tip.present(word, translated, x, y, self.bounds)

            if (
                self.ocr_job is None
                and now - self.still_since >= args.dwell_ms / 1000
                and now - self.last_ocr_at >= 1.1
                and now >= self.retry_at
            ):
                self.last_ocr_at = now
                self.ocr_job = (
                    self.ocr_pool.submit(recognize_at, x, y, ocr_lang=args.ocr_lang),
                    self.generation,
                )

        @property
        def bounds(self) -> dict:
            g = self.root.get_geometry()
            return {"left": 0, "top": 0, "width": g.width, "height": g.height}

        def close(self) -> None:
            self.timer.stop()
            self.tip.close()
            self.ocr_pool.shutdown(wait=False, cancel_futures=True)
            self.translation_pool.shutdown(wait=False, cancel_futures=True)
            self.display.close()

    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    try:
        hoverlate = Hoverlate()
    except Exception as exc:
        print(f"Hoverlate could not start: {exc}", file=sys.stderr)
        return 1
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(400)
    app.aboutToQuit.connect(hoverlate.close)
    print("Hoverlate is running. Hover over German text. Press Ctrl+C to exit.", flush=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
