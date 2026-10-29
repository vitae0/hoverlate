# Hoverlate

Translate German words by hovering over them in games, without cloud translation.

## v0.7.0: game-font recognition, real English glosses and lower CPU usage

This release addresses three problems observed during real game use:

- **Visual OCR:** recognises pixels around the cursor, including text drawn into game scenes rather than accessible application text. A 380x140 crop is contrast-adjusted, inverted for dark dialogue boxes and sharpened. If the first pass fails, adaptive mode tries one binary/sparse-text pass. This remains Tesseract OCR; decorative fonts may still be misread.
- **English translations:** skips the German headword, IPA pronunciations and grammatical labels before displaying the first short English gloss. Glosses are cached; no online translation is used by default.
- **Conjugated German verbs:** resolves common irregular forms (e.g. `ging` → `gehen`) and regular endings (e.g. `spielte` → `spielen`). Accepts a guess only if FreeDict has a usable English gloss. It is not a complete German morphological analyzer.
- **CPU:** default Tesseract language is now German-only (`deu`), OpenMP uses one thread, frames beyond **12 FPS** are dropped *before* RGB conversion, OCR works on smaller crops, and identical static game text is not repeatedly OCRed for eight seconds.
- **Stability:** isolated OCR errors and timeouts no longer close the screen-sharing session.

The first-hover delay remains **150 ms**. Actual latency also depends on OCR processing time and how often the portal sends frames.

~~~bash
hoverlate                              # adaptive graphics OCR, 12 FPS, 150 ms
hoverlate --ocr-mode fast              # one OCR pass, lowest CPU
hoverlate --capture-fps 8              # fewer frames, somewhat slower response
hoverlate --ocr-lang deu+eng           # optional mixed German-English OCR
hoverlate-dict lookup ging             # tests German inflection resolution
~~~

No additional Python, ML or CUDA dependencies are needed.

## v0.6.2: small quality-of-life and stability update

- **150 ms first hover stays fast:** each significant cursor movement clears the previous OCR delay, so a new word is checked promptly.
- **Lower idle CPU usage:** if no word is found, OCR retries at most about every 800 ms; when a word is already displayed, every 2 seconds. Moving to a new word resets the interval.
- **True single-line bubble:** long meanings are cut with an ellipsis instead of expanding into a tall tooltip.
- **Less flicker:** equivalent uppercase/lowercase OCR reads do not trigger redundant updates; words can reappear after briefly disappearing.
- **Recoverable OCR errors:** a couple of transient failures no longer immediately end the session; three consecutive failures still raise a meaningful error.
- Check your installation with `hoverlate --version` (or `hoverlate-live --version`).

The default is still **150 ms hover**, with local FreeDict translation. The live capture and cursor-metadata implementation are otherwise unchanged.

### v0.6.1: compact offline word popups

The default translation backend is now **FreeDict German -> English**, installed from Ubuntu's own package repository.

- **No PyTorch, CUDA, Stanza, Argos Translate or Google requests in the default installation.**
- Dictionary lookups happen locally with Python's standard library.
- Hover tooltip shows only the first short meaning (usually one to four words) in a compact, unobtrusive bubble. Missing entries produce no bubble. The default hover delay is **150 ms** (adjustable with `--dwell-ms`).
- Live cursor tracking and OCR still use the experimental GNOME Wayland ScreenCast/PipeWire backend.
- Exact word lookup is fast. FreeDict is a headword dictionary, not a sentence-level machine translation model. Inflected German words may not be found, and some dictionary entries contain multiple meanings.
- Missing words produce no popup. Hoverlate does not invent translations or silently switch to the internet.

### Ubuntu GNOME Wayland: install/update

~~~bash
cd ~/hoverlate
git pull --ff-only
sudo apt update
sudo apt install -y dict-freedict-deu-eng tesseract-ocr tesseract-ocr-deu \
  python3-gi python3-gst-1.0 gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 gstreamer1.0-pipewire gstreamer1.0-plugins-base
source .venv/bin/activate
python -m pip install -e .
hoverlate-dict check
hoverlate-dict lookup gehen
hoverlate
~~~

If the environment does not see system GStreamer packages, recreate it once:

~~~bash
deactivate 2>/dev/null || true
python3 -m venv --clear --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
~~~

On Wayland, GNOME asks to share the monitor containing your game. Once you approve it, hover a German word for ~150ms and Hoverlate attempts OCR and local dictionary lookup. Quit via Ctrl+C. This is an experimental live integration and may need further desktop-specific fixes.

### Offline and optional online modes

~~~bash
hoverlate                           # local FreeDict by default
hoverlate --translator dictionary   # explicitly local
hoverlate --translator offline      # same local dictionary, legacy alias
hoverlate-dict check                # inspect installed dictionary
hoverlate-dict lookup verlassen     # lookup without launching game
~~~

No internet translation is attempted unless you **explicitly** request it:

~~~bash
python -m pip install -e '.[online]'
hoverlate --translator google
~~~

The optional Google backend uses the unofficial deep-translator client and may be rate-limited. The one-shot screenshot mode also uses the online backend and requires the optional online dependency.

### How local dictionary lookups work

Ubuntu's dict-freedict-deu-eng package provides the two files:

- /usr/share/dictd/freedict-deu-eng.index
- /usr/share/dictd/freedict-deu-eng.dict.dz

Hoverlate reads the compressed dictzip/gzip-compatible data once in memory and indexes headwords using DICT's numerical base64 byte offsets. Each hover is a direct in-memory lookup; no dictd daemon, PyTorch, or model download is required.

The FreeDict dataset is installed separately from Ubuntu and retains its own license. Hoverlate does not ship or modify the dictionary.

### Known limitations

- **GNOME Wayland live cursor metadata remains unverified end-to-end on all setups.** Hoverlate v0.5 added a source-side GStreamer metadata probe, but some ScreenCast/GStreamer combinations may still not provide usable cursor coordinates.
- Wayland may prevent the tooltip from appearing at the exact mouse location.
- Game font styles affect Tesseract OCR results.
- Inflected German words often differ from dictionary headwords. Version 0.6 performs exact lookup and case-folding, not advanced morphological analysis.
- For other language directions, an additional dictionary backend would be needed.

### Tests

~~~bash
python -m pip install -e '.[dev]'
python -m pytest -q
~~~

MIT licensed (application code only).
