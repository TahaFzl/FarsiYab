"""Load the word lists in data/lexicons/ and compile them into regexes."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from farsiyab.config import get_settings


def _normalize_term(term: str) -> str:
    # Persian yeh/kaf, and ZWNJ treated like a space so "فارسی‌زبان" == "فارسی زبان".
    return term.replace("ي", "ی").replace("ك", "ک").replace("‌", " ").lower()


def normalize_text(text: str) -> str:
    return _normalize_term(text)


def read_terms(path: Path) -> list[str]:
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(_normalize_term(line))
    return terms


def compile_terms(terms: list[str]) -> re.Pattern[str]:
    """Whole-word match for every term; spaces inside a term also match '-' or '_'."""
    if not terms:
        return re.compile(r"(?!x)x")
    parts = []
    for term in sorted(set(terms), key=len, reverse=True):
        words = [re.escape(w) for w in re.split(r"[\s\-_]+", term) if w]
        parts.append(r"[\s\-_]+".join(words))
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


@dataclass(frozen=True)
class Lexicons:
    explicit: re.Pattern[str]
    product_terms: re.Pattern[str]
    product_adjectives: frozenset[str]
    places: re.Pattern[str]
    places_ambiguous: re.Pattern[str]
    place_adjectives: re.Pattern[str]
    foods: re.Pattern[str]
    occasions: re.Pattern[str]
    negative: re.Pattern[str]
    surname_suffixes: tuple[str, ...]


def load_lexicons(directory: Path) -> Lexicons:
    def pattern(name: str) -> re.Pattern[str]:
        return compile_terms(read_terms(directory / name))

    return Lexicons(
        explicit=pattern("keywords_explicit.txt"),
        product_terms=pattern("product_terms.txt"),
        product_adjectives=frozenset(read_terms(directory / "product_adjectives.txt")),
        places=pattern("iranian_places.txt"),
        places_ambiguous=pattern("iranian_places_ambiguous.txt"),
        place_adjectives=pattern("iranian_place_adjectives.txt"),
        foods=pattern("persian_foods.txt"),
        occasions=pattern("occasions.txt"),
        negative=pattern("negative_keywords.txt"),
        surname_suffixes=tuple(read_terms(directory / "surname_suffixes.txt")),
    )


HINT_FILES = (
    "keywords_explicit.txt",
    "iranian_places.txt",
    "iranian_places_ambiguous.txt",
    "persian_foods.txt",
    "occasions.txt",
)


@lru_cache
def latin_hint_terms(directory: Path | None = None) -> tuple[str, ...]:
    """Latin-script lexicon terms (4+ letters) used to pre-filter large registries on the
    server side; the detector then decides precisely. Surnames are left out on purpose."""
    directory = directory or get_settings().data_dir / "lexicons"
    terms = {
        term
        for name in HINT_FILES
        for term in read_terms(directory / name)
        if re.fullmatch(r"[a-z][a-z \-]{3,}", term)
    }
    return tuple(sorted(terms))


@lru_cache
def default_lexicons() -> Lexicons:
    return load_lexicons(get_settings().data_dir / "lexicons")
