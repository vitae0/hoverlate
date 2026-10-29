# Hoverlate

**Translate words in games and desktop apps simply by hovering over them.**

Hoverlate v0.2 runs on Linux X11 and includes an **experimental GNOME Wayland backend**. It captures a small screen region around the cursor, uses Tesseract OCR to identify the word beneath it, and shows a click-through translation popup.

> **Status:** Early MVP. Unit-tested, but not yet verified inside Bad End Theater or a real desktop session. Use windowed/borderless game mode if a fullscreen window hides the popup.

## Features

- German OCR and German → English translations by default.
- Hover instead of copy/paste: wait about 400 ms over a word.
- Small-region OCR, non-interactive overlay, and in-memory translation cache.
- Configurable source, target and OCR languages.

## Install on Ubuntu X11/Xorg

Check your desktop session:

~~~bash
echo $XDG_SESSION_TYPE
~~~

For these X11 instructions it must say `x11`. If it says `wayland`, use the GNOME Wayland instructions below.

~~~bash
sudo apt update
sudo apt install -y python3-venv python3-pip tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
git clone https://github.com/vitae0/hoverlate.git
cd hoverlate
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
hoverlate
~~~

Keep the terminal running. Hover over a word and wait for the popup; quit with **Ctrl+C**.

Options:

~~~bash
hoverlate --source de --target en --ocr-lang deu+eng --dwell-ms 400
~~~

To run tests:

~~~bash
pip install -e '.[dev]'
pytest -q
~~~

## Ubuntu GNOME Wayland (experimental)

You do **not** need to switch to X11. GNOME requires an explicitly installed Shell extension for global pointer access and screenshot capture.

~~~bash
sudo apt update
sudo apt install -y python3-venv python3-pip tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
git clone https://github.com/vitae0/hoverlate.git
cd hoverlate
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[wayland]'
mkdir -p ~/.local/share/gnome-shell/extensions
cp -r gnome-extension/hoverlate@hoverlate.dev ~/.local/share/gnome-shell/extensions/
gnome-extensions enable hoverlate@hoverlate.dev
hoverlate
~~~

**If GNOME says the extension is not found**, log out and back in, enable it again, then run `hoverlate` from the virtual environment. Check with `gnome-extensions list --enabled`.

This experimental backend works only with GNOME Shell, not KDE, Hyprland, or Sway. GNOME Shell supplies cursor position, small in-memory screenshots near the pointer (up to 520×220 logical pixels, limited to one capture every 500 ms) and draws the overlay. Python does OCR and translation. It requires no X11 desktop session.

**Privacy warning:** The extension exposes cursor position and small cursor-area screenshots to processes that can reach your user-session D-Bus. While enabled, other local applications may request those captures. Disable it when not actively using Hoverlate, particularly around sensitive content:

~~~bash
gnome-extensions disable hoverlate@hoverlate.dev
~~~

OCR screenshots are not saved to files. Recognized words are sent to the online translation provider. This code has passed syntax and unit checks but has **not yet been tested in a real GNOME Shell session or Bad End Theater**. GNOME release differences, fullscreen game mode, and HiDPI can require fixes.

## Privacy and limitations

- **Wayland:** GNOME Shell only via the opt-in extension. A normal Wayland application cannot freely read global cursor coordinates or capture the desktop.
- **Online translations.** Google Translate is accessed through the unofficial \`deep-translator\` client. Recognized words are sent to a third party; never hover over sensitive text while using Hoverlate. This may be rate-limited or unavailable.
- Screenshots are processed in memory, not saved to disk. The word cache is also memory-only.
- OCR can struggle with stylized small fonts. Fullscreen-exclusive game surfaces may cover the tooltip.
- Multi-monitor scaling and fractional DPI alignment are not fully tested.

## Roadmap

- [ ] End-to-end test in Bad End Theater on an X11 desktop.
- [ ] Optional offline translation models.
- [ ] Sentence context and vocabulary saving.
- [x] Experimental GNOME Shell Wayland bridge (not yet desktop-tested).
- [ ] Cross-compositor Wayland portal support.
- [ ] Windows and macOS support.

MIT licensed.
