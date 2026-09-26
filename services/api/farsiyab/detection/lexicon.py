"""Load the word lists in data/lexicons/ and compile them into regexes."""

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from farsiyab.config import get_settings

# One character in, one character out: detector matches on the normalized text and
# cuts snippets from the original with the same offsets.
_FOLD = str.maketrans({
    "ي": "ی", "ك": "ک",  # Arabic yeh/kaf -> Persian, so Arabic "إيراني" matches "ایرانی"
    "إ": "ا", "أ": "ا",  # hamza forms of alef (Arabic spelling)
    "‌": " ",  # ZWNJ, so "فارسی‌زبان" == "فارسی زبان"
    "İ": "i", "ı": "i",  # Turkish dotted/dotless i ("İranlı"); "İ".lower() is two characters
})


def _normalize_term(term: str) -> str:
    return "".join(c if len(low := c.lower()) != 1 else low for c in term.translate(_FOLD))


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
    # Negative only when the same text has no explicit keyword (arabic_markers.txt).
    arabic_markers: re.Pattern[str] = re.compile(r"(?!x)x")


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
        arabic_markers=pattern("arabic_markers.txt"),
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


@lru_cache
def country_exclusions(directory: Path | None = None) -> dict[str, frozenset[str]]:
    path = (directory or get_settings().data_dir / "lexicons") / "country_exclusions.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k).upper(): frozenset(_normalize_term(t) for t in v or ()) for k, v in data.items()}


@lru_cache
def lexicons_for_country(lex: Lexicons, country: str) -> Lexicons:
    """`lex` without the explicit keywords excluded for this country."""
    excluded = country_exclusions().get(country.upper())
    if not excluded:
        return lex
    directory = get_settings().data_dir / "lexicons"
    terms = [t for t in read_terms(directory / "keywords_explicit.txt") if t not in excluded]
    return dataclasses.replace(lex, explicit=compile_terms(terms))
