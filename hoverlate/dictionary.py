"""Small, offline German -> English FreeDict/DICtD dictionary reader.

Only Python's standard library is needed. The Ubuntu dictionary is gzip-
compatible dictzip data + a DICT index of encoded byte offsets.
"""
from __future__ import annotations

import gzip
import html
from pathlib import Path
import re
import unicodedata

DEFAULT_INDEX = Path("/usr/share/dictd/freedict-deu-eng.index")
DEFAULT_DATA = Path("/usr/share/dictd/freedict-deu-eng.dict.dz")
DIGITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
MAX_UNCOMPRESSED = 160 * 1024 * 1024
MAX_DEFINITION_BYTES = 65_536


class DictionaryUnavailable(RuntimeError):
    pass


def decode_dict_offset(encoded: str) -> int:
    """Decode a DICT numerical base64 offset (not MIME base64 bytes)."""
    if not encoded:
        raise ValueError("Empty DICT offset")
    result = 0
    for digit in encoded:
        value = DIGITS.find(digit)
        if value < 0:
            raise ValueError(f"Invalid DICT offset digit: {digit!r}")
        result = result * 64 + value
    return result


def normalize(word: str) -> str:
    return unicodedata.normalize("NFC", word).strip().casefold()


def summarize_definition(raw: bytes, *, limit: int = 280) -> str:
    """Preserve short dictionary meanings, not potentially enormous entries."""
    text = html.unescape(raw.decode("utf-8", errors="replace"))
    text = re.sub(r"<[^>\n]*>", " ", text)
    lines = [" ".join(line.strip().split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return " · ".join(lines)[:limit].strip(" ·")


class FreeDictTranslator:
    """Local exact-headword dictionary lookup; never accesses the network."""

    def __init__(self, source: str = "de", target: str = "en",
                 *, index_path: Path = DEFAULT_INDEX,
                 data_path: Path = DEFAULT_DATA):
        if (source, target) != ("de", "en"):
            raise DictionaryUnavailable(
                "The lightweight bundled system dictionary currently supports de -> en only."
            )
        index_path = Path(index_path)
        data_path = Path(data_path)
        if not index_path.is_file() or not data_path.is_file():
            raise DictionaryUnavailable(
                "German-English FreeDict is not installed. "
                "Run: sudo apt install dict-freedict-deu-eng"
            )

        # A dictzip file is gzip-compatible. Decompress once per running
        # process so mouse-hover lookups need no disk I/O or dictd server.
        try:
            with gzip.open(data_path, "rb") as file:
                self._data = file.read(MAX_UNCOMPRESSED + 1)
        except (OSError, EOFError) as exc:
            raise DictionaryUnavailable(f"Cannot read FreeDict data: {exc}") from exc
        if len(self._data) > MAX_UNCOMPRESSED:
            raise DictionaryUnavailable("FreeDict data is unexpectedly large")
        self._index: dict[str, list[tuple[int, int]]] = {}
        with index_path.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) < 3:
                    continue
                headword, offset_s, size_s = fields[:3]
                try:
                    offset = decode_dict_offset(offset_s)
                    size = decode_dict_offset(size_s)
                except ValueError:
                    continue
                if size <= 0 or size > MAX_DEFINITION_BYTES:
                    continue
                if offset < 0 or offset + size > len(self._data):
                    continue
                key = normalize(headword)
                if not key or key.startswith("00-database-"):
                    continue
                refs = self._index.setdefault(key, [])
                if len(refs) < 3:
                    refs.append((offset, size))
        if not self._index:
            raise DictionaryUnavailable("FreeDict index is empty or incompatible")

    @property
    def entry_count(self) -> int:
        return len(self._index)

    def try_translate(self, word: str) -> str:
        key = normalize(word)
        if not key:
            return "No word recognized"
        references = self._index.get(key)
        if not references:
            return f"No dictionary entry for '{word}'"
        meanings = []
        for offset, size in references:
            meaning = summarize_definition(self._data[offset:offset + size])
            if meaning and meaning not in meanings:
                meanings.append(meaning)
        return " / ".join(meanings)[:360] if meanings else f"No definition for '{word}'"


def make_translator(source: str = "de", target: str = "en", mode: str = "dictionary"):
    if mode in ("dictionary", "auto", "offline"):
        return FreeDictTranslator(source, target)
    if mode == "google":
        from .translate import ThrottledTranslator
        return ThrottledTranslator(source, target)
    raise ValueError(f"Unknown translation mode {mode!r}")


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Inspect the local FreeDict dictionary")
    parser.add_argument("action", choices=["check", "lookup"])
    parser.add_argument("word", nargs="?")
    args = parser.parse_args(argv)
    try:
        dictionary = FreeDictTranslator()
    except DictionaryUnavailable as exc:
        parser.exit(1, f"Hoverlate: {exc}\n")
    if args.action == "check":
        print(f"FreeDict ready: {dictionary.entry_count} headwords (offline)")
        return 0
    if not args.word:
        parser.error("lookup requires a German word")
    print(f"{args.word}: {dictionary.try_translate(args.word)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
