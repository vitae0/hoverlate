"""Pluggable word translator: Google Translate through deep-translator for v0.1."""

from collections import OrderedDict


class WordTranslator:
    def __init__(self, source: str = "de", target: str = "en", cache_size: int = 1024):
        if cache_size < 1:
            raise ValueError("cache_size must be positive")
        self.source = source
        self.target = target
        self.cache_size = cache_size
        self._cache: OrderedDict[str, str] = OrderedDict()

    def cached(self, word: str) -> str | None:
        key = word.casefold()
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def translate(self, word: str) -> str:
        from deep_translator import GoogleTranslator

        previous = self.cached(word)
        if previous is not None:
            return previous
        result = GoogleTranslator(source=self.source, target=self.target).translate(word)
        if not result or not isinstance(result, str):
            raise RuntimeError("No translation returned")
        key = word.casefold()
        self._cache[key] = result
        self._cache.move_to_end(key)
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return result
