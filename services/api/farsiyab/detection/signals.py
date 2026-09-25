"""Signal catalogue: weights and user-facing labels (docs/04-iranian-detection.md)."""

from dataclasses import dataclass

WEIGHTS: dict[str, float] = {
    "explicit_keyword": 0.6,
    "persian_product_term": 0.2,
    "osm_cuisine_tag": 0.7,
    "osm_language_fa": 0.7,
    "overture_persian_category": 0.7,
    "google_type_persian": 0.7,
    "persian_script_name": 0.5,
    "persian_script_text": 0.4,
    "website_persian_content": 0.5,
    "iranian_place_name": 0.3,
    "iranian_food_terms": 0.4,
    "persian_personal_name": 0.2,
    "listed_in_iranian_directory": 0.6,
    "linked_from_iranian_source": 0.3,
    "nowruz_yalda_mentions": 0.3,
    "user_submission_verified": 0.8,
    "registry_language_farsi": 0.8,
    "schemaorg_serves_persian": 0.7,
    "cc_persian_language_site": 0.4,
    "wikidata_iran_related": 0.5,
    "negative_keyword": 0.3,
}

NEGATIVE_SIGNALS = frozenset({"negative_keyword"})

LABELS: dict[str, tuple[str, str]] = {
    "explicit_keyword": ("ذکر صریح ایرانی یا فارسی‌زبان بودن", "Explicitly says Iranian or Farsi"),
    "persian_product_term": ("محصول ایرانی (مثلاً فرش ایرانی)", "Persian product (e.g. Persian rugs)"),
    "osm_cuisine_tag": ("برچسب غذای ایرانی در OpenStreetMap", "Persian cuisine tag in OpenStreetMap"),
    "osm_language_fa": ("برچسب زبان فارسی در OpenStreetMap", "Farsi language tag in OpenStreetMap"),
    "overture_persian_category": ("دسته‌ی رستوران ایرانی در Overture Maps", "Persian restaurant category in Overture Maps"),
    "google_type_persian": ("دسته‌ی رستوران ایرانی در Google", "Persian restaurant type in Google"),
    "persian_script_name": ("نام به خط فارسی", "Name written in Persian script"),
    "persian_script_text": ("متن فارسی", "Text in Persian"),
    "website_persian_content": ("وب‌سایت به زبان فارسی", "Website in Persian"),
    "iranian_place_name": ("نام شهر یا نماد ایرانی در نام", "Iranian place or symbol in the name"),
    "iranian_food_terms": ("غذاهای ایرانی", "Iranian dishes"),
    "persian_personal_name": ("نام خانوادگی ایرانی", "Iranian-style surname"),
    "listed_in_iranian_directory": ("ثبت در دایرکتوری ایرانی", "Listed in an Iranian directory"),
    "linked_from_iranian_source": ("لینک از یک سایت ایرانی", "Linked from an Iranian site"),
    "nowruz_yalda_mentions": ("اشاره به نوروز یا یلدا", "Mentions Nowruz or Yalda"),
    "user_submission_verified": ("ثبت‌شده و تأییدشده", "Submitted and verified"),
    "registry_language_farsi": ("زبان فارسی در رجیستری رسمی", "Farsi listed in an official registry"),
    "schemaorg_serves_persian": ("غذای ایرانی در اطلاعات ساختاریافته‌ی سایت", "Persian cuisine in the site's structured data"),
    "cc_persian_language_site": ("سایت فارسی‌زبان (Common Crawl)", "Persian-language site (Common Crawl)"),
    "wikidata_iran_related": ("ارتباط با ایران در Wikidata", "Iran-related in Wikidata"),
    "negative_keyword": ("نشانه‌ی غیرایرانی", "Signal of non-Iranian origin"),
}


@dataclass(frozen=True)
class Signal:
    signal: str
    weight: float
    snippet: str
    url: str | None = None

    @property
    def negative(self) -> bool:
        return self.signal in NEGATIVE_SIGNALS


def make(signal: str, snippet: str, url: str | None = None, weight: float | None = None) -> Signal:
    return Signal(signal, WEIGHTS[signal] if weight is None else weight, snippet[:200], url)


def label(signal: str, lang: str) -> str:
    fa, en = LABELS.get(signal, (signal, signal))
    return fa if lang == "fa" else en
