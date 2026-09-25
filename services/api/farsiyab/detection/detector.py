"""Turn text into Iranian-ness signals and combine them into a confidence score.

See docs/04-iranian-detection.md for the signal catalogue, the weights and the
false positives found in real data that the rules below guard against.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from math import prod
from typing import Literal

from farsiyab.detection import script
from farsiyab.detection.lexicon import Lexicons, default_lexicons, normalize_text
from farsiyab.detection.signals import WEIGHTS, Signal, make

FieldKind = Literal["name", "text", "username", "page"]

LATIN_TOKEN = re.compile(r"[A-Za-z]+")
SNIPPET_CONTEXT = 60

AMBIGUOUS_PLACE_WEIGHT = 0.15
LABEL_THRESHOLDS = (("high", 0.75), ("medium", 0.45), ("low", 0.25))


@dataclass(frozen=True)
class TextField:
    kind: FieldKind
    text: str
    url: str | None = None


def _context(text: str, start: int, end: int) -> str:
    lo, hi = max(0, start - SNIPPET_CONTEXT), min(len(text), end + SNIPPET_CONTEXT)
    snippet = re.sub(r"\s+", " ", text[lo:hi]).strip()
    return ("…" if lo > 0 else "") + snippet + ("…" if hi < len(text) else "")


def _script_signal(field: TextField) -> Signal | None:
    if field.kind in ("username", "page"):
        return None
    kind = script.classify(field.text)
    if kind not in (script.Script.PERSIAN_DEFINITIVE, script.Script.PERSIAN_LIKELY):
        return None
    part = script.arabic_script_part(field.text)
    name = "persian_script_name" if field.kind == "name" else "persian_script_text"
    weight = WEIGHTS[name]
    if kind is script.Script.PERSIAN_LIKELY and len(part) < script.SHORT_TEXT_CHARS:
        weight /= 2
    snippet = part if field.kind == "name" else _context(field.text, 0, len(part))
    return make(name, snippet or field.text, field.url, weight)


def _keyword_signals(field: TextField, lex: Lexicons) -> list[Signal]:
    text = field.text
    norm = normalize_text(text)
    found: list[Signal] = []

    matches = list(lex.explicit.finditer(norm))
    product = lex.product_terms.search(norm)
    if product:
        adjectives = [m for m in matches if m.group(0) in lex.product_adjectives]
        matches = [m for m in matches if m.group(0) not in lex.product_adjectives]
    if matches:
        found.append(make("explicit_keyword", _context(text, *matches[0].span()), field.url))
    elif product and adjectives:
        found.append(make("persian_product_term", _context(text, *adjectives[0].span()), field.url))

    for pattern, signal in (
        (lex.places, "iranian_place_name"),
        (lex.place_adjectives, "persian_personal_name"),
        (lex.foods, "iranian_food_terms"),
        (lex.occasions, "nowruz_yalda_mentions"),
        (lex.negative, "negative_keyword"),
    ):
        m = pattern.search(norm)
        if m:
            found.append(make(signal, _context(text, *m.span()), field.url))
    m = lex.places_ambiguous.search(norm)
    if m:
        found.append(make("iranian_place_name", _context(text, *m.span()), field.url,
                          weight=AMBIGUOUS_PLACE_WEIGHT))

    if field.kind == "name":
        for m in LATIN_TOKEN.finditer(text):
            token = m.group(0).lower()
            if any(
                token.endswith(suffix) and len(token) >= len(suffix) + 3
                for suffix in lex.surname_suffixes
            ):
                found.append(make("persian_personal_name", _context(text, *m.span()), field.url))
                break
    return found


def detect(
    fields: Iterable[TextField],
    extra: Iterable[Signal] = (),
    lexicons: Lexicons | None = None,
) -> list[Signal]:
    """All signals for one source record, strongest first, one per signal type."""
    lex = lexicons or default_lexicons()
    candidates: list[Signal] = list(extra)
    for field in fields:
        if not field.text or not field.text.strip():
            continue
        signal = _script_signal(field)
        if signal:
            candidates.append(signal)
        candidates.extend(_keyword_signals(field, lex))

    best: dict[str, Signal] = {}
    for signal in candidates:
        current = best.get(signal.signal)
        if current is None or signal.weight > current.weight:
            best[signal.signal] = signal
    return sorted(best.values(), key=lambda s: s.weight, reverse=True)


def score(signals: Iterable[Signal]) -> float:
    """Noisy-OR over the strongest signal of each type, damped once by negatives."""
    positive: dict[str, float] = {}
    has_negative = False
    for s in signals:
        if s.negative:
            has_negative = True
        else:
            positive[s.signal] = max(positive.get(s.signal, 0.0), s.weight)
    value = 1 - prod(1 - w for w in positive.values())
    if has_negative:
        value *= 1 - WEIGHTS["negative_keyword"]
    return round(value, 4)


def confidence_label(value: float) -> str | None:
    for name, threshold in LABEL_THRESHOLDS:
        if value >= threshold:
            return name
    return None


def has_positive(signals: Iterable[Signal]) -> bool:
    return any(not s.negative for s in signals)
