"""Small dependency-free German inflection resolver for dictionary lookups.

Only return candidate lemmas; accept one *only* if FreeDict contains it.
This prevents unsupported forms from producing invented translations.
"""
from __future__ import annotations

IRREGULAR = {
    # High-frequency verbs. Ambiguous forms are checked against FreeDict.
    "bin": "sein", "bist": "sein", "ist": "sein", "sind": "sein",
    "seid": "sein", "war": "sein", "waren": "sein", "warst": "sein",
    "wart": "sein", "gewesen": "sein", "sei": "sein",
    "habe": "haben", "hast": "haben", "hat": "haben",
    "hatte": "haben", "hatten": "haben", "gehabt": "haben",
    "werde": "werden", "wirst": "werden", "wird": "werden",
    "wurde": "werden", "wurden": "werden", "geworden": "werden",
    "ging": "gehen", "gingst": "gehen", "gingen": "gehen",
    "gegangen": "gehen", "geht": "gehen", "gehe": "gehen",
    "kam": "kommen", "kamst": "kommen", "kamen": "kommen",
    "gekommen": "kommen",
    "sah": "sehen", "sahst": "sehen", "sahen": "sehen",
    "siehst": "sehen", "sieht": "sehen", "gesehen": "sehen",
    "gab": "geben", "gabst": "geben", "gaben": "geben",
    "gibst": "geben", "gibt": "geben", "gegeben": "geben",
    "nahm": "nehmen", "nahmen": "nehmen", "nimmst": "nehmen",
    "nimmt": "nehmen", "genommen": "nehmen",
    "fand": "finden", "fanden": "finden", "gefunden": "finden",
    "stand": "stehen", "standen": "stehen", "gestanden": "stehen",
    "lag": "liegen", "lagen": "liegen", "gelegen": "liegen",
    "lief": "laufen", "liefen": "laufen", "läufst": "laufen",
    "läuft": "laufen", "gelaufen": "laufen",
    "fuhr": "fahren", "fuhren": "fahren", "fährst": "fahren",
    "fährt": "fahren", "gefahren": "fahren",
    "sprach": "sprechen", "sprachen": "sprechen",
    "sprichst": "sprechen", "spricht": "sprechen", "gesprochen": "sprechen",
    "schrieb": "schreiben", "schrieben": "schreiben",
    "geschrieben": "schreiben",
    "las": "lesen", "lasen": "lesen", "liest": "lesen",
    "gelesen": "lesen",
    "aß": "essen", "aßen": "essen", "isst": "essen",
    "gegessen": "essen",
    "trank": "trinken", "tranken": "trinken", "getrunken": "trinken",
    "dachte": "denken", "dachten": "denken", "gedacht": "denken",
    "brachte": "bringen", "brachten": "bringen", "gebracht": "bringen",
    "wusste": "wissen", "wussten": "wissen", "weiß": "wissen",
    "konnte": "können", "konnten": "können", "kann": "können",
    "kannst": "können",
    "musste": "müssen", "mussten": "müssen", "muss": "müssen",
    "musst": "müssen",
    "wollte": "wollen", "wollten": "wollen", "will": "wollen",
    "willst": "wollen",
    "sollte": "sollen", "sollten": "sollen", "soll": "sollen",
    "sollst": "sollen",
    "durfte": "dürfen", "durften": "dürfen", "darf": "dürfen",
    "darfst": "dürfen",
    "tat": "tun", "taten": "tun", "getan": "tun",
    "blieb": "bleiben", "blieben": "bleiben", "geblieben": "bleiben",
}
SEPARABLE = ("zurück", "weiter", "wieder", "zusammen", "vorbei", "heraus",
             "hinein", "herum", "hinauf", "auf", "ab", "an", "aus", "ein",
             "mit", "vor", "weg", "zu", "nach", "um")


def lemma_candidates(word: str):
    """Generate a small ordered set of plausible German headwords."""
    word = word.casefold().strip()
    if not word or len(word) > 70:
        return
    seen = set()

    def emit(value):
        if (len(value) < 3 or value in seen or len(value) > 70
                or not value.isalpha()):
            return None
        seen.add(value)
        return value

    first = emit(word)
    if first:
        yield first
    mapped = IRREGULAR.get(word)
    if mapped:
        candidate = emit(mapped)
        if candidate:
            yield candidate

    stems = [word]
    if word.startswith("ge") and len(word) >= 6:
        stems.append(word[2:])
    # Separable prefixes: aufgemacht -> aufmachen, mitgebracht -> mitbringen.
    for prefix in SEPARABLE:
        if word.startswith(prefix + "ge") and len(word) >= len(prefix) + 6:
            stems.append(prefix + word[len(prefix) + 2:])

    endings = ("test", "tet", "ten", "est", "ete", "ete", "te", "et",
               "st", "t", "en", "n", "e")
    for stem in stems:
        for suffix in endings:
            if not stem.endswith(suffix) or len(stem) <= len(suffix) + 2:
                continue
            base = stem[:-len(suffix)]
            for form in (base + "en", base + "n",
                         base[:-1] + "en" if base.endswith("e") else ""):
                result = emit(form)
                if result:
                    yield result

    # For nominal/adjectival inflections, exact dictionary verification is
    # essential: an ending may be grammatical but a candidate may be nonsense.
    for suffix in ("ern", "em", "es", "er", "en", "e", "s", "n"):
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            result = emit(word[:-len(suffix)])
            if result:
                yield result
