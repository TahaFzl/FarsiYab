"""Tell Persian script apart from Arabic, Pashto, Urdu and Sorani.

All of them use the Arabic Unicode block, so "has Arabic-script letters" is not
enough (docs/04-iranian-detection.md, "تشخیص خط فارسی از عربی").
"""

import re
import unicodedata
from enum import Enum

ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
ARABIC_SCRIPT_RUN = re.compile(
    r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿‌]"
    r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿‌\s\d.،\-]*"
)

# Letters that exist in Persian but not in Arabic.
PERSIAN_DEFINITIVE = set("پچژگ")
# Persian forms of yeh and kaf, and the zero-width non-joiner used in Persian words.
PERSIAN_LIKELY = {"ی", "ک", "‌"}
# Arabic-only forms.
ARABIC_ONLY = {"ي", "ك", "ة", "ى"}  # ي ك ة ى
PASHTO_ONLY = set("ټډړږښګڼېۍځڅ")
URDU_ONLY = set("ٹڈڑںےھۓہۂۃ")  # ہ (heh goal) is Urdu; Persian uses ه
SORANI_ONLY = set("ڵڕۆێەڤ")
# The Pashto possessive "د" as a word of its own ("د عبدالرحمن خان ..."); Persian never
# writes a lone dal.
PASHTO_PARTICLE = re.compile(r"(?<![\w\u0600-\u06FF])د(?![\w\u0600-\u06FF])")

SHORT_TEXT_CHARS = 15


class Script(Enum):
    PERSIAN_DEFINITIVE = "persian_definitive"
    PERSIAN_LIKELY = "persian_likely"
    OTHER = "other"  # Arabic, Pashto, Urdu, Sorani or undecidable
    NONE = "none"  # no Arabic-script letters at all


def normalize(text: str) -> str:
    """NFC-normalize and fold presentation forms (e.g. U+FEFB) to base letters."""
    return unicodedata.normalize("NFKC", text)


def classify(text: str) -> Script:
    text = normalize(text)
    letters = set(ARABIC_SCRIPT.findall(text))
    if not letters:
        return Script.NONE
    if letters & (PASHTO_ONLY | URDU_ONLY | SORANI_ONLY):
        return Script.OTHER
    if PASHTO_PARTICLE.search(text):
        return Script.OTHER
    if letters & PERSIAN_DEFINITIVE:
        return Script.PERSIAN_DEFINITIVE
    has_persian_forms = bool((letters | set(text)) & PERSIAN_LIKELY)
    if has_persian_forms and not letters & ARABIC_ONLY:
        return Script.PERSIAN_LIKELY
    return Script.OTHER


def arabic_script_part(text: str) -> str:
    """The longest run of Arabic-script text, e.g. 'صرافی دیپلمات' from
    'Diplomat Exchange | صرافی دیپلمات'."""
    runs = [m.group(0).strip(" .-،‌") for m in ARABIC_SCRIPT_RUN.finditer(normalize(text))]
    runs = [r for r in runs if ARABIC_SCRIPT.search(r)]
    return max(runs, key=len) if runs else ""


def latin_part(text: str) -> str:
    """Text with the Arabic-script runs and leftover separators removed."""
    stripped = ARABIC_SCRIPT_RUN.sub(" ", normalize(text))
    stripped = re.sub(r"[()\[\]|/–—-]+\s*$", "", stripped.strip())
    stripped = re.sub(r"^\s*[()\[\]|/–—-]+", "", stripped)
    return re.sub(r"\s{2,}", " ", stripped).strip(" |/-–—()")


def persian_letter_ratio(text: str) -> tuple[int, float]:
    """(count, ratio) of Arabic-script letters among all letters in the text."""
    text = normalize(text)
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0, 0.0
    persian = sum(1 for c in letters if ARABIC_SCRIPT.match(c))
    return persian, persian / len(letters)
