"""Wikivoyage listings and Wikidata items (docs/sources/wikimedia.md).

Both are open (CC BY-SA / CC0) and need no account; Wikimedia asks for a
User-Agent with contact details, which `Settings.user_agent` provides.
"""

import logging
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx

from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField
from farsiyab.reference import CityInfo

log = logging.getLogger(__name__)

WIKIVOYAGE_API = "https://en.wikivoyage.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

LISTING_TYPES = {"eat", "drink", "buy", "see", "do", "sleep", "go", "listing"}
LISTING_CATEGORY = {"eat": "restaurant", "drink": "restaurant"}
HINTS = "Persian|Iranian|Farsi|Tehran|Shiraz|Isfahan|Esfahan|Tabriz|Persepolis"


def _client(client: httpx.Client | None) -> httpx.Client:
    # HTTP/2: Wikimedia's robot policy answered 403 to HTTP/1.1 requests from Python
    # clients during the phase 3 live test, even with a proper User-Agent.
    return client or httpx.Client(
        headers={"User-Agent": get_settings().user_agent},
        timeout=120,
        follow_redirects=True,
        http2=True,
    )


def _send(send: Any, what: str, retries: int = 2) -> httpx.Response:
    """Call `send()`; on 429 wait for Retry-After (at most 90 s) and try again."""
    for attempt in range(retries + 1):
        try:
            response = send()
        except httpx.HTTPError as exc:
            raise SourceUnavailable(f"{what} unreachable: {exc}") from exc
        if response.status_code == 429:
            if attempt == retries:
                break
            wait = min(int(response.headers.get("retry-after", "60") or 60), 90)
            log.warning("%s: rate limited, waiting %ss", what, wait)
            time.sleep(wait)
            continue
        if response.status_code != 200:
            raise SourceUnavailable(f"{what} returned HTTP {response.status_code}")
        return response
    raise SourceUnavailable(f"{what} kept rate-limiting us")


# ── Wikivoyage ────────────────────────────────────────────────────────────────


def split_template_params(body: str) -> list[str]:
    """Split a template body on top-level '|' (ignores pipes inside {{…}} and [[…]])."""
    parts, depth, current = [], 0, []
    i = 0
    while i < len(body):
        pair = body[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            i += 2
            continue
        if pair in ("}}", "]]"):
            depth -= 1
            current.append(pair)
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(body[i])
        i += 1
    parts.append("".join(current))
    return parts


def find_listings(wikitext: str) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield (type, params) for every {{eat|…}}-style listing template."""
    i = 0
    while (start := wikitext.find("{{", i)) != -1:
        depth, j = 0, start
        while j < len(wikitext):
            if wikitext.startswith("{{", j):
                depth, j = depth + 1, j + 2
            elif wikitext.startswith("}}", j):
                depth, j = depth - 1, j + 2
                if depth == 0:
                    break
            else:
                j += 1
        body = wikitext[start + 2 : j - 2]
        parts = split_template_params(body)
        kind = parts[0].strip().lower()
        if kind in LISTING_TYPES:
            params = {}
            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    params[key.strip().lower()] = value.strip()
            if kind == "listing":
                kind = params.get("type", "listing").lower()
            yield kind, params
            i = j
        else:
            i = start + 2


def plain_text(wikitext: str) -> str:
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", wikitext)  # [[a|b]] -> b
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)  # inline templates
    text = re.sub(r"'{2,}", "", text)  # bold / italic
    return re.sub(r"\s+", " ", text).strip()


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def listing_from_template(
    kind: str, params: dict[str, str], page: str, city: CityInfo
) -> RawListing | None:
    name = plain_text(params.get("name", ""))
    if not name:
        return None
    lat, lng = _float(params.get("lat")), _float(params.get("long"))
    west, south, east, north = city.bbox
    if lat is not None and lng is not None and not (south <= lat <= north and west <= lng <= east):
        return None  # a listing for a day trip outside the city
    url = f"https://en.wikivoyage.org/wiki/{page.replace(' ', '_')}"
    content = plain_text(params.get("content", ""))
    texts = [TextField("name", name, url)]
    if params.get("alt"):
        texts.append(TextField("name", plain_text(params["alt"]), url))
    if content:
        texts.append(TextField("text", content, url))
    return RawListing(
        source_id="wikivoyage",
        external_id=f"{page}#{name}",
        name=name,
        url=url,
        lat=lat,
        lng=lng,
        address=plain_text(params.get("address", "")) or None,
        category=LISTING_CATEGORY.get(kind, "other"),
        phones=[p for p in [params.get("phone", "")] if p],
        urls=[u for u in [params.get("url", "")] if u.startswith("http")],
        texts=texts,
        raw={"page": page, "type": kind, "name": name, "content": content[:500]},
    )


class WikivoyageAdapter:
    id = "wikivoyage"

    def __init__(
        self, pages: dict[str, list[str]], client: httpx.Client | None = None, delay: float = 1.0
    ):
        self.pages = pages  # city slug -> Wikivoyage page titles
        self.client = _client(client)
        self.delay = delay

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        time.sleep(self.delay)  # be gentle: one city can be dozens of district pages
        return _send(
            lambda: self.client.get(WIKIVOYAGE_API, params={**params, "format": "json"}),
            "Wikivoyage",
        ).json()

    def page_titles(self, base: str) -> list[str]:
        """The city page plus its district pages ("Toronto/Downtown", …)."""
        data = self._get({"action": "query", "list": "allpages", "apprefix": f"{base}/",
                          "aplimit": "max"})
        return [base] + [p["title"] for p in data.get("query", {}).get("allpages", [])]

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        for base in self.pages.get(city.slug, []):
            for title in self.page_titles(base):
                data = self._get({"action": "parse", "page": title, "prop": "wikitext",
                                  "formatversion": "2"})
                wikitext = data.get("parse", {}).get("wikitext", "")
                for kind, params in find_listings(wikitext):
                    listing = listing_from_template(kind, params, title, city)
                    if listing:
                        yield listing


# ── Wikidata ──────────────────────────────────────────────────────────────────


def build_sparql(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"""SELECT ?item ?enLabel ?enDesc ?faLabel ?coord ?website ?instagram ?facebook
       (GROUP_CONCAT(DISTINCT ?typeLabel; separator="|") AS ?types) WHERE {{
  SERVICE wikibase:box {{
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point({west} {south})"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point({east} {north})"^^geo:wktLiteral .
  }}
  ?item rdfs:label ?enLabel . FILTER(LANG(?enLabel) = "en")
  OPTIONAL {{ ?item schema:description ?enDesc . FILTER(LANG(?enDesc) = "en") }}
  FILTER(REGEX(?enLabel, "{HINTS}", "i") || REGEX(COALESCE(?enDesc, ""), "{HINTS}", "i"))
  OPTIONAL {{ ?item rdfs:label ?faLabel . FILTER(LANG(?faLabel) = "fa") }}
  OPTIONAL {{ ?item wdt:P856 ?website }}
  OPTIONAL {{ ?item wdt:P2003 ?instagram }}
  OPTIONAL {{ ?item wdt:P2013 ?facebook }}
  OPTIONAL {{ ?item wdt:P31 ?type . ?type rdfs:label ?typeLabel . FILTER(LANG(?typeLabel) = "en") }}
}}
GROUP BY ?item ?enLabel ?enDesc ?faLabel ?coord ?website ?instagram ?facebook
LIMIT 2000"""


TYPE_CATEGORY = (
    ("restaurant", "restaurant"), ("café", "restaurant"), ("cafe", "restaurant"),
    ("bakery", "bakery"), ("grocery", "grocery"), ("supermarket", "grocery"),
    ("school", "education"), ("university", "education"), ("organization", "community"),
    ("association", "community"), ("cultural", "community"), ("mosque", "community"),
    ("church", "community"), ("clinic", "doctor"), ("hospital", "doctor"),
    ("law firm", "lawyer"),
)


def category_from_types(types: str) -> str:
    lowered = types.lower()
    return next((slug for word, slug in TYPE_CATEGORY if word in lowered), "other")


def _value(binding: dict[str, Any], key: str) -> str | None:
    return (binding.get(key) or {}).get("value")


def point(wkt: str | None) -> tuple[float | None, float | None]:
    match = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(match.group(2)), float(match.group(1))) if match else (None, None)


def binding_to_listing(binding: dict[str, Any]) -> RawListing:
    item = _value(binding, "item") or ""
    qid = item.rsplit("/", 1)[-1]
    name = _value(binding, "enLabel") or qid
    description = _value(binding, "enDesc")
    fa_label = _value(binding, "faLabel")
    lat, lng = point(_value(binding, "coord"))
    urls = [u for u in [_value(binding, "website")] if u]
    if _value(binding, "instagram"):
        urls.append(f"https://www.instagram.com/{_value(binding, 'instagram')}/")
    if _value(binding, "facebook"):
        urls.append(f"https://www.facebook.com/{_value(binding, 'facebook')}")
    # The Persian label is shown but not used as evidence: famous places often have
    # Persian translations on Wikidata without having anything to do with Iran.
    texts = [TextField("name", name, item)]
    if description:
        texts.append(TextField("text", description, item))
    display_name = f"{name} | {fa_label}" if fa_label else name
    return RawListing(
        source_id="wikidata",
        external_id=qid,
        name=display_name,
        url=item,
        lat=lat,
        lng=lng,
        category=category_from_types(_value(binding, "types") or ""),
        urls=urls,
        texts=texts,
        raw={"qid": qid, "label": name, "description": description, "fa": fa_label},
    )


class WikidataAdapter:
    id = "wikidata"

    def __init__(self, client: httpx.Client | None = None):
        self.client = _client(client)

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        response = _send(
            lambda: self.client.post(
                WIKIDATA_SPARQL,
                data={"query": build_sparql(city.bbox)},
                headers={"Accept": "application/sparql-results+json"},
            ),
            "Wikidata",
        )
        for binding in response.json().get("results", {}).get("bindings", []):
            yield binding_to_listing(binding)
