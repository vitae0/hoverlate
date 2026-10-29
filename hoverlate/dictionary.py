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


def compact_gloss(definition: str, headword: str = "") -> str:
    """Find the FIRST English translation, never the headword or IPA.

    FreeDict dictd entries start with the German headword and optional
    pronunciation/part-of-speech lines; blindly taking the first line is wrong.
    """
    if not definition:
        return ""
    text = html.unescape(definition)
    text = re.sub(r"<(?:br|p|div|blockquote|li)\b[^>]*>", "\n",
                  text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]*>", " ", text)
    lines = re.split(r"[\r\n]+|\s+·\s+", text)
    headword_key = normalize(headword)
    labels = {"n", "v", "adj", "adv", "noun", "verb", "adjective",
              "adverb", "f", "m", "nt", "pron", "pronoun",
              "masculine", "feminine", "neuter", "pl", "sing",
              "transitive", "intransitive", "intr", "trans"}
    for original in lines:
        line = original.strip(" \t–—-: ")
        if not line:
            continue
        # Headword may be followed by IPA, e.g. "gehen /ˈɡeːən/ v.".
        if headword_key:
            pattern = r"^" + re.escape(headword) + r"(?=$|[\s/:[(])"
            line = re.sub(pattern, "", line, count=1, flags=re.IGNORECASE).strip()
        # Remove IPA and phonetic transcription before considering a meaning.
        line = re.sub(r"/[^/\n]{1,110}/", " ", line)
        line = re.sub(r"\[[^\]\n]{1,110}\]", " ", line)
        line = re.sub(r"\b(?:IPA|pronunciation|Aussprache|Phonetik)\s*:",
                      " ", line, flags=re.IGNORECASE)
        line = re.sub(r"^\s*\d+[.)]\s*", "", line)
        # Grammar markers often appear on their own line, or ahead of a gloss.
        for _ in range(3):
            match = re.match(r"^\s*([A-Za-z.]{1,15})\s*(?::|\.\s*|\s+|$)", line)
            if not match or match.group(1).rstrip(".").casefold() not in labels:
                break
            line = line[match.end():]
        line = re.split(r"\s*(?:;|\|| / | — | – |→)\s*", line, maxsplit=1)[0]
        line = re.sub(r"\s*\([^)]{1,36}\)\s*$", "", line)
        line = re.sub(r"\s+", " ", line).strip(" .,;:/·")
        if not line or normalize(line) == headword_key:
            continue
        if normalize(line) in labels:
            continue
        # Transcription without delimiters is still not an English gloss.
        if not re.search(r"[A-Za-z]", line):
            continue
        if sum(ch in "ˈˌːɡəɐʃʊʁŋçʒθðæʔ" for ch in line) >= 2:
            continue
        return " ".join(line.split()[:4])[:36].rstrip(" ,;:-")
    return ""


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

    def has_word(self, word: str) -> bool:
        """Check for a usable local dictionary lemma; no internet or disk I/O."""
        from .morphology import lemma_candidates
        return any(candidate in self._index for candidate in lemma_candidates(normalize(word)))

    def try_translate(self, word: str) -> str:
        """Resolve common inflections, then show a real English gloss only."""
        from .morphology import lemma_candidates
        for lemma in lemma_candidates(normalize(word)):
            references = self._index.get(lemma, ())
            for offset, size in references:
                raw = self._data[offset:offset + size].decode("utf-8", errors="replace")
                meaning = compact_gloss(raw, lemma)
                if meaning:
                    return meaning
        return ""


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
