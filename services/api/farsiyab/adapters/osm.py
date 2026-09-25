"""OpenStreetMap through the Overpass API (docs/sources/openstreetmap.md).

One query per city asks only for places that already carry an Iranian hint
(Persian cuisine, a Farsi name or language tag, an Iranian keyword in the
name), which keeps us far below the public server's fair-use limits.
"""

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import make
from farsiyab.reference import CategoryMapper, CityInfo, default_mapper

log = logging.getLogger(__name__)

POI_KEYS = ("amenity", "shop", "office", "healthcare", "craft", "club", "tourism", "leisure")
NAME_HINTS = "persian|iranian|farsi|tehran|shiraz|isfahan|esfahan|tabriz|mashhad|persepolis"


def build_query(bbox: tuple[float, float, float, float], timeout: int = 120) -> str:
    west, south, east, north = bbox
    b = f"({south},{west},{north},{east})"
    return f"""[out:json][timeout:{timeout}];
(
  nwr["cuisine"~"persian|iranian",i]{b};
  nwr["name:fa"]{b};
  nwr["language:fa"="yes"]{b};
  nwr["name"~"[پچژگ]"]{b};
  nwr["name"~"{NAME_HINTS}",i]{b};
  nwr["description"~"persian|iranian|farsi",i]{b};
);
out center tags;"""


def _address(tags: dict[str, str]) -> str | None:
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    parts = [street, tags.get("addr:city"), tags.get("addr:postcode")]
    return ", ".join(p for p in parts if p) or None


def element_to_listing(element: dict[str, Any], mapper: CategoryMapper) -> RawListing | None:
    tags: dict[str, str] = element.get("tags") or {}
    name = tags.get("name") or tags.get("name:en") or tags.get("name:fa")
    if not name or not any(key in tags for key in POI_KEYS):
        return None

    osm_type, osm_id = element["type"], element["id"]
    url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lng = element.get("lon", (element.get("center") or {}).get("lon"))

    texts = [TextField("name", n, url) for n in dict.fromkeys(
        tags.get(k) for k in ("name", "name:fa", "name:en", "alt_name", "brand") if tags.get(k)
    )]
    if tags.get("description"):
        texts.append(TextField("text", tags["description"], url))

    signals = []
    cuisine = tags.get("cuisine", "")
    if any(c.strip().lower() in ("persian", "iranian") for c in cuisine.split(";")):
        signals.append(make("osm_cuisine_tag", f"cuisine={cuisine}", url))
    if tags.get("language:fa") == "yes":
        signals.append(make("osm_language_fa", "language:fa=yes", url))

    urls = [
        tags[k]
        for k in ("website", "contact:website", "contact:instagram", "contact:facebook",
                  "contact:telegram", "facebook", "instagram")
        if tags.get(k)
    ]
    # contact:instagram is sometimes a bare username.
    urls = [
        f"https://www.instagram.com/{u.lstrip('@')}" if "/" not in u and "." not in u else u
        for u in urls
    ]
    phones = [p.strip() for k in ("phone", "contact:phone") for p in tags.get(k, "").split(";")]

    return RawListing(
        source_id="osm",
        external_id=f"{osm_type}/{osm_id}",
        name=name,
        url=url,
        lat=lat,
        lng=lng,
        address=_address(tags),
        category=mapper.osm(tags),
        phones=[p for p in phones if p],
        urls=urls,
        texts=texts,
        signals=signals,
        raw={"type": osm_type, "id": osm_id, "tags": tags},
    )


class OsmAdapter:
    id = "osm"

    def __init__(
        self,
        client: httpx.Client | None = None,
        mapper: CategoryMapper | None = None,
        retries: int = 2,
    ) -> None:
        settings = get_settings()
        self.url = settings.overpass_url
        self.client = client or httpx.Client(
            headers={"User-Agent": settings.user_agent}, timeout=180
        )
        self.mapper = mapper or default_mapper()
        self.retries = retries

    def _query(self, query: str) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            try:
                response = self.client.post(self.url, data={"data": query})
            except httpx.HTTPError as exc:
                raise SourceUnavailable(f"Overpass unreachable: {exc}") from exc
            if response.status_code in (429, 502, 503, 504) and attempt < self.retries:
                wait = 30 * (attempt + 1)
                log.warning("overpass: HTTP %s, retrying in %ss", response.status_code, wait)
                time.sleep(wait)
                continue
            if response.status_code != 200:
                raise SourceUnavailable(f"Overpass returned HTTP {response.status_code}")
            return response.json()
        raise SourceUnavailable("Overpass kept rejecting the query")

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        log.info("osm: querying Overpass for %s", city.slug)
        data = self._query(build_query(city.bbox))
        for element in data.get("elements", []):
            listing = element_to_listing(element, self.mapper)
            if listing:
                yield listing
