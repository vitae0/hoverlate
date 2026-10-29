"""Experimental live Wayland hover translator via ScreenCast/PipeWire cursor metadata.

One screen-sharing approval; no GNOME Shell extension, no screenshot picker.
"""
import argparse
import asyncio
import math
import os
import secrets
import shutil
import sys
import threading
import time

PORTAL = "org.freedesktop.portal.Desktop"
ROOT = "/org/freedesktop/portal/desktop"
SC = "org.freedesktop.portal.ScreenCast"
REQ = "org.freedesktop.portal.Request"


def request_path(sender, token):
    return f"{ROOT}/request/{sender.lstrip(':').replace('.', '_')}/{token}"


class ScreenCast:
    def __init__(self):
        self.bus = None
        self.session = None
        self.fd = None

    async def open(self):
        from dbus_next.aio import MessageBus
        from dbus_next import Message, MessageType, Variant

        self.bus = await MessageBus(negotiate_unix_fd=True).connect()

        async def call(method, signature, args):
            reply = await self.bus.call(Message(destination=PORTAL, path=ROOT,
                                                interface=SC, member=method,
                                                signature=signature, body=args))
            if reply.message_type == MessageType.ERROR:
                raise RuntimeError(f"ScreenCast {method}: {reply.body}")
            return reply

        async def request(method, signature, args, index):
            token = "hv_" + secrets.token_hex(8)
            path = request_path(self.bus.unique_name, token)
            future = asyncio.get_running_loop().create_future()

            def handler(msg):
                if (msg.message_type == MessageType.SIGNAL and msg.path == path and
                        msg.interface == REQ and msg.member == "Response" and not future.done()):
                    future.set_result(msg.body)
                return False

            rule = f"type='signal',interface='{REQ}',member='Response',path='{path}'"
            reply = await self.bus.call(Message(
                destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus", member="AddMatch",
                signature="s", body=[rule]))
            if reply.message_type == MessageType.ERROR:
                raise RuntimeError(f"Cannot subscribe to portal signals: {reply.body}")
            self.bus.add_message_handler(handler)
            args[index]["handle_token"] = Variant("s", token)
            try:
                reply = await call(method, signature, args)
                if not reply.body or reply.body[0] != path:
                    raise RuntimeError("Unexpected ScreenCast request handle")
                code, values = await asyncio.wait_for(future, timeout=180)
                if code != 0:
                    raise RuntimeError("Screen-sharing permission cancelled or rejected")
                return values
            finally:
                self.bus.remove_message_handler(handler)

        created = await request(
            "CreateSession", "a{sv}",
            [{"session_handle_token": Variant("s", "hv_" + secrets.token_hex(8))}], 0)
        self.session = created["session_handle"].value
        # Cursor mode 4 provides cursor position as PipeWire metadata.
        opts = {"types": Variant("u", 1), "multiple": Variant("b", False),
                "cursor_mode": Variant("u", 4)}
        await request("SelectSources", "oa{sv}", [self.session, opts], 1)
        started = await request("Start", "osa{sv}", [self.session, "", {}], 2)
        streams = started.get("streams")
        if not streams or not streams.value:
            raise RuntimeError("No shared monitor stream returned")
        node = int(streams.value[0][0])
        reply = await call("OpenPipeWireRemote", "oa{sv}", [self.session, {}])
        self.fd = os.dup(reply.unix_fds[int(reply.body[0])])
        return node, self.fd

    async def close(self):
        from dbus_next import Message
        if self.bus is not None and self.session:
            try:
                await self.bus.call(Message(
                    destination=PORTAL, path=self.session,
                    interface="org.freedesktop.portal.Session", member="Close"))
            except Exception:
                pass
        if self.bus is not None:
            self.bus.disconnect()
            self.bus = None
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


def get_cursor_metadata(buffer):
    """pipewiresrc maps SPA_META_Cursor to a GStreamer cursor ROI."""
    from gi.repository import GstVideo, GLib
    roi = GstVideo.buffer_get_video_region_of_interest_meta_id(buffer, 0)
    if roi is None or GLib.quark_to_string(roi.roi_type) != "cursor":
        return None
    return int(roi.x), int(roi.y)


def recognize_crop(image, cursor, lang):
    from PIL import Image, ImageOps
    import pytesseract
    from .ocr import hovered_word

    x, y = cursor
    left, top = max(0, x - 260), max(0, y - 100)
    right, bottom = min(image.width, x + 260), min(image.height, y + 100)
    if left >= right or top >= bottom:
        return None
    crop = ImageOps.autocontrast(ImageOps.grayscale(image.crop((left, top, right, bottom))))
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
    data = pytesseract.image_to_data(
        crop, lang=lang, config="--psm 11", output_type=pytesseract.Output.DICT)
    return hovered_word(data, (x - left) * 2, (y - top) * 2)


def read_sample(sample):
    from gi.repository import Gst, GstVideo
    from PIL import Image

    buffer = sample.get_buffer()
    cursor = get_cursor_metadata(buffer)
    if cursor is None:
        return None
    caps = sample.get_caps().get_structure(0)
    width, height = int(caps.get_value("width")), int(caps.get_value("height"))
    fmt = caps.get_string("format")
    formats = {"RGB": "RGB", "BGR": "BGR", "RGBx": "RGBX",
               "BGRx": "BGRX", "RGBA": "RGBA", "BGRA": "BGRA"}
    if fmt not in formats:
        raise RuntimeError(f"Unsupported PipeWire video format: {fmt}")
    meta = GstVideo.buffer_get_video_meta(buffer)
    stride = int(meta.stride[0]) if meta else width * (3 if fmt in ("RGB", "BGR") else 4)
    ok, mapped = buffer.map(Gst.MapFlags.READ)
    if not ok:
        raise RuntimeError("Cannot map a video frame")
    try:
        image = Image.frombytes("RGB", (width, height), bytes(mapped.data),
                                "raw", formats[fmt], stride, 1)
    finally:
        buffer.unmap(mapped)
    return cursor, image


def stream_loop(fd, node, settings, events, stop):
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstVideo", "1.0")
    from gi.repository import Gst
    from .translate import ThrottledTranslator, TranslationRateLimited

    Gst.init(None)
    src = Gst.ElementFactory.make("pipewiresrc", "capture")
    converter = Gst.ElementFactory.make("videoconvert", "convert")
    caps = Gst.ElementFactory.make("capsfilter", "rgb")
    sink = Gst.ElementFactory.make("appsink", "frames")
    if not all((src, converter, caps, sink)):
        raise RuntimeError("Install gstreamer1.0-pipewire and gstreamer1.0-plugins-base")
    src.set_property("fd", os.dup(fd))
    src.set_property("path", str(node))
    caps.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
    sink.set_property("sync", False)
    sink.set_property("max-buffers", 1)
    sink.set_property("drop", True)
    pipeline = Gst.Pipeline.new("hoverlate-live")
    for elem in (src, converter, caps, sink):
        pipeline.add(elem)
    if not (src.link(converter) and converter.link(caps) and caps.link(sink)):
        raise RuntimeError("Could not connect the video pipeline")
    if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
        raise RuntimeError("Could not start PipeWire stream")
    translator = ThrottledTranslator(settings.source, settings.target)
    # Capture cursor ROI *before* videoconvert. Some video transforms can
    # drop/alter GstVideoRegionOfInterestMeta on their output buffers.
    cursor_state = {"last": None, "seen_at": 0.0, "source_frames": 0,
                    "cursor_frames": 0}
    cursor_lock = threading.Lock()

    def capture_source_cursor(_pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK
        position = get_cursor_metadata(buffer)
        with cursor_lock:
            cursor_state["source_frames"] += 1
            if position is not None:
                cursor_state["last"] = position
                cursor_state["seen_at"] = time.monotonic()
                cursor_state["cursor_frames"] += 1
        return Gst.PadProbeReturn.OK

    probe_pad = src.get_static_pad("src")
    probe_id = probe_pad.add_probe(Gst.PadProbeType.BUFFER, capture_source_cursor)
    last_position = None
    steady_since = time.monotonic()
    last_ocr = 0.0
    last_word = None
    first_frame = time.monotonic()
    try:
        while not stop.is_set():
            sample = sink.emit("try-pull-sample", int(0.2 * Gst.SECOND))
            if sample is None:
                message = pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
                if message is not None:
                    raise RuntimeError("Screen-sharing stream ended: " + str(message.type))
                continue
            cursor = get_cursor_metadata(sample.get_buffer())
            if cursor is None:
                with cursor_lock:
                    cursor = cursor_state["last"]
                    last_seen = cursor_state["seen_at"]
                    frames_seen = cursor_state["source_frames"]
                    cursor_frames = cursor_state["cursor_frames"]
                # A brief gap in cursor metadata is normal; reuse the most
                # recent source-side position, not an unrelated OCR result.
                if cursor is not None and time.monotonic() - last_seen > 3.0:
                    cursor = None
                if cursor is None:
                    if time.monotonic() - first_frame > 15:
                        raise RuntimeError(
                            "No PipeWire cursor position available "
                            f"(source frames={frames_seen}, cursor ROI frames={cursor_frames}). "
                            "ScreenCast supports cursor mode 4 in theory, but "
                            "this stream did not expose usable cursor metadata."
                        )
                    continue
            now = time.monotonic()
            if last_position is None or math.dist(cursor, last_position) > 8:
                last_position = cursor
                steady_since = now
                last_word = None
                events.hide.emit()
            if now - steady_since < settings.dwell_ms / 1000 or now - last_ocr < 1.0:
                continue
            last_ocr = now
            data = read_sample(sample)
            if data is None:
                continue
            cursor, image = data
            word = recognize_crop(image, cursor, settings.ocr_lang)
            if not word:
                events.hide.emit()
                continue
            if word == last_word:
                continue
            try:
                translation = translator.try_translate(word)
            except TranslationRateLimited as exc:
                # A 429 is not fatal: cursor tracking and OCR keep working,
                # cached translations remain available during the cooldown.
                print("Hoverlate live: " + str(exc), file=sys.stderr, flush=True)
                events.show.emit("Hoverlate", f"Rate limited; retry in {exc.wait_seconds:.0f}s",
                                 cursor[0], cursor[1])
                continue
            except Exception as exc:
                # Network outages and temporary translation failures must not
                # close the entire screen-sharing session.
                print(f"Hoverlate live: translation temporarily unavailable: {exc}",
                      file=sys.stderr, flush=True)
                continue
            if translation is None:
                # Request pacing/cooldown is active; check again on later frames.
                continue
            events.show.emit(word, translation, cursor[0], cursor[1])
            last_word = word
    finally:
        probe_pad.remove_probe(probe_id)
        pipeline.set_state(Gst.State.NULL)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Continuous Wayland hover translation")
    parser.add_argument("--source", default="de")
    parser.add_argument("--target", default="en")
    parser.add_argument("--ocr-lang", default="deu+eng")
    parser.add_argument("--dwell-ms", type=int, default=400)
    args = parser.parse_args(argv)
    if args.dwell_ms < 100:
        parser.error("Dwell must be at least 100 milliseconds")
    if not shutil.which("tesseract"):
        parser.error("Install tesseract-ocr and tesseract-ocr-deu")
    try:
        import gi
        gi.require_version("Gst", "1.0")
        gi.require_version("GstVideo", "1.0")
        from gi.repository import Gst
        from PySide6.QtCore import QObject, Signal, Qt, QTimer
        from PySide6.QtWidgets import QApplication, QLabel
    except ImportError as exc:
        parser.error("Missing GStreamer/PyGObject packages. See README. " + str(exc))

    class Events(QObject):
        show = Signal(str, str, int, int)
        hide = Signal()
        error = Signal(str)

    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    tip = QLabel()
    tip.setWordWrap(True)
    tip.setMaximumWidth(370)
    # A top-level Qt.ToolTip is an xdg_popup on Wayland and requires a
    # transient parent. Use an ordinary non-activating window instead.
    # Compositors may ignore absolute tip.move() placement.
    tip.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint |
                       Qt.WindowType.FramelessWindowHint |
                       Qt.WindowType.WindowDoesNotAcceptFocus |
                       Qt.WindowType.WindowTransparentForInput)
    tip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    tip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    tip.setStyleSheet(
        "color: white; background: #181b22; border: 1px solid #596171; "
        "border-radius: 8px; padding: 11px;")
    events = Events()

    def present(word, english, x, y):
        tip.setText(f"{word} → {english}")
        tip.adjustSize()
        # Best effort: absolute popup positioning is compositor-controlled on Wayland.
        tip.move(x + 18, y + 20)
        tip.show()

    events.show.connect(present)
    events.hide.connect(tip.hide)
    events.error.connect(lambda msg: (print(msg, file=sys.stderr), app.quit()))
    stop = threading.Event()

    def runner():
        session = ScreenCast()

        async def run():
            try:
                node, fd = await session.open()
                await asyncio.to_thread(stream_loop, fd, node, args, events, stop)
            finally:
                await session.close()

        try:
            asyncio.run(run())
        except Exception as exc:
            if not stop.is_set():
                events.error.emit("Hoverlate live: " + str(exc))

    threading.Thread(target=runner, daemon=True).start()
    app.aboutToQuit.connect(stop.set)
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    print("Hoverlate live: share the game monitor once; hover over text. Ctrl+C to exit.",
          flush=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
