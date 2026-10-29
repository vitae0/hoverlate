"""Optional offline translation for Hoverlate, powered by Argos Translate.

Models are downloaded only by the explicit 'hoverlate-offline install' command.
Never download language packs while running the live mouse tracker.
"""
import argparse
import sys

from .translate import WordTranslator


class OfflineTranslator(WordTranslator):
    def __init__(self, source="de", target="en", cache_size=2048):
        super().__init__(source=source, target=target, cache_size=cache_size)
        try:
            from argostranslate.translate import get_installed_languages
        except ImportError as exc:
            raise RuntimeError(
                "Argos Translate not installed. Run: pip install -e '.[offline]'"
            ) from exc
        languages = {lang.code: lang for lang in get_installed_languages()}
        if source not in languages or target not in languages:
            raise RuntimeError(
                f"Offline {source}→{target} model is missing. "
                "Run: hoverlate-offline install"
            )
        self.model = languages[source].get_translation(languages[target])
        if self.model is None:
            raise RuntimeError(
                f"No offline translation route for {source}→{target}. "
                "Run: hoverlate-offline install"
            )

    def try_translate(self, word: str) -> str:
        cached = self.cached(word)
        if cached is not None:
            return cached
        result = self.model.translate(word)
        if not result or not isinstance(result, str):
            raise RuntimeError(f"Offline translation failed for: {word!r}")
        self._cache[word.casefold()] = result
        self._cache.move_to_end(word.casefold())
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return result


def make_translator(source: str, target: str, mode: str = "auto"):
    """Prefer an installed local Argos language pair; never download implicitly."""
    if mode in ("auto", "offline"):
        try:
            result = OfflineTranslator(source, target)
            print("Hoverlate: offline translation enabled (no Google requests).",
                  flush=True)
            return result
        except (ImportError, RuntimeError):
            if mode == "offline":
                raise
    if mode not in ("auto", "google"):
        raise ValueError(f"Unknown translation backend: {mode}")
    from .translate import ThrottledTranslator
    print("Hoverlate: using rate-limited online translations. "
          "For offline use: pip install -e '.[offline]' && hoverlate-offline install",
          flush=True)
    return ThrottledTranslator(source, target)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Install one offline Argos Translate language pack for Hoverlate.")
    parser.add_argument("action", choices=["install", "status"])
    parser.add_argument("--source", default="de")
    parser.add_argument("--target", default="en")
    args = parser.parse_args(argv)
    try:
        import argostranslate.package as package
    except ImportError:
        parser.error("First run: pip install -e '.[offline]'")
    if args.action == "status":
        try:
            OfflineTranslator(args.source, args.target)
        except RuntimeError as exc:
            print(f"Not installed: {exc}")
            return 1
        print(f"Installed: {args.source} → {args.target}")
        return 0
    try:
        OfflineTranslator(args.source, args.target)
    except RuntimeError:
        pass
    else:
        print(f"Offline model {args.source} → {args.target} is already installed.")
        return 0
    print("Downloading offline language model (one-time internet connection required).")
    try:
        package.update_package_index()
        available = package.get_available_packages()
        model = next(
            (item for item in available
             if item.from_code == args.source and item.to_code == args.target),
            None,
        )
        if model is None:
            raise RuntimeError(
                f"No Argos package for {args.source} → {args.target} in package index"
            )
        package.install_from_path(model.download())
        OfflineTranslator(args.source, args.target)
    except Exception as exc:
        print(f"Unable to install offline model: {exc}", file=sys.stderr)
        return 1
    print(f"Offline model installed: {args.source} → {args.target}. Run hoverlate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
