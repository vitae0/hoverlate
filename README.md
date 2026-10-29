# Hoverlate

**Translate German words by hovering over them, including inside games.**

Hoverlate v0.5.0 provides **continuous cursor tracking and live OCR** on Wayland. Instead of a GNOME Shell extension, it uses ScreenCast desktop portal permissions and PipeWire cursor metadata. Once you approve screen sharing, Hoverlate reads the word below your cursor after ~400 ms of stillness. The v0.4.1 release adds online-translation request pacing, cached-word reuse, and automatic cooldown after Google rate-limit responses.

> **Experimental:** The live GNOME Wayland backend has not been end-to-end tested on GNOME Shell 50.1 or Bad End Theater. Cursor metadata availability and tooltip positioning are compositor-dependent.

## Ubuntu GNOME Wayland

In your existing Hoverlate checkout:

~~~bash
cd ~/hoverlate
git pull --ff-only
sudo apt update
sudo apt install -y python3-venv python3-gi python3-gst-1.0 \
  gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 \
  gstreamer1.0-pipewire gstreamer1.0-plugins-base \
  tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
~~~

Ubuntu provides GStreamer and PyGObject as system Python packages. Make sure your virtual environment can see them:

~~~bash
deactivate 2>/dev/null || true
python3 -m venv --clear --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
hoverlate
~~~

GNOME should show a **screen-sharing permission dialog**. Select the monitor containing the game and approve once. Move your cursor onto a German word and pause. A small translation tooltip should appear. Press **Ctrl+C** in the terminal to exit.

No GNOME Shell extension, screenshot picker, or logout is required for this backend.

Optional command-line arguments:

~~~bash
hoverlate-live --source de --target en --ocr-lang deu+eng --dwell-ms 400
~~~

The default hoverlate command uses this live mode on Wayland, and the older automatic hover backend on X11.

## Fixes for GNOME Wayland 50 (v0.5)

Two corrections target reported runtime failures:

- PipeWire cursor ROI is captured **before** GStreamer video conversion, then reused on buffers where the cursor metadata is absent. The stream no longer requires an ROI on every frame.
- The tooltip uses a normal non-activating top-level Qt window instead of a parentless Wayland popup. GNOME still controls final window placement, so positioning right beside the mouse remains best effort.

If the desktop provides no cursor metadata at the source at all, Hoverlate now reports a diagnostic containing source frame and cursor ROI counts. This cannot be solved by claiming that a cursor was detected.

### Recommended: install offline translations

For repeated single-word translations, the official Argos Translate offline model is more reliable than an unofficial Google endpoint. You download it **once** (internet required for setup), and subsequent translation runs are local:

~~~bash
cd ~/hoverlate
source .venv/bin/activate
python -m pip install -e '.[offline]'
hoverlate-offline install
hoverlate --translator offline
~~~

If you want to verify the model installation:

~~~bash
hoverlate-offline status
~~~

Without a local model, default auto mode still uses the rate-limited Google backend. You can explicitly choose Google with `hoverlate --translator google`. The automatic mode prefers local translation whenever the language pair is installed. No language models are downloaded automatically when starting Hoverlate.

**Important:** Translation models can be large and offline model quality may differ from Google. Screensharing and OCR still require the GNOME/PipeWire bridge; the offline model only removes the internet translation failure.

## Optional screenshot fallback

The manual-selection v0.3 mode still exists, but **it is not the default**:

~~~bash
hoverlate-snap
~~~

It opens the screenshot picker only if you deliberately choose this alternative.

## How live mode works

1. The GNOME ScreenCast portal grants temporary access to a monitor.
2. PipeWire streams frames and provides the cursor position as metadata (cursor mode 4).
3. GStreamer decodes frames; the Python backend waits approximately 400 ms for the cursor to stop.
4. OCR processes a small cursor-centred region; Google Translate returns the English word.
5. A lightweight tooltip displays the translation.

No video frames are intentionally stored on disk. **Recognized text** is transmitted to the third-party online translation service. End screen sharing when not using Hoverlate; do not use it over sensitive content.

## Current limitations

- This is not yet tested on an actual GNOME Shell 50.1 desktop; the real error logs are needed to verify functionality.
- Some PipeWire or GStreamer versions might not expose cursor position metadata correctly. The app exits with an error if no cursor metadata arrives.
- Wayland may override absolute tooltip position, meaning it might not appear exactly beside the cursor.
- Select the correct monitor; the app cannot follow the pointer outside a monitor you share.
- Fullscreen-exclusive games may cover the tooltip; windowed or borderless mode can help.
- Stylized fonts and text recognition errors may cause wrong translations.
- Translations use an unofficial online service and still require internet. Network requests are paced at least **3 seconds apart**; repeated words are served immediately from an in-memory cache.
- If the provider returns HTTP 429 / 'too many requests', Hoverlate **keeps tracking the mouse** but pauses new online requests for 60 seconds, doubling the pause on repeated limit errors (up to 15 minutes). Cached translations remain usable. This cannot bypass a provider-side block.
- The word cache lasts only for the current process; restarting Hoverlate will not clear a server-side limit.

## Tests

~~~bash
python -m pip install -e '.[dev]'
python -m pytest -q
~~~

MIT licensed.
