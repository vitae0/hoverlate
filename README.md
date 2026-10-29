# Hoverlate

Translate German words in games without leaving the game.

**v0.3: Keyboard shortcut → select a word → English translation.** GNOME Wayland uses the standard XDG Screenshot portal. No GNOME Shell extension, background daemon, or global mouse tracking. The older X11 automatic hover implementation remains available for X11 sessions.

## Ubuntu / GNOME Wayland

~~~bash
sudo apt update
sudo apt install -y python3-venv python3-pip tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
git clone https://github.com/vitae0/hoverlate.git
cd hoverlate
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
hoverlate-snap
~~~

If Hoverlate is already cloned and installed:

~~~bash
cd ~/hoverlate
git pull --ff-only
source .venv/bin/activate
python -m pip install -e .
hoverlate-snap
~~~

1. GNOME's standard screenshot picker opens. Select **Selection** and drag a small rectangle around the German word or phrase.
2. Confirm the screenshot with Enter (or the capture button).
3. Hoverlate recognizes the text and shows its English translation in an always-on-top window.
4. Close the popup when finished.

GNOME may save a screenshot copy to Pictures/Screenshots and/or your clipboard. Hoverlate does not take additional screenshots or send image data to the translation provider. Recognized **text** is sent to Google Translate using the unofficial deep-translator client. Do not use it on sensitive text.

### Keyboard shortcut

Open **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → Add Shortcut**.

- Name: Hoverlate
- Command: absolute path to your Python environment's Hoverlate shortcut entrypoint, for example /home/USERNAME/hoverlate/.venv/bin/hoverlate-snap
- Shortcut: e.g., Ctrl+Alt+Y

Find your executable after activating the environment:

~~~bash
command -v hoverlate-snap
~~~

You no longer need to open a terminal. Each screenshot still requires confirmation from GNOME; this is the Wayland security boundary.

### Retire the old GNOME extension

The experimental v0.2 GNOME extension is **not needed**. If it was enabled, disable it:

~~~bash
gnome-extensions disable hoverlate@hoverlate.dev
~~~

You do not need to log out or restart GNOME Shell for v0.3.

## X11 automatic hover mode (experimental)

On X11, the original hover-translation background process is still available:

~~~bash
echo $XDG_SESSION_TYPE
hoverlate
~~~

The default hoverlate command detects Wayland and opens the screenshot picker instead. Use hoverlate-snap directly for the new workflow on any desktop supporting the portal.

## Languages

~~~bash
hoverlate-snap --source de --target en --ocr-lang deu+eng
~~~

Source and target use Google Translate language codes; OCR uses installed Tesseract language packs.

## Limitations and privacy

- GNOME Wayland is the primary target; other portal implementations are not tested.
- Screenshots are processed only after explicit user selection; no screen recording.
- The Screenshot portal can save its own capture and change the system clipboard.
- The internet translation provider may rate-limit requests.
- OCR may fail on stylized fonts. Select a tight rectangle.
- The new path has unit tests, but it has **not been end-to-end tested on Ubuntu GNOME 50.1 or Bad End Theater**.

## Run tests

~~~bash
pip install -e '.[dev]'
pytest -q
~~~

MIT licensed.
