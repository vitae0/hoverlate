"""German-English translation with an in-memory LRU cache and safe request pacing.

The online service is unofficial. Its actual limits can change without warning.
"""
from collections import OrderedDict
import time


class TranslationRateLimited(RuntimeError):
    """The provider requested a cooldown. Live capture should keep running."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = wait_seconds
        super().__init__(
            f"Google Translate is rate-limiting; waiting {wait_seconds:.0f}s before retry."
        )


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


class ThrottledTranslator(WordTranslator):
    """Non-blocking rate control for continuous mouse/keyboard interaction.

    Cached words return immediately. Uncached words return None if another
    request is too recent or the service is on cooldown, so video capture and
    cursor tracking do not freeze. API rate-limit failures trigger exponential
    cooldown rather than killing the hover loop.
    """

    def __init__(self, source: str = "de", target: str = "en",
                 cache_size: int = 2048, min_interval: float = 3.0,
                 base_backoff: float = 60.0, max_backoff: float = 900.0):
        super().__init__(source, target, cache_size)
        if min_interval <= 0 or base_backoff <= 0 or max_backoff < base_backoff:
            raise ValueError("Invalid translation pacing/backoff settings")
        self.min_interval = min_interval
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.next_allowed_at = 0.0
        self.failures = 0

    @staticmethod
    def is_rate_limit(error: Exception) -> bool:
        details = (type(error).__name__ + " " + str(error)).casefold()
        return any(marker in details for marker in (
            "toomanyrequests", "too many requests", "429",
            "rate limit", "ratelimit", "quota exceeded",
        ))

    def try_translate(self, word: str) -> str | None:
        existing = self.cached(word)
        if existing is not None:
            return existing
        now = time.monotonic()
        if now < self.next_allowed_at:
            return None
        # Reserve the interval before starting the request, even if it fails.
        self.next_allowed_at = now + self.min_interval
        try:
            translation = super().translate(word)
        except Exception as exc:
            if self.is_rate_limit(exc):
                self.failures = min(self.failures + 1, 16)
                wait = min(self.max_backoff, self.base_backoff * (2 ** (self.failures - 1)))
                self.next_allowed_at = max(self.next_allowed_at, time.monotonic() + wait)
                raise TranslationRateLimited(wait) from exc
            # For network failures, skip repeated calls briefly, too.
            self.next_allowed_at = max(self.next_allowed_at, time.monotonic() + 15.0)
            raise
        self.failures = 0
        return translation
