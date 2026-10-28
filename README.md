# Hoverlate

**Translate words in games and desktop apps simply by hovering over them.**

Hoverlate v0.1 is a Linux **X11-only prototype**. It captures a small screen region around the cursor, uses Tesseract OCR to identify the word beneath it, and shows a click-through translation popup.

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

It must say \`x11\`. Under GNOME, if \`wayland\`, log out and select **Ubuntu on Xorg** from the login screen's gear menu if available.

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

## Privacy and limitations

- **Linux/X11 only.** Wayland does not expose unrestricted global screen capture or mouse coordinates. An XWayland application within a Wayland session does not provide full desktop access.
- **Online translations.** Google Translate is accessed through the unofficial \`deep-translator\` client. Recognized words are sent to a third party; never hover over sensitive text while using Hoverlate. This may be rate-limited or unavailable.
- Screenshots are processed in memory, not saved to disk. The word cache is also memory-only.
- OCR can struggle with stylized small fonts. Fullscreen-exclusive game surfaces may cover the tooltip.
- Multi-monitor scaling and fractional DPI alignment are not fully tested.

## Roadmap

- [ ] End-to-end test in Bad End Theater on an X11 desktop.
- [ ] Optional offline translation models.
- [ ] Sentence context and vocabulary saving.
- [ ] Wayland portal/compositor integration.
- [ ] Windows and macOS support.

MIT licensed.
